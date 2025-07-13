import click
import os
import subprocess
import sys
import json
import re

try:
    import termios
    import tty
except ImportError:
    pass  # For Windows, we'll use msvcrt

def _getch():
    """Cross-platform function to get a single character without pressing Enter."""
    if os.name == 'nt':  # Windows
        import msvcrt
        return msvcrt.getch().decode('utf-8')
    else:  # Unix-like
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

def custom_prompt():
    """Custom input prompt that handles keyboard shortcuts like ctrl+o and ctrl+t."""
    line = ""
    cycling = False
    cycle_matches = []
    cycle_index = -1
    last_partial = ""
    sys.stdout.write("  > ")
    sys.stdout.flush()
    while True:
        ch = _getch()
        if ch in ('\r', '\n'):  # Enter
            print()
            return line
        elif ch == '\x7f':  # Backspace
            if line:
                line = line[:-1]
                sys.stdout.write('\b \b')
                sys.stdout.flush()
        elif ch == '\x0f':  # Ctrl+O
            print("\nNo errors to display.")
            sys.stdout.write("  > " + line)
            sys.stdout.flush()
        elif ch == '\x14':  # Ctrl+T
            print("\nMCP Servers:\n- Server 1\n- Server 2\n- Server 3\n- Server 4\n- Server 5")
            sys.stdout.write("  > " + line)
            sys.stdout.flush()
        elif ch == '\t':  # Tab for autocomplete
            pos = line.rfind('@')
            if pos == -1 or (line.rfind(' ') > pos):
                cycling = False
                continue
            partial_path = line[pos+1:]
            if not partial_path:
                cycling = False
                continue
            dirname, basename = os.path.split(partial_path)
            if not dirname:
                dirname = '.'
            full_dir = os.path.expanduser(dirname) if dirname.startswith('~') else dirname
            try:
                files = os.listdir(full_dir)
                matches = [f for f in files if f.startswith(basename)]
                if not matches:
                    cycling = False
                    continue
                sorted_matches = sorted(matches)
                common = os.path.commonprefix(sorted_matches)
                completion = common[len(basename):]
                if completion:
                    line += completion
                    sys.stdout.write(completion)
                    sys.stdout.flush()
                    cycling = True
                    cycle_matches = sorted_matches
                    cycle_index = -1
                    last_partial = partial_path + completion
                else:
                    if not cycling or partial_path != last_partial:
                        cycling = True
                        cycle_matches = sorted_matches
                        cycle_index = -1
                        last_partial = partial_path
                    # Cycle to next
                    cycle_index = (cycle_index + 1) % len(cycle_matches)
                    chosen = cycle_matches[cycle_index]
                    new_partial = os.path.join(dirname, chosen)
                    if os.path.isdir(os.path.join(full_dir, chosen)):
                        new_partial += '/'
                    # Erase current partial
                    current_len = len(partial_path)
                    line = line[:-current_len]
                    sys.stdout.write('\b \b' * current_len)
                    # Add new
                    line += new_partial
                    sys.stdout.write(new_partial)
                    sys.stdout.flush()
                    # Update last
                    last_partial = new_partial
            except:
                cycling = False
                continue
        else:
            line += ch
            sys.stdout.write(ch)
            sys.stdout.flush()

from .agent import GrokAgent

def print_grok_art():
    """Prints the bold Grok CLI ASCII art."""
    art = """
  ██████╗ ██████╗  ██████╗ ██╗  ██╗    ██╗  ██╗     ██████╗██╗     ██╗
 ██╔════╝ ██╔══██╗██╔═══██╗██║ ██╔╝    ██║  ██║    ██╔════╝██║     ██║
 ██║  ███╗██████╔╝██║   ██║█████╔╝     ███████║    ██║     ██║     ██║
 ██║   ██║██╔══██╗██║   ██║██╔═██╗     ╚════██║    ██║     ██║     ██║
 ╚██████╔╝██║  ██║╚██████╔╝██║  ██╗         ██║    ╚██████╗███████╗██║
  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝         ╚═╝     ╚═════╝╚══════╝╚═╝
"""
    click.echo(click.style(art, fg='magenta'))

