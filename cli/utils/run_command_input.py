from pydantic import BaseModel, Field

class RunCommandInput(BaseModel):
    """Input for running shell commands."""
    command: str = Field(description="The command to execute")
