from langchain.tools import tool

from pydantic import BaseModel

import subprocess
import sys
from pathlib import Path
import os

class CommandResult(BaseModel):
    success: bool
    result: str
    error: str

@tool
def run_command(command: str, shell_path: str, shell_flag: str) -> CommandResult:
    """Runs a command in the shell and returns the output.

    Args:
        command: The command to run.
        shell_path: The path to the shell executable.
        shell_flag: The flag to use for running a command in the shell.
    """

    if not command.strip():
        return CommandResult(
            success=False,
            result="",
            error="No command provided",
        )
    
    parts = command.split(maxsplit=1)
    base = parts[0]

    try:
        if base == "cd":
            target = parts[1] if len(parts) > 1 else str(Path.home())

            try:
                new_path = Path(target).expanduser().resolve()
                if not new_path.exists() or not new_path.is_dir():
                    return CommandResult(
                        success=False,
                        result="",
                        error="Path doesn't exist",
                    )
                else:
                    os.chdir(new_path)
                    return CommandResult(
                        success=True,
                        result=f"Changed directory to {new_path}",
                        error="",
                    )
            except Exception as e:
                return CommandResult(
                    success=False,
                    result="",
                    error="Invalid path: " + str(e),
                )
        else:
            result = subprocess.run(
                [shell_path, shell_flag, command],
                capture_output=True,
                text=True
            )

            return CommandResult(
                success=result.returncode == 0,
                result=result.stdout.strip(),
                error=result.stderr.strip(),
            )
    except Exception as e:
        return CommandResult(
            success=False,
            result="",
            error=str(e),
        )
