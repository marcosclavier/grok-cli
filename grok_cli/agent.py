import json
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from composio_langchain import ComposioToolSet, App

# The prompt template is now manually defined with a very specific example.
REACT_PROMPT_TEMPLATE = """
Assistant is a large language model trained by Google.

Assistant is designed to be able to assist with a wide range of tasks, from answering simple questions to providing in-depth explanations and discussions on a wide range of topics. As a language model, Assistant is able to generate human-like text in response to a wide range of prompts and questions, allowing it to engage in natural-sounding conversations and provide responses that are coherent and relevant to the topic at hand.

Assistant is constantly learning and improving, and its capabilities are constantly evolving. It is able to process and understand large amounts of text, and can use this knowledge to provide accurate and informative responses to a wide range of questions. Additionally, Assistant is able to generate its own text, allowing it to engage in discussions and provide explanations and descriptions on a wide range of topics.

Overall, Assistant is a powerful tool that can help with a wide range of tasks and provide valuable insights and information on a wide range of topics. Whether you need help with a specific question or just want to have a conversation about a particular topic, Assistant is here to assist.

TOOLS:
------
Assistant has access to the following tools:

{tools}

To use a tool, please use the following format. For example, to read a file named 'example.txt', you would format your response *exactly* like this:

```json
{{
    "action": "FILETOOL_OPEN_FILE",
    "action_input": {{
        "file_path": "example.txt"
    }}
}}
```

When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:

```json
{{
    "action": "Final Answer",
    "action_input": "your response to the user"
}}
```

Begin!

Previous conversation history:
{chat_history}

New input: {input}
Assistant:
"""

class GrokAgent:
    def __init__(self, api_key, model="grok-4-0709", base_url="https://api.x.ai/v1"):
        self.llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=0.7,
            max_tokens=1000,
        )
        
        self.composio_toolset = ComposioToolSet()
        self.tools = self.composio_toolset.get_tools(apps=[App.FILETOOL])
        self.tool_names = ", ".join([tool.name for tool in self.tools])
        
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

    def chat(self, user_message):
        prompt = REACT_PROMPT_TEMPLATE.format(
            tools=self.tool_names,
            chat_history=self.memory.chat_memory.messages,
            input=user_message
        )

        try:
            llm_response = self.llm.invoke(prompt)
            response_text = llm_response.content

            if '```json' in response_text:
                json_str = response_text.split('```json')[1].split('```')[0].strip()
                parsed_json = json.loads(json_str)
                
                action = parsed_json.get("action")
                action_input = parsed_json.get("action_input")

                if action == "Final Answer":
                    print(action_input)
                    self.memory.save_context({"input": user_message}, {"output": action_input})
                    return action_input

                tool_to_use = next((t for t in self.tools if t.name == action), None)
                if tool_to_use:
                    tool_output = tool_to_use.invoke(action_input)

                    # Instead of printing the raw dict, parse it for a clean response.
                    if isinstance(tool_output, dict) and tool_output.get("successful"):
                        data = tool_output.get("data", {})
                        message = data.get("message", "Tool executed successfully.")
                        lines = data.get("lines")
                        
                        clean_output = message
                        if lines:
                            clean_output += f"\n{lines}"
                        
                        print(clean_output)
                        self.memory.save_context({"input": user_message}, {"output": clean_output})
                        return clean_output
                    elif isinstance(tool_output, dict):
                        error_message = tool_output.get("error", "An unknown error occurred.")
                        clean_output = f"Error executing tool: {error_message}"
                        print(clean_output)
                        self.memory.save_context({"input": user_message}, {"output": clean_output})
                        return clean_output
                    else:
                        # Fallback for non-dict tool outputs
                        clean_output = str(tool_output)
                        print(clean_output)
                        self.memory.save_context({"input": user_message}, {"output": clean_output})
                        return clean_output
                else:
                    final_response = f"Error: Tool '{action}' not found."
                    print(final_response)
                    return final_response
            else:
                print(response_text)
                self.memory.save_context({"input": user_message}, {"output": response_text})
                return response_text

        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            print(error_msg)
            return error_msg
