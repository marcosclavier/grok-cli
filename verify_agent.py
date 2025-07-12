import os
from grok_cli.agent import GrokAgent

api_key = os.getenv('XAI_API_KEY')
if not api_key:
    print("Error: XAI_API_KEY environment variable is not set.")
else:
    agent = GrokAgent(api_key=api_key)
    response = agent.chat('add "hello dolly" to the readme.md file')
    print(response)
