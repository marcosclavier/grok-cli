import os
import json
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module='langchain')
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import PromptTemplate

# --- The Definitive Monkey-Patch ---
import openai
original_create = openai.resources.chat.completions.Completions.create
def patched_create(*args, **kwargs):
    kwargs.pop("stop", None)
    return original_create(*args, **kwargs)
openai.resources.chat.completions.Completions.create = patched_create
# --- End of the Definitive Monkey-Patch ---

# Custom file tools (replacing Composio's FILETOOL)
@tool
def list_files() -> str:
    """List all files in the current working directory."""
    try:
        files = os.listdir(os.getcwd())
        return json.dumps({"files": files})
    except Exception as e:
        return f"Error listing files: {str(e)}"

@tool
def read_file(file_path: str) -> str:
    """Read the content of a file at the given path."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return json.dumps({"content": content})
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"

@tool
def edit_file(file_path: str, old_text: str = "", new_text: str = "") -> str:
    """Edit a file by replacing old_text with new_text. If old_text is empty, new_text is appended. If new_text is empty, old_text is deleted. Use relative path."""
    try:
        if not os.path.exists(file_path):
            return f"Error: File '{file_path}' does not exist."
        
        with open(file_path, 'r') as f:
            content = f.read()

        if old_text and new_text:
            new_content = content.replace(old_text, new_text)
        elif old_text and not new_text:
            new_content = content.replace(old_text, "")
        elif not old_text and new_text:
            new_content = content + new_text
        else:
            return "Error: Must provide either old_text or new_text (or both)."

        with open(file_path, 'w') as f:
            f.write(new_content)
            
        return "File edited successfully."
    except Exception as e:
        return f"Error editing file '{file_path}': {str(e)} (Check permissions or path)."

from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# Tool calling prompt (simpler, no ReAct needed)
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful assistant with access to tools for file operations. Always use the appropriate tools to complete the user's request. Confirm the update in your final response."),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ]
)

class GrokAgent:
    def __init__(self, api_key, model="grok-4-0709", base_url="https://api.x.ai/v1"):
        self.llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=0.0,
            max_tokens=1000,
        )
        
        self.tools = [list_files, read_file, edit_file]
        
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
            max_iterations=15,  # Prevent hangs
            handle_parsing_errors=True,
            verbose=True,  # Set to False in production; helpful for debugging
            early_stopping_method="generate"
        )

    def chat(self, user_message):
        try:
            response = self.executor.invoke({"input": user_message})
            return response["output"]
        except Exception as e:
            return f"An error occurred: {str(e)}. Check file permissions or path."