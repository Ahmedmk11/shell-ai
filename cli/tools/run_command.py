import shlex

import subprocess
from pathlib import Path
import os

from langchain.tools import BaseTool

from cli.utils.tool_result import ToolResult
from cli.utils.run_command_input import RunCommandInput

class RunCommandTool(BaseTool):
    name: str = "run_command"
    description: str = "Runs a command in the shell and returns the output."
    args_schema: type = RunCommandInput

    shell_path: str
    shell_flag: str
    working_directory: str

    def _run(self, command: str) -> ToolResult:
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
            if base == "cd" or base == "Set-Location":
                target = tokens[1] if len(tokens) > 1 else str(Path.home())

                try:
                    if Path(target).is_absolute():
                        new_path = Path(target).expanduser().resolve()
                    else:
                        new_path = (Path(self.working_directory) / target).expanduser().resolve()

                    if not new_path.exists() or not new_path.is_dir():
                        return ToolResult(
                            guardrail="",
                            success=False,
                            result="",
                            error="Path doesn't exist",
                            new_working_directory=None
                        )
                    else:
                        return ToolResult(
                            guardrail="",
                            success=True,
                            result="",
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
                        [self.shell_path, self.shell_flag, command],
                        capture_output=True,
                        text=True,
                        cwd=self.working_directory,
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
