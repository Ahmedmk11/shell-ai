import json
import platform

from langchain.chat_models import init_chat_model
import os

from langgraph.graph import START, StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from state import AgentState
from utils.tool_result import ToolResult

class LLMClient:
    def __init__(self, temperature: float = 0.15, tools: list | None = None) -> None:
        self.llm = init_chat_model(
            model=os.getenv("GROQ_MODEL"),
            temperature=temperature,
        ).bind_tools(tools if tools else [])

class Agent:
    def __init__(self, temperature: float = 0.15, tools: list | None = None, no_exec: bool = False, shell_path: str = "", shell_flag: str = "") -> None:
        self.tools = tools if tools else []
        self.no_exec = no_exec

        if not shell_path:
            if platform.system() == "Windows":
                shell_path = "C:\\Windows\\System32\\cmd.exe"
                shell_flag = "/c"
            else:
                shell_path = "/bin/bash"
                shell_flag = "-c"

        if not shell_flag:
            raise ValueError("shell_flag is required")

        self.shell_path = shell_path
        self.shell_flag = shell_flag
        self.llm = LLMClient(temperature, self.tools)
        self.graph = self._build_graph()
        self.system_prompt = f"""You are a helpful CLI assistant that executes shell commands.

        EXECUTION ENVIRONMENT
        Shell: {shell_path}
        Flag: {shell_flag}
        Only use syntax compatible with {shell_path}.

        TOOL RESPONSE FORMAT
        Responses are JSON with:
        - guardrail (string): "" = success, "block" = invalid, "partial" = dangerous, "no-exec" = read-only
        - success (bool): Whether command succeeded
        - result (string): Command output
        - error (string): Error messages
        - new_working_directory (string or null): Updated working directory if changed, otherwise null

        HANDLING BLOCKED COMMANDS
        - guardrail="block": Tool call was invalid. Do NOT retry. Suggest an alternative.
        - guardrail="partial": Command is dangerous. Do NOT execute NOR retry. Show the user the exact command to run manually with context.
        - guardrail="no-exec": Read-only mode. Do NOT execute. Show the user the exact command with context.

        BEST PRACTICES
        - Always explain what a command does
        - Provide context on why commands are necessary
        """

    def invoke(self, user_input: str, max_iterations: int = 8):
        state = {
            "messages": [HumanMessage(content=user_input)],
            "working_directory": os.getcwd()
        }
        config = {"recursion_limit": max_iterations}
        return self.graph.invoke(state, config)

    def stream(self, user_input: str, max_iterations: int = 8):
        state = {
            "messages": [HumanMessage(content=user_input)],
            "working_directory": os.getcwd()
        }
        config = {"recursion_limit": max_iterations}
        
        for update in self.graph.stream(state, config, stream_mode="updates"):
            yield update

    def _build_graph(self):
        def reasoning_node(state: AgentState) -> AgentState:
            messages = [
                SystemMessage(content=self.system_prompt),
                *state["messages"]
            ]

            response = self.llm.llm.invoke(messages)

            return {
                "messages": state["messages"] + [response],
                "working_directory": state["working_directory"]
            }

        def tool_guardrail_node(state: AgentState) -> AgentState:
            last_message = state["messages"][-1]
            guardrail_errors = []
            destructive_words = [
                    # unix
                    "rm",
                    "dd",
                    "mkfs",
                    "shred",
                    "shutdown",
                    "reboot",
                    "halt",
                    "poweroff",
                    "sudo",
                    "su",

                    # cmd
                    "del",
                    "rmdir",
                    "rd",
                    "format",
                    "diskpart",
                    "takeown",

                    # ps
                    "Remove-Item",
                    "Clear-Disk",
                    "Format-Volume",
                    "Stop-Computer",
                    "Restart-Computer",
                    "Invoke-Expression",
                    "iex",

                    # flags
                    "-r",
                    "-rf",
                    "/s",
                    "-Recurse",
                    "*",

                    # remote
                    "curl",
                    "wget",
                    "New-Object Net.WebClient",
                ]

            # did the llm decide to call a tool in the first place?
            if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
                return state
            
            for tool_call in last_message.tool_calls:

                # does the tool exist?
                if not any(t.name == tool_call.name for t in self.tools):
                    guardrail_errors.append(
                        ToolMessage(
                            content=ToolResult(
                                guardrail="block",
                                success=False,
                                result="",
                                error="(Guardrail) Tool doesn't exist",
                                new_working_directory=None
                            ).model_dump_json(),
                            tool_call_id=tool_call.id
                        )
                    )
                    continue

                # are the arguments valid?
                if tool_call.name == "run_command":
                    command = tool_call.args.get("command")

                    if not command:
                        guardrail_errors.append(
                            ToolMessage(
                                content=ToolResult(
                                    guardrail="block",
                                    success=False,
                                    result="",
                                    error="(Guardrail) Missing required argument: command",
                                    new_working_directory=None
                                ).model_dump_json(),
                                tool_call_id=tool_call.id
                            )
                        )
                        continue
                    
                # is there a --no-exec flag?
                if tool_call.name == "run_command" and self.no_exec:
                    guardrail_errors.append(ToolMessage(
                        content=ToolResult(
                            guardrail="no-exec",
                            success=False,
                            result="",
                            error="(Guardrail) Execution blocked: --no-exec flag is enabled.",
                            new_working_directory=None
                        ).model_dump_json(),
                        tool_call_id=tool_call.id
                    ))
                    continue

                # is it a destructive command?
                command = tool_call.args.get("command", "").lower()

                if tool_call.name == "run_command" and any(word in command for word in destructive_words):
                    guardrail_errors.append(ToolMessage(
                        content=ToolResult(
                            guardrail="partial",
                            success=False,
                            result="",
                            error="(Guardrail) Execution blocked: The command is potentially destructive.",
                            new_working_directory=None
                        ).model_dump_json(),
                        tool_call_id=tool_call.id
                    ))
                    continue

            if guardrail_errors:
                return {
                    "messages": state["messages"] + guardrail_errors, 
                    "working_directory": state["working_directory"]
                }

            return state

        def should_continue(state: AgentState):
            last_message = state["messages"][-1]

            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tool"

            if isinstance(last_message, ToolMessage):
                return "reasoning"

            return END

        def tool_node(state: AgentState):
            tool_results = []
            new_working_directory = state.get("working_directory")

            last_message = state["messages"][-1]

            tools_by_name = {tool.name: tool for tool in self.tools}

            for tool_call in last_message.tool_calls:
                tool = tools_by_name.get(tool_call.name)

                try:
                    result = tool.invoke({
                        "command": tool_call.args.get("command"),
                        "shell_path": self.shell_path,
                        "shell_flag": self.shell_flag,
                        "working_directory": state.get("working_directory"),
                    })

                    response = json.loads(result.model_dump_json())

                    if response.get("new_working_directory"):
                        new_working_directory = response["new_working_directory"]

                    tool_results.append(ToolMessage(
                        content=result.model_dump_json(),
                        tool_call_id=tool_call.id
                    ))
                except Exception as e:
                    tool_results.append(ToolMessage(
                        content=ToolResult(
                            guardrail="",
                            success=False,
                            result="",
                            error=str(e),
                            new_working_directory=None
                        ).model_dump_json(),
                        tool_call_id=tool_call.id
                    ))

            return {
                "messages": state["messages"] + tool_results,
                "working_directory": new_working_directory
            }

        graph = StateGraph(AgentState)
        
        graph.add_node("reasoning", reasoning_node)
        graph.add_node("tool_guardrail", tool_guardrail_node)
        graph.add_node("tool", tool_node)

        graph.add_edge(START, "reasoning")
        graph.add_edge("reasoning", "tool_guardrail")
        graph.add_conditional_edges("tool_guardrail", should_continue)
        graph.add_edge("tool", "reasoning")

        return graph.compile()
