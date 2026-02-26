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

def get_shell():
    try:
        shell_name, _ = shellingham.detect_shell()
        return shell_name
    except shellingham.ShellDetectionFailure:
        return "unknown"

def print_header():
    print("\033[2J\033[H", end="")

    f = Figlet(font='big')
    console = Console()

    ascii_title = f.renderText('ShellAI').rstrip()
    console.print(Panel(f"[#2563EB]{ascii_title}", border_style="#1D4ED8"))

    console.print("\nType 'exit' to quit")
    console.print("[dim]AI prompt by default · Use [bold #2563EB]run[/] <cmd> for shell execution[/]\n")

def main():
    parser = argparse.ArgumentParser(prog="shellai")

    parser.add_argument("--model", type=str, default="openai/gpt-oss-120b", help="Model to use")
    parser.add_argument("--temperature", type=float, default=0.15, help="Temperature for the model")
    parser.add_argument("--repo", type=str, default=".", help="Repository to use")
    parser.add_argument("--no_exec", action="store_true", help="Flag to disable execution")

    args = parser.parse_args()

    print_header()

    session = PromptSession(lexer=RunLexer())
    style = Style.from_dict({
        "prompt": "ansicyan bold",
        "command": "ansiblue bold",
    })

    while True:
        try:
            cwd = Path.cwd()
            user_input = session.prompt(
                HTML(f"<prompt>(ShellAI)</prompt> {get_shell()} {cwd.as_posix()}> "),
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
                print(f"Running command: {user_input}")
            else:
                print(f"Running prompt: {user_input}")
        except KeyboardInterrupt:
            print("\033[2J\033[H", end="")
            print("Exiting ShellAI. Goodbye!")
            break

if __name__ == "__main__":
    main()
