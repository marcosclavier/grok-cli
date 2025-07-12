import click
import os
import subprocess
from .agent import GrokAgent

def print_grok_art():
    """Prints the bold Grok CLI ASCII art."""
    art = """
  ██████╗ ██████╗  ██████╗ ██╗  ██╗   ██████╗ ██╗     ██████╗
 ██╔════╝ ██╔══██╗██╔═══██╗██║ ██╔╝  ██╔════╝ ██║     ╚═██╔═╝
 ██║  ███╗██████╔╝██║   ██║█████╔╝   ██║      ██║       ██║  
 ██║   ██║██╔══██╗██║   ██║██╔═██╗   ██║      ██║       ██║  
 ╚██████╔╝██║  ██║╚██████╔╝██║  ██╗  ╚██████╗ ███████╗███████╗
  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═════╝ ╚══════╝╚══════╝
"""
    click.echo(click.style(art, fg='magenta'))


def print_status_bar():
    """Prints the status bar at the bottom, styled like the Gemini CLI."""
    # Get current directory and git branch
    current_dir = os.getcwd().replace(os.path.expanduser("~"), "~")
    try:
        git_branch_raw = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        git_branch = f"({git_branch_raw})"
    except subprocess.CalledProcessError:
        git_branch = ""

    # --- Grok-style status elements ---
    sandbox_info = "no sandbox (see /docs)"
    # Use cyan for the model info
    model_info = click.style("grok-4 (100% context left)", fg="cyan") 
    # Use red for errors, with a placeholder count
    errors_info = click.style("X 0 errors (ctrl+o for details)", fg="red") 

    status_line = f"  {current_dir} {git_branch}   {sandbox_info}   {model_info} | {errors_info}"
    
    # The entire status bar is dimmed
    click.echo(click.style(status_line, dim=True))

def display_user_prompt(text):
    """Displays the user's entered prompt inside a styled box."""
    # Don't display empty prompts
    if not text.strip():
        return
        
    width = len(text) + 4
    click.echo("  " + click.style("╭" + "─" * width + "╮", dim=True))
    click.echo("  " + click.style("│", dim=True) + f" > {text} " + click.style("│", dim=True))
    click.echo("  " + click.style("╰" + "─" * width + "╯", dim=True))
    click.echo()

def display_agent_response(text):
    """Formats and displays the agent's response based on its content."""
    # Check for the special "WriteFile" command from the agent
    if text.startswith("WriteFile:"):
        parts = text.split('\n', 1)
        header = parts[0]
        code = parts[1] if len(parts) > 1 else ""
        filename = header.split(':', 1)[1].strip()

        # Print the green "WriteFile" block
        click.echo("  " + click.style("╭" + "─" * 50 + "╮", dim=True))
        click.echo("  " + "│ " + click.style("✓ WriteFile", fg='green') + f" Writing to {filename}")
        click.echo("  " + "│ ")
        for line in code.split('\n'):
            # Indent the code inside the box
            click.echo("  " + "│ " + click.style(f"  {line}", fg='yellow'))
        click.echo("  " + click.style("╰" + "─" * 50 + "╯", dim=True))
        click.echo()
        
        # Print the follow-up message
        follow_up = f"I've created a simple Python script named {click.style(filename, bold=True)} in the current directory. It will print \"Hello, World!\" when you run it."
        click.echo(" " + click.style("✦", fg="magenta") + f" {follow_up}")

    # Check if the agent is asking a question
    elif text.endswith("?"):
        click.echo(" " + click.style("✦", fg="magenta") + f" {text}")
    
    # Handle a standard text response
    else:
        # Print raw response if it contains complex formatting that our simple parser can't handle.
        # This makes it compatible with the original script's output.
        click.echo(text)


@click.command()
@click.option('--api-key', default=None, help='xAI API key. If not provided, uses XAI_API_KEY env var.')
@click.option('--dev', is_flag=True, help='Use cheaper OpenAI model for development (requires OPENAI_API_KEY)')
@click.option('--prompt', default=None, help='Prompt to run directly. If not provided, enters interactive mode.')
def main(api_key, dev, prompt):
    """A Grok-styled command-line interface."""
    os.system('clear')

    # --- Initialize Agent based on original script's logic ---
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
    
    # --- Startup Screen ---
    print_grok_art()

    click.echo("Tips for getting started:")
    click.echo("1. Ask questions, edit files, or run commands.")
    click.echo("2. Be specific for the best results.")
    click.echo("3. Create " + click.style("GROK.md", bold=True) + " files to customize your interactions with Grok.")
    click.echo("4. /help for more information.")
    click.echo()
    click.echo(click.style("Using 5 MCP servers (ctrl+t to view)", dim=True))
    click.echo()

    # --- Main Loop ---
    if prompt:
        # Handle non-interactive mode
        display_user_prompt(prompt)
        response = agent.chat(prompt)
        display_agent_response(response) # Format and display the response
        click.echo()
        print_status_bar()
    else:
        # Handle interactive mode
        # Initial status bar before first prompt
        print_status_bar()
        click.echo()
        while True:
            user_input = click.prompt("  >", prompt_suffix=" ")
            
            os.system('clear')
            print_grok_art()
            
            display_user_prompt(user_input)
            
            if user_input.lower() in ['exit', 'quit']:
                click.echo("Goodbye!")
                break
            
            response = agent.chat(user_input)
            display_agent_response(response) # Format and display the response
            click.echo()
            print_status_bar()
            click.echo()

if __name__ == '__main__':
    main()
