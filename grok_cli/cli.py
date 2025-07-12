import click
import os
import json
from .agent import GrokAgent
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt

console = Console()

def print_gemini_logo():
    logo_text = """
    ██████╗ ██████╗ ██████╗ ██╗  ██╗    ██╗  ██╗     ██████╗██╗     ██╗
    ██╔════╝ ██╔══██╗██╔═══██╗██║ ██╔╝    ██║  ██║    ██╔════╝██║     ██║
    ██║  ███╗██████╔╝██║   ██║█████╔╝     ███████║    ██║     ██║     ██║
    ██║   ██║██╔══██╗██║   ██║██╔═██╗     ╚════██║    ██║     ██║     ██║
    ╚██████╔╝██║  ██║╚██████╔╝██║  ██╗         ██║    ╚██████╗███████╗██║
     ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝         ╚═╝     ╚═════╝╚══════╝╚═╝
    """
    
    colors = ["#0000FF", "#0033FF", "#0066FF", "#0099FF", "#00CCFF", "#00FFCC", "#00FF99", "#00FF66", "#00FF33", "#00FF00"]
    gradient_logo = Text()
    for i, line in enumerate(logo_text.split("\n")):
        color_index = (i * (len(colors) - 1)) // len(logo_text.split("\n"))
        gradient_logo.append(line + "\n", style=colors[color_index])

    console.print(gradient_logo)

@click.command()
@click.option('--api-key', default=None, help='xAI API key. If not provided, uses XAI_API_KEY env var.')
@click.option('--dev', is_flag=True, help='Use cheaper OpenAI model for development (requires OPENAI_API_KEY)')
def main(api_key, dev):
    if dev:
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            raise click.UsageError("Development mode requires OPENAI_API_KEY environment variable. Get it from https://platform.openai.com/api-keys")
        agent = GrokAgent(api_key=openai_key, model="gpt-3.5-turbo", base_url="https://api.openai.com/v1")
        console.print("[bold yellow]🚧 DEVELOPMENT MODE: Using OpenAI gpt-3.5-turbo (cheaper)[/bold yellow]")
    else:
        api_key = api_key or os.getenv('XAI_API_KEY')
        if not api_key:
            raise click.UsageError("API key is required. Provide via --api-key or XAI_API_KEY environment variable. Get it from https://x.ai/api.")
        agent = GrokAgent(api_key=api_key)
    
    print_gemini_logo()
    console.print("Tips for getting started:")
    console.print("1. Ask questions, edit files, or run commands.")
    console.print("2. Be specific for the best results.")
    console.print("3. Create GEMINI.md files to customize your interactions with Gemini.")
    console.print("4. /help for more information.")
    console.print("Using 5 MCP servers (ctrl+t to view)")

    while True:
        user_input = Prompt.ask("[bold blue]> [/bold blue]Type your message or @path/to/file")
        if user_input.lower() == 'exit':
            console.print("[bold red]Goodbye![/bold red]")
            break
        
        response = agent.chat(user_input)
        
        if isinstance(response, dict):
            if response.get("type") == "tool_code":
                code_content = response.get("code", "")
                if isinstance(code_content, dict):
                    display_text = json.dumps(code_content, indent=2)
                else:
                    display_text = str(code_content)
                console.print(Panel(Text(display_text, style="green"), title="[bold green]Tool Output[/bold green]"))
            else:
                display_text = json.dumps(response, indent=2)
                console.print(Panel(Text(display_text, style="yellow"), title="[bold yellow]Agent Response[/bold yellow]"))
        else:
            console.print(f"[bold green]✦ {response}[/bold green]")
