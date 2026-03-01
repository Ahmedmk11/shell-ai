import shlex
from langchain.tools import tool
from pydantic import BaseModel, Field

import subprocess
from pathlib import Path
import os
from utils.tool_result import ToolResult

class RunCommandInput(BaseModel):
    """Input for running shell commands."""
    command: str = Field(description="The command to execute")
    shell_flag: str = Field(
        description="The shell flag to use (e.g., -c for bash, -Command for powershell)"
    )
    shell_path: str = Field(
        description="full path to the shell binary (e.g., /bin/bash or /opt/homebrew/bin/zsh)"
    )
    working_directory: str = Field(
        description="The working directory to run the command in"
    )

@tool(args_schema=RunCommandInput)
def run_command(command: str, shell_flag: str, shell_path: str, working_directory: str) -> ToolResult:
    """Runs a command in the shell and returns the output.

    Args:
        command: The command to run.
        shell_path: The path to the shell executable.
        shell_flag: The flag to use for running a command in the shell.
        working_directory: The working directory to run the command in.
    """

    if not command.strip():
        return ToolResult(
            guardrail="",
            success=False,
            result="",
            error="No command provided",
            new_working_directory=None
        )
    
    tokens = shlex.split(command)
    base = tokens[0] if tokens else ""

    try:
        if base == "cd":
            target = tokens[1] if len(tokens) > 1 else str(Path.home())

            try:
                new_path = Path(target).expanduser().resolve()
                if not new_path.exists() or not new_path.is_dir():
                    return ToolResult(
                        guardrail="",
                        success=False,
                        result="",
                        error="Path doesn't exist",
                        new_working_directory=None
                    )
                else:
                    os.chdir(new_path)
                    return ToolResult(
                        guardrail="",
                        success=True,
                        result=f"Changed directory to {new_path}",
                        error="",
                        new_working_directory=str(new_path)
                    )
            except Exception as e:
                return ToolResult(
                    guardrail="",
                    success=False,
                    result="",
                    error="Invalid path: " + str(e),
                    new_working_directory=None
                )
        else:
            try:
                result = subprocess.run(
                    [shell_path, shell_flag, command],
                    capture_output=True,
                    text=True,
                    cwd=working_directory,
                    timeout=15
                )

                return ToolResult(
                    guardrail="",
                    success=result.returncode == 0,
                    result=result.stdout.strip(),
                    error=result.stderr.strip(),
                    new_working_directory=None
                )

            except subprocess.TimeoutExpired as e:
                return ToolResult(
                    guardrail="",
                    success=False,
                    result="",
                    error="Command timed out after 15 seconds",
                    new_working_directory=None
                )
    except Exception as e:
        return ToolResult(
            guardrail="",
            success=False,
            result="",
            error=str(e),
            new_working_directory=None
        )
