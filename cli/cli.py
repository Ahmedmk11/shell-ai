import argparse
from pathlib import Path
import shellingham
import subprocess
import os
from dotenv import load_dotenv
from pyfiglet import Figlet

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.align import Align

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML

from cli.utils.lexer import RunLexer
from cli.agent import Agent
from cli.tools.run_command import RunCommandTool

from langgraph.errors import GraphRecursionError
from langchain_core.messages import AIMessageChunk

load_dotenv()

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

    console.print("\nType [bold #2563EB]'exit'[/] to quit")
    console.print("[dim]AI prompt by default · Use [bold #2563EB]run[/] <cmd> for shell execution[/]\n")

def authenticate_github():
    # Placeholder for GitHub authentication logic
    pass

def main():
    parser = argparse.ArgumentParser(prog="shellai")

    parser.add_argument("--temperature", type=float, default=0.15, help="Temperature for the model")
    parser.add_argument("--no-exec", action="store_true", help="Flag to disable execution")
    parser.add_argument("--no-path", action="store_true", help="Flag to hide file paths in CLI")
    parser.add_argument("--no-usage", action="store_true", help="Flag to disable usage tracking")

    parser.add_argument("--github", action="store_false", help="Flag to enable GitHub authentication")
    parser.add_argument("--repo", type=str, default=".", help="Repository to use")

    args = parser.parse_args()

    shell_name, shell_path = get_shell()

    if "powershell" in shell_name or "pwsh" in shell_name:
        shell_flag = "-Command"
    elif shell_name in ["bash", "zsh", "sh", "fish"]:
        shell_flag = "-c"
    elif  "cmd" in shell_name:
        shell_flag = "/c"
    else:
        shell_flag = "-c"

    agent = Agent(
        temperature=args.temperature,
        tools=[RunCommandTool(
            shell_path=shell_path,
            shell_flag=shell_flag,
            working_directory=os.getcwd()
        )],
        no_exec=args.no_exec,
        shell_path=shell_path,
        shell_flag=shell_flag,
    )

    prev_prompt_tokens = 0
    prev_completion_tokens = 0

    print_header()

    session = PromptSession(lexer=RunLexer())
    style = Style.from_dict({
        "prompt": "ansicyan bold",
        "command": "ansiblue bold",
    })

    while True:
        try:
            cwd = Path.cwd()
            displayed_path = cwd.as_posix() if not args.no_path else cwd.as_posix().split("/")[-1]

            user_input = session.prompt(
                HTML(f"<prompt>(ShellAI)</prompt> {shell_name} {displayed_path}> "),
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
                    if base == "cd" or base == "Set-Location":
                        target = parts[1] if len(parts) > 1 else str(Path.home())

                        try:
                            new_path = Path(target).expanduser().resolve()
                            if not new_path.exists() or not new_path.is_dir():
                                print("Directory does not exist.")
                            else:
                                os.chdir(new_path)
                        except Exception as e:
                            print(f"Invalid path: {e}")

                        continue

                    process = subprocess.run([shell_path, shell_flag, cmd])
                    continue
                except KeyboardInterrupt:
                    process.terminate()
                    print("\nProcess terminated.")

                except Exception as e:
                    print(f"Error running command: {e}")

            else:
                print()

                full_response = ""

                try:
                    console = Console()

                    with Live(console=console, refresh_per_second=15) as live:
                        for msg, metadata in agent.stream(user_input):
                            if (
                                isinstance(msg, AIMessageChunk)
                                and metadata.get("langgraph_node") == "reasoning"
                                and msg.content
                                and not msg.tool_call_chunks
                            ):
                                full_response += msg.content

                                live.update(
                                    Panel(
                                        Text(full_response),
                                        border_style="white",
                                        padding=(1, 2),
                                        expand=True,
                                        title="Agent",
                                        title_align="left"
                                    )
                                )

                    if not args.no_usage:
                        if agent.usage_callback.usage_metadata:
                            total_input = 0
                            total_output = 0
                            models = []

                            for model, usage in agent.usage_callback.usage_metadata.items():
                                total_input += usage.get("input_tokens", 0)
                                total_output += usage.get("output_tokens", 0)
                                models.append(model)

                            delta_input = total_input - prev_prompt_tokens
                            delta_output = total_output - prev_completion_tokens

                            prev_prompt_tokens = total_input
                            prev_completion_tokens = total_output

                            usage_text = (
                                f"{' · '.join(models)} · ↑ {delta_input} ↓ {delta_output} · "
                                f"{delta_input + delta_output} tok"
                            )

                            console.print(
                                Align.right(f"[dim]{usage_text}[/dim]")
                            )
                            
                except GraphRecursionError:
                    print("Error: The agent got stuck in a loop and was stopped.")
                except Exception as e:
                    print(f"Error: {e}")

                print()
        except KeyboardInterrupt:
            print("\033[2J\033[H", end="")
            print("Exiting ShellAI. Goodbye!")
            break

if __name__ == "__main__":
    main()
