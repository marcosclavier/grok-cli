# Grok CLI

A command-line interface (CLI) tool designed to interact with xAI's Grok model via its API. This tool provides a seamless terminal-based experience for engaging with the Grok AI, allowing users to send prompts and receive responses directly within their command line.

## Features
- **Interactive Chat:** Engage in real-time conversations with the Grok AI.
- **Conversation History:** The CLI maintains conversation history, allowing for context-aware interactions.
- **Easy Setup:** Quick and straightforward installation and configuration.
- **Agentic Capabilities:** The Grok AI possesses agentic capabilities, enabling it to use tools for performing various tasks such as file operations directly from the conversation.

## Setup
1. **Obtain API Key:** Get your API key from the official xAI API portal: `https://x.ai/api`.
2. **Install Dependencies:** Navigate to the project root directory and install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
3. **Install CLI Tool:** Install the CLI tool in editable mode:
   ```bash
   pip install -e .
   ```

## Usage
To start the Grok CLI, run the following command, replacing `YOUR_API_KEY` with your actual xAI API key:

```bash
grok_cli --api-key YOUR_API_KEY
```

Once the CLI is running:
- Enter your prompts at the `You: ` prompt.
- Type `exit` to end the conversation and quit the application.

## Development
For developers, the editable installation (`pip install -e .`) allows for direct modifications to the source code without needing to reinstall the package. Changes to the `grok_cli` directory will be reflected immediately upon running the `grok_cli` command.