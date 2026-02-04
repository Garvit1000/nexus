# Jarvis Assistant

A Linux assistant that lives in your terminal.

## Prerequisites

- Python 3.10 or higher

## Installation

1. Clone the repository (if you haven't already):
   ```bash
   git clone <repository-url>
   cd linux-agent
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install the package in editable mode (recommended for development):
   ```bash
   pip install -e .
   ```

4. Configure the AI:
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Gemini API key:
   ```bash
   # Open .env and set JARVIS_API_KEY
   ```

## Usage

Once installed, you can run the assistant using the `jarvis` command:

```bash
jarvis --help
```

### Current Capabilities

- **AI Chat**: Chat with a helpful Linux assistant (`jarvis chat`).
- **Package Management**: Install, remove, and update packages from system repositories (`jarvis install`, `jarvis remove`, `jarvis update`).
  - *Supported*: `apt`, `dnf`, `pacman`.
  - *Note*: Does not yet support direct `.deb` file installation (planned).
- **Natural Language Actions**: Execute complex system tasks using plain English (`jarvis do "find all python files"`).
- **System Info**: View basic OS and package manager details (`jarvis info`).

### Examples

```bash
# Chat
jarvis chat "How do I check disk space?"

# Install a package
jarvis install htop

# Execute a command via AI
jarvis do "List all files larger than 100MB in /var"
```