def print_status_bar(agent=None):
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
    
    # Context left calculation
    model_name = agent.model if agent else "grok-4"
    if agent and agent.last_token_usage.get("total_tokens", 0) > 0:
        used_tokens = agent.last_token_usage["total_tokens"]
        percent_left = max(0, (agent.context_window - used_tokens) / agent.context_window * 100)
        context_left = f"{model_name} ({int(percent_left)}% context left)"
    else:
        context_left = f"{model_name} (100% context left)"  # Initial or fallback
    
    model_info = click.style(context_left, fg="cyan")
    
    # Error count
    error_count = agent.last_error_count if agent else 0
    errors_info = click.style(f"X {error_count} errors (ctrl+o for details)", fg="red")

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
    try:
        # Attempt to parse the text as JSON
        response_json = json.loads(text)

        if "error" in response_json:
            # Handle structured error messages from tools
            click.echo("  " + click.style("╭" + "─" * 50 + "╮", dim=True))
            click.echo("  " + "│ " + click.style("✖ Tool Error", fg='red'))
            click.echo("  " + "│ ")
            click.echo("  " + "│ " + click.style(f"  {response_json['error']}", fg='red'))
            click.echo("  " + click.style("╰" + "─" * 50 + "╯", dim=True))
            click.echo()
        elif "files" in response_json:
            # Handle list_files output
            click.echo("  " + click.style("╭" + "─" * 50 + "╮", dim=True))
            click.echo("  " + "│ " + click.style("📁 Files Listed", fg='green'))
            click.echo("  " + "│ ")
            for f in response_json["files"]:
                click.echo("  " + "│ " + click.style(f"  - {f}", fg='cyan'))
            click.echo("  " + click.style("╰" + "─" * 50 + "╯", dim=True))
            click.echo()
        elif "content" in response_json:
            # Handle read_file output
            click.echo("  " + click.style("╭" + "─" * 50 + "╮", dim=True))
            click.echo("  " + "│ " + click.style("📄 File Content", fg='green'))
            click.echo("  " + "│ ")
            for line in response_json["content"].split('\n'):                click.echo("  " + "│ " + click.style(f"  {line}", fg='yellow'))
            click.echo("  " + click.style("╰" + "─" * 50 + "╯", dim=True))
            click.echo()
        elif "status" in response_json and response_json["status"] == "success":
            # Handle successful edit_file output
            click.echo("  " + click.style("╭" + "─" * 50 + "╮", dim=True))
            click.echo("  " + "│ " + click.style("✔ File Edited", fg='green'))
            click.echo("  " + "│ ")
            click.echo("  " + "│ " + click.style(f"  Path: {response_json.get('file_path', 'N/A')}", fg='cyan'))
            click.echo("  " + "│ " + click.style(f"  Operation: {response_json.get('operation', 'N/A')}", fg='cyan'))
            
            old_snippet = response_json.get('old_content_snippet')
            new_snippet = response_json.get('new_content_snippet')

            if old_snippet:
                click.echo("  " + "│ " + click.style("  Old Content Snippet:", fg='yellow'))
                for line in old_snippet.split('\n'):
                    click.echo("  " + "│ " + click.style(f"    {line}", fg='yellow'))
            if new_snippet:
                click.echo("  " + "│ " + click.style("  New Content Snippet:", fg='yellow'))
                for line in new_snippet.split('\n'):
                    click.echo("  " + "│ " + click.style(f"    {line}", fg='yellow'))

            click.echo("  " + click.style("╰" + "─" * 50 + "╯", dim=True))
            click.echo()
        elif "verification" in response_json and response_json["verification"] == "success":
            click.echo("  " + click.style("╭" + "─" * 50 + "╮", dim=True))
            click.echo("  " + "│ " + click.style("✔ Verification Successful", fg='green'))
            click.echo("  " + click.style("╰" + "─" * 50 + "╯", dim=True))
            click.echo()
        else:
            # Fallback for other JSON structures or if not recognized
            click.echo(text)
    except json.JSONDecodeError:
        # If not valid JSON, check for the special "WriteFile" command from the agent
        if text.startswith("WriteFile:"):
            parts = text.split('\n', 1)
            header = parts[0]
            code = parts[1] if len(parts) > 1 else ""
            filename = header.split(':', 1)[1].strip()

            # Print the green "WriteFile" block
            click.echo("  " + click.style("╭" + "─" * 50 + "╮", dim=True))
            click.echo("  " + "│ " + click.style("✔ WriteFile", fg='green') + f" Writing to {filename}")
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
        agent = GrokAgent(api_key=openai_key, model="gpt-3.5-turbo", base_url="https://api.openai.com/v1", summarize_memory=True)
        print("🚧 DEVELOPMENT MODE: Using OpenAI gpt-3.5-turbo (cheaper)")
    else:
        # Production mode with Grok
        api_key = api_key or os.getenv('XAI_API_KEY')
        if not api_key:
            raise click.UsageError("API key is required. Provide via --api-key or XAI_API_KEY environment variable. Get it from https://x.ai/api.")
        agent = GrokAgent(api_key=api_key, summarize_memory=True)
    
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
        print_status_bar(agent)
    else:
        # Handle interactive mode
        # Initial status bar before first prompt
        print_status_bar()
        click.echo()
        while True:
            try:
                user_input = custom_prompt()
                
                os.system('clear')
                print_grok_art()
                
                display_user_prompt(user_input)
                
                # Preprocess for @ attachments
                enhanced_message = user_input
                attachments = ""
                matches = re.findall(r'@(\S+)', user_input)
                for path in set(matches):
                    full_path = os.path.expanduser(path)
                    if os.path.isfile(full_path):
                        try:
                            with open(full_path, 'r') as f:
                                content = f.read()
                            enhanced_message = enhanced_message.replace(f'@{path}', f'[attached file: {path}]')
                            attachments += f"\n\nAttached file '{path}':\n```\n{content}\n```"
                        except Exception as e:
                            enhanced_message = enhanced_message.replace(f'@{path}', f'[error attaching {path}: {str(e)}]')
                    elif os.path.isdir(full_path):
                        try:
                            files = os.listdir(full_path)
                            enhanced_message = enhanced_message.replace(f'@{path}', f'[attached dir: {path}]')
                            attachments += f"\n\nAttached directory '{path}' listing:\n" + "\n".join(f" - {f}" for f in files)
                        except Exception as e:
                            enhanced_message = enhanced_message.replace(f'@{path}', f'[error attaching {path}: {str(e)}]')
                enhanced_message += attachments
                
                if user_input.lower() in ['exit', 'quit']:
                    click.echo("Goodbye!")
                    break
                
                response = agent.chat(enhanced_message)
                display_agent_response(response) # Format and display the response
                click.echo()
                print_status_bar(agent)
                click.echo()
            except KeyboardInterrupt:
                click.echo("\nGoodbye!")
                break

if __name__ == '__main__':
    main()