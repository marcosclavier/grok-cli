import os
import json
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module='langchain')
import tiktoken
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory, ConversationSummaryBufferMemory
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import PromptTemplate
from langchain_community.callbacks import get_openai_callback
from langchain_core.messages import BaseMessage
from typing import List

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

# Custom token counter
def get_grok_num_tokens(messages, model="grok-4-0709"):
    encoding = tiktoken.encoding_for_model("gpt-4")  # Proxy
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # Overhead
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += -1
    num_tokens += 2  # Response priming
    return num_tokens

# Custom LLM subclass
class CustomChatOpenAI(ChatOpenAI):
    def get_num_tokens_from_messages(self, messages: List[BaseMessage]) -> int:
        converted_messages = [{"role": msg.type, "content": msg.content if isinstance(msg.content, str) else str(msg.content)} for msg in messages]
        return get_grok_num_tokens(converted_messages)

from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# Tool calling prompt (trimmed for efficiency)
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", """You are an autonomous AI assistant specializing in software engineering tasks.
Your primary goal is to help the user by safely and efficiently modifying files and executing commands.

**Core Mandates:**
- Analyze request and context using tools.
- Plan step-by-step; share for complex changes.
- Implement with `edit_file`.
- Verify with `read_file`; retry if needed.
- Persist until resolved; handle errors by retrying.
- Be concise; focus on results.

**Tool Usage:**
- Use `list_files`, `read_file`, `edit_file` for filesystem.
- Precise args; `old_text` with context.

**Modification Workflow:**
1. Read file.
2. Identify exact `old_text`/`new_text`.
3. Edit.
4. Verify; retry if incorrect.

**Debugging:**
- Analyze errors; adjust and retry.
- Do not finish prematurely.

**Current Context:**
- CLI with filesystem tools.

Proceed with request."""),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)

class GrokAgent:
    def __init__(self, api_key, model="grok-4-0709", base_url="https://api.x.ai/v1", summarize_memory=True):  # Default to True
        self.llm = CustomChatOpenAI(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=0.0,
            max_tokens=4096,  # Reduced for efficiency
        )
        self.model = model  # Add this
        
        self.tools = [list_files, read_file, edit_file]
        
        self.context_window = 256000 if "grok-4" in model else 16384  # Accurate for Grok-4
        
        if summarize_memory:
            self.memory = ConversationSummaryBufferMemory(
                llm=self.llm,  # Use subclass, no bind
                memory_key="chat_history",
                return_messages=True,
                input_key="input",
                output_key="output",  # Explicit
                max_token_limit=2000
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
            max_iterations=25,
            handle_parsing_errors="Check your output and try again.",
            verbose=False,  # Disabled for production efficiency
            early_stopping_method="force",
            return_intermediate_steps=True
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
                    tool_output = step[1]
                    try:
                        output_dict = json.loads(tool_output)
                        if "error" in output_dict:
                            error_count += 1
                    except json.JSONDecodeError:
                        pass
                
                self.last_error_count = error_count
                
            return response["output"]
        except Exception as e:
            self.last_error_count += 1
            return f"An error occurred: {str(e)}. Check file permissions or path."