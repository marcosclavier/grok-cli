import click
import os
from .agent import GrokAgent

@click.command()
@click.option('--api-key', default=None, help='xAI API key. If not provided, uses XAI_API_KEY env var.')
@click.option('--dev', is_flag=True, help='Use cheaper OpenAI model for development (requires OPENAI_API_KEY)')
@click.option('--prompt', default=None, help='Prompt to run directly. If not provided, enters interactive mode.')
def main(api_key, dev, prompt):
    if dev:
        # Development mode with cheaper OpenAI model
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            raise click.UsageError("Development mode requires OPENAI_API_KEY environment variable. Get it from https://platform.openai.com/api-keys")
        agent = GrokAgent(api_key=openai_key, model="gpt-3.5-turbo", base_url="https://api.openai.com/v1")
        print("🚧 DEVELOPMENT MODE: Using OpenAI gpt-3.5-turbo (cheaper)")
    else:
        # Production mode with Grok
        api_key = api_key or os.getenv('XAI_API_KEY')
        if not api_key:
            raise click.UsageError("API key is required. Provide via --api-key or XAI_API_KEY environment variable. Get it from https://x.ai/api.")
        agent = GrokAgent(api_key=api_key)
    
    # ASCII Art for Grok 4 CLI
    print("""
 ██████╗ ██████╗  ██████╗ ██╗  ██╗    ██╗  ██╗     ██████╗██╗     ██╗
██╔════╝ ██╔══██╗██╔═══██╗██║ ██╔╝    ██║  ██║    ██╔════╝██║     ██║
██║  ███╗██████╔╝██║   ██║█████╔╝     ███████║    ██║     ██║     ██║
██║   ██║██╔══██╗██║   ██║██╔═██╗     ╚════██║    ██║     ██║     ██║
╚██████╔╝██║  ██║╚██████╔╝██║  ██╗         ██║    ╚██████╗███████╗██║
 ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝         ╚═╝     ╚═════╝╚══════╝╚═╝
    """)
    print("Chat with Grok 4 in your terminal.")
    print("Type 'exit' to quit.")
    
    if prompt:
        response = agent.chat(prompt)
        print(f"✦ {response}")
    else:
        while True:
            user_input = input("You: ")
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break
            response = agent.chat(user_input)
            print(f"✦ {response}")