from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    guardrail: str = Field(default="", description="Indicates if the result was blocked or partially blocked by guardrails")
    success: bool = Field(description="Whether the tool executed successfully")
    result: str = Field(default="", description="The EXACT output/stdout from the tool")
    error: str = Field(default="", description="Any error or stderr from the tool")
    new_working_directory: str | None = Field(default=None, description="The new working directory if the tool changes it")
