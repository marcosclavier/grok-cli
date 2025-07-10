from openai import OpenAI
from composio_openai import ComposioToolSet, Action, App  # Import for Composio integration
import time
import random

class GrokAgent:
    def __init__(self, api_key, model="grok-4-0709", base_url="https://api.x.ai/v1"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.messages = []  # Maintain conversation history
        self.tools = None
        self.toolset = None
        self.toolset = ComposioToolSet()
        self.tools = self.toolset.get_tools(apps=[App.FILETOOL])    # Add more apps here
    
    def _make_api_call_with_retry(self, api_call_func, max_retries=3):
        """Make API call with exponential backoff retry for rate limits"""
        for attempt in range(max_retries):
            try:
                return api_call_func()
            except Exception as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff
                        print(f"Rate limit hit. Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                raise e

    def chat(self, user_message):
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        if self.tools:
            # Non-streaming mode with tool calling (ReAct loop for simplicity)
            while True:
                response = self._make_api_call_with_retry(lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=self.tools,
                    tool_choice="auto",
                    stream=False,
                    max_tokens=1000  # Limit response length to save tokens
                ))
                message = response.choices[0].message
                if message.tool_calls:
                    # Handle tool calls
                    self.messages.append(message)  # Add assistant message with tool calls
                    for tool_call in message.tool_calls:
                        print(f"Executing tool: {tool_call.function.name} with args: {tool_call.function.arguments}")
                        # Execute via Composio
                        tool_output = self.toolset.execute_tool_call(tool_call)
                        # Append tool response to messages
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": str(tool_output),
                        })
                    # Continue the loop to let the model respond to tool outputs
                else:
                    # No more tool calls; this is the final response
                    response_content = message.content
                    print(response_content)
                    self.messages.append({"role": "assistant", "content": response_content})
                    return response_content
        else:
            # Original streaming mode without tools
            stream = self._make_api_call_with_retry(lambda: self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                stream=True,
                max_tokens=1000  # Limit response length to save tokens
            ))
            response_content = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    response_content += content
            print()  # Newline after response
            self.messages.append({"role": "assistant", "content": response_content})
            return response_content