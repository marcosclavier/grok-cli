import os
import json
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module='langchain')
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory, ConversationSummaryBufferMemory
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import PromptTemplate
from langchain_community.callbacks import get_openai_callback

# --- The Definitive Monkey-Patch ---
import openai
original_create = openai.resources.chat.completions.Completions.create
def patched_create(*args, **kwargs):
    if "stop" in kwargs:
        kwargs["stop"] = []
    return original_create(*args, **kwargs)
openai.resources.chat.completions.Completions.create = patched_create
# --- End of the Definitive Monkey-Patch ---

# Custom file tools (replacing Composio's FILETOOL)
@tool
def list_files() -> str:
    """Lists the names of files and subdirectories directly within a specified directory path.
    This tool provides an overview of the current working directory's contents.

    Returns:
        str: A JSON string containing a list of file and directory names.
             Example: `{"files": ["file1.txt", "subdir", "another_file.py"]}`
             Returns an error message if the directory cannot be listed.
    """
    try:
        files = os.listdir(os.getcwd())
        return json.dumps({"files": files})
    except Exception as e:
        return json.dumps({"error": f"Error listing files: {str(e)}"})

@tool
def read_file(file_path: str) -> str:
    """Reads the content of a specified file from the local filesystem.
    This tool is useful for inspecting the contents of text-based files.

    Args:
        file_path (str): The path to the file to read. This should be a relative path
                         from the current working directory.

    Returns:
        str: A JSON string containing the content of the file.
             Example: `{"content": "This is the content of the file."}`
             Returns an error message if the file cannot be read (e.g., file not found, permissions issues).
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return json.dumps({"content": content})
    except Exception as e:
        return json.dumps({"error": f"Error reading file '{file_path}': {str(e)}"})

@tool
def edit_file(file_path: str, old_text: str = "", new_text: str = "") -> str:
    """Edits a file by replacing occurrences of `old_text` with `new_text`.
    This tool can be used to modify existing content, append new content, or delete existing content.

    Args:
        file_path (str): The path to the file to edit. This should be a relative path
                         from the current working directory.
        old_text (str, optional): The exact literal text to be replaced. If empty, `new_text`
                                  will be appended to the file. Defaults to "".
        new_text (str, optional): The exact literal text to replace `old_text` with. If empty,
                                  `old_text` will be deleted from the file. Defaults to "".

    Returns:
        str: A success message if the file was edited successfully, or an error message
             if the file does not exist, permissions are insufficient, or both `old_text`
             and `new_text` are empty.
    """
    try:
        if not os.path.exists(file_path):
            return json.dumps({"error": f"Error: File '{file_path}' does not exist."})
        
        original_content = ""
        with open(file_path, 'r') as f:
            original_content = f.read()

        new_content = original_content
        operation = "none"

        if old_text and new_text:
            if old_text not in original_content:
                return json.dumps({"error": f"Error: 'old_text' not found in file. Re-read and adjust."})
            new_content = original_content.replace(old_text, new_text, 1)  # Limit to first occurrence for precision
            operation = "replace"
        elif old_text and not new_text:
            new_content = original_content.replace(old_text, "")
            operation = "delete"
        elif not old_text and new_text:
            new_content = original_content + new_text
            operation = "append"
        else:
            return json.dumps({"error": "Error: Must provide either old_text or new_text (or both)."})

        with open(file_path, 'w') as f:
            f.write(new_content)
            
        return json.dumps({
            "status": "success",
            "message": "File edited successfully.",
            "file_path": file_path,
            "operation": operation,
            "old_content_snippet": original_content[:200] + "..." if len(original_content) > 200 else original_content,
            "new_content_snippet": new_content[:200] + "..." if len(new_content) > 200 else new_content
        })
    except Exception as e:
        return json.dumps({"error": f"Error editing file '{file_path}': {str(e)} (Check permissions or path)."})

from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# Tool calling prompt (simpler, no ReAct needed)
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", """You are an autonomous AI assistant specializing in software engineering tasks.
Your primary goal is to help the user by safely and efficiently modifying files and executing commands.

**Core Mandates:**
- **Understand:** Thoroughly analyze the user's request and the current project context. Use file reading and listing tools extensively to gather information.
- **Plan:** Formulate a clear, step-by-step plan to address the user's request. Share this plan with the user if it's complex or involves significant changes.
- **Implement:** Use file modification tools (like `edit_file`) to apply changes.
- **Verify:** After making changes, always use `read_file` to confirm the edit was applied correctly. If not, retry with adjusted parameters.
- **Confirm & Persist:** After performing an action, confirm the update in your final response. If the task is incomplete (e.g., verification fails), do not end—continue with corrective actions. Persist until fully resolved, especially for small files where mismatches might occur due to whitespace.
- **Error Handling:** If a tool call fails, analyze the error, explain it, and retry. For `edit_file` failures like 'old_text not found', re-read the file, adjust `old_text` (include exact whitespace/line endings), and try again.

**Tool Usage:**
- Always use the provided tools (`list_files`, `read_file`, `edit_file`) when interacting with the filesystem.
- Provide precise arguments to tools. For `edit_file`, ensure `old_text` includes surrounding context for accuracy.

**File Modification Workflow:**
When asked to modify a file:
1. **Read the file:** Use the `read_file` tool to get the current content of the target file.
2. **Identify `old_text` and `new_text`:** Carefully determine the exact `old_text` (the string to be replaced) and the `new_text` (its replacement). Ensure `old_text` is precise, including whitespace, newlines, and surrounding context, to avoid unintended changes. Normalize for common issues like line endings.
3. **Call `edit_file`:** Use the `edit_file` tool with the `file_path`, `old_text`, and `new_text` arguments.
4. **Verify:** Always use `read_file` again to confirm the changes. If incorrect, analyze and retry.

**Debugging and Self-Correction:**
- If a tool returns an error, analyze the error message carefully.
- If `edit_file` fails because `old_text` was not found or found multiple times, re-read the file to get the latest content and adjust `old_text` to be more precise (e.g., full line).
- If verification shows the edit didn't take effect as expected, retry the entire workflow.
- Do not finish prematurely; if unresolved, plan the next step instead of finalizing.

**Communication:**
- Be concise and direct.
- Focus on actions taken and results.
- Do not engage in conversational filler.

**Current Context:**
- You are operating within a command-line interface.
- You have access to file system tools.

Now, proceed with the user's request."""),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)

class GrokAgent:
    def __init__(self, api_key, model="grok-4-0709", base_url="https://api.x.ai/v1", summarize_memory=False):
        self.llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=0.0,
            max_tokens=128000,  # Increased for better context handling
        )
        
        self.tools = [list_files, read_file, edit_file]
        
        self.context_window = 128000 if "grok-4" in model else 16384  # Model-specific context window
        
        if summarize_memory:
            self.memory = ConversationSummaryBufferMemory(
                llm=self.llm,
                memory_key="chat_history",
                return_messages=True,
                input_key="input",
                max_token_limit=2000  # Summarize if history exceeds this
            )
        else:
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                input_key="input"
            )
        
        # Create tool calling agent
        self.agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            max_iterations=25,  # Increased to allow more steps
            handle_parsing_errors="Check your output and try again.",
            verbose=True,  # Set to False in production; helpful for debugging
            early_stopping_method="force",  # Force agent to continue until max_iterations or explicit stop
            return_intermediate_steps=True  # For debugging intermediate tool calls
        )

        self.last_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.last_error_count = 0

    def chat(self, user_message):
        try:
            with get_openai_callback() as cb:
                response = self.executor.invoke({"input": user_message})
                
                self.last_token_usage = {
                    "prompt_tokens": cb.prompt_tokens,
                    "completion_tokens": cb.completion_tokens,
                    "total_tokens": cb.total_tokens
                }
                
                error_count = 0
                for step in response.get("intermediate_steps", []):
                    tool_output = step[1]  # AgentAction, tool output
                    try:
                        output_dict = json.loads(tool_output)
                        if "error" in output_dict:
                            error_count += 1
                    except json.JSONDecodeError:
                        pass  # Non-JSON output, skip
                
                self.last_error_count = error_count
                
            return response["output"]
        except Exception as e:
            self.last_error_count += 1  # Count top-level exceptions
            return f"An error occurred: {str(e)}. Check file permissions or path."
