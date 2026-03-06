# ShellAI

An AI-powered CLI agent that lives in your terminal. Ask it questions or have it run shell commands on your behalf.

![Python](https://img.shields.io/badge/python-3.13+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Table of Contents

- [Screenshots](#screenshots)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Options](#options)
- [Example](#example)

---

## Screenshots

### Agent Capabilities Overview

![Startup](https://github.com/user-attachments/assets/0b2ebbf4-5a0e-4fc9-9d13-b9177dc0055c)

### Automatic Git Commit and Push

![Commands](https://github.com/user-attachments/assets/3e70c07a-3267-4e7f-868a-a65a079dcdef)

### File System Commands & Safety Guardrails

![PR](https://github.com/user-attachments/assets/65899ea8-287c-4c82-a474-5826244cb175)

### MCP tool calls: PR Request & Issue Creation

![Issue](https://github.com/user-attachments/assets/27be0354-48db-4836-bc95-d2b414e034dc)

---

## Prerequisites

- Python 3.13+
- An Anthropic API key

---

## Installation

```bash
# macOS / Linux
git clone https://github.com/Ahmedmk11/shell-ai.git
cd shell-ai
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Windows (PowerShell)
git clone https://github.com/Ahmedmk11/shell-ai.git
cd shell-ai
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

---

## Configuration

Export your credentials before running:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
export ANTHROPIC_MODEL=claude-opus-4-5
```

To avoid doing this every session, add them to your `~/.bashrc` or `~/.zshrc`.
or create a `.env` file in the project root with the following content:

```
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_MODEL=claude-opus-4-5
```

---

## Usage

```bash
shellai
```

```bash
shellai --no-exec --no-usage
```

### Options

| Flag            | Description                                        |
| --------------- | -------------------------------------------------- |
| `--temperature` | Model temperature (default: `0`)                   |
| `--no-exec`     | Disable command execution                          |
| `--no-path`     | Show only current folder name instead of full path |
| `--no-usage`    | Hide token usage stats                             |

---

## Example

```
(ShellAI) bash ~/projects/shell-ai> how many python files are in this project?
(ShellAI) bash ~/projects/shell-ai> run git status
(ShellAI) bash ~/projects/shell-ai> clear
(ShellAI) bash ~/projects/shell-ai> exit
```

Type naturally to talk to the AI, or prefix with `run` to execute shell commands directly, bypassing the AI entirely. The agent will always show you the exact command it ran and its output.
