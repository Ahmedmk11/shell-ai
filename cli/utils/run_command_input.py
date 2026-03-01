from pydantic import BaseModel, Field

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
