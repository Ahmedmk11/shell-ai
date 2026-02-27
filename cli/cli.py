import argparse
from pathlib import Path

from pyfiglet import Figlet
from rich.console import Console
from rich.panel import Panel

import shellingham
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from cli.utils.lexer import RunLexer

import subprocess

def get_shell():
    try:
        shell_name, shell_path = shellingham.detect_shell()
        return shell_name, shell_path
    except shellingham.ShellDetectionFailure:
        return "unknown", None

def print_header():
    print("\033[2J\033[H", end="")

    f = Figlet(font='big')
    console = Console()

    ascii_title = f.renderText('ShellAI').rstrip()
    console.print(Panel(f"[#2563EB]{ascii_title}", border_style="#1D4ED8"))

    console.print("\nType 'exit' to quit")
    console.print("[dim]AI prompt by default · Use [bold #2563EB]run[/] <cmd> for shell execution[/]\n")

def authenticate_github():
    # Placeholder for GitHub authentication logic
    pass

def main():
    parser = argparse.ArgumentParser(prog="shellai")

    parser.add_argument("--model", type=str, default="openai/gpt-oss-120b", help="Model to use")
    parser.add_argument("--temperature", type=float, default=0.15, help="Temperature for the model")
    parser.add_argument("--repo", type=str, default=".", help="Repository to use")
    parser.add_argument("--no_exec", action="store_true", help="Flag to disable execution")
    parser.add_argument("--github", action="store_false", help="Flag to enable GitHub authentication")

    args = parser.parse_args()

    print_header()

    session = PromptSession(lexer=RunLexer())
    style = Style.from_dict({
        "prompt": "ansicyan bold",
        "command": "ansiblue bold",
    })

    shell_name, shell_path = get_shell()

    if "powershell" in shell_name or "pwsh" in shell_name:
        shell_flag = "-Command"
    elif shell_name in ["bash", "zsh", "sh", "fish"]:
        shell_flag = "-c"
    elif shell_name == "cmd":
        shell_flag = "/c"
    else:
        shell_flag = "-c"

    while True:
        try:
            cwd = Path.cwd()

            user_input = session.prompt(
                HTML(f"<prompt>(ShellAI)</prompt> {shell_name} {cwd.as_posix()}> "),
                style=style
            )

            if user_input.lower() == "exit":
                print("\033[2J\033[H", end="")
                print("Exiting ShellAI. Goodbye!")
                break
            elif user_input.strip() == "":
                continue
            elif user_input.lower() == "clear":
                print_header()
            elif user_input.lower().split()[0] == "run":
                if not shell_path:
                    print("Could not detect shell.")
                    continue

                cmd = user_input[4:].strip()

                if cmd == "":
                    print("Please provide a command to run.")
                    continue

                parts = cmd.split(maxsplit=1)
                base = parts[0]

                try:
                    if base == "cd":
                        target = parts[1] if len(parts) > 1 else str(Path.home())

                        try:
                            new_path = (Path.cwd() / target).expanduser().resolve()
                            if not new_path.exists() or not new_path.is_dir():
                                print("Directory does not exist.")
                            else:
                                import os
                                os.chdir(new_path)
                        except Exception as e:
                            print(f"Invalid path: {e}")

                        continue

                    process = subprocess.Popen([shell_path, shell_flag, cmd])
                    process.wait()
                    continue
                except KeyboardInterrupt:
                    process.terminate()
                    print("\nProcess terminated.")

                except Exception as e:
                    print(f"Error running command: {e}")

            else:
                print(f"Running prompt: {user_input}")
        except KeyboardInterrupt:
            print("\033[2J\033[H", end="")
            print("Exiting ShellAI. Goodbye!")
            break

if __name__ == "__main__":
    main()
