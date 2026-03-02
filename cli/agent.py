import os
import json
import platform

import textwrap
from uuid import uuid4

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.callbacks import UsageMetadataCallbackHandler

from cli.state import AgentState
from cli.utils.debug_logger import append_llm_input
from cli.utils.tool_result import ToolResult

def get_env_model():
    model = os.getenv("GROQ_MODEL")
    if not model:
        raise ValueError("Model is not set")
    return model

class LLMClient:
    def __init__(self, temperature: float = 0.15, tools: list | None = None) -> None:
        self.llm = init_chat_model(
            model=get_env_model(),
            temperature=temperature,
        ).bind_tools(tools if tools else [])

class Agent:
    def __init__(self, temperature: float = 0.15, tools: list | None = None, no_exec: bool = False, shell_path: str = "", shell_flag: str = "") -> None:
        self.usage_callback = UsageMetadataCallbackHandler()
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

        self.thread_id = str(uuid4())
        self.memory = MemorySaver()

        self.llm = LLMClient(temperature, self.tools)
        self.graph = self._build_graph()

        self.system_prompt = textwrap.dedent(f"""You are a CLI agent. You reason, execute shell commands when needed, and respond to the user.

        ENVIRONMENT
        Shell: {shell_path} (flag: {shell_flag})
        Only use syntax compatible with {shell_path}.

        REASONING RULES
        - Execute a command ONLY if the user explicitly asks OR it is strictly required to answer
        - Never execute speculatively or to "check" things
        - Never call run_command more than once per response
        - One command at a time, no chaining (no ; && ||)
        - If no command is needed, respond directly in FORMAT B

        TOOL
        - run_command: runs a shell command and returns output
        - If you call a tool, output NO text content whatsoever. ONLY the tool call
        - Never combine a text response with a tool call in the same message
        - Text response and tool calls are mutually exclusive

        AFTER TOOL EXECUTION
        - After receiving any tool result (success or error), do NOT call another tool
        - Respond immediately using FORMAT A

        BLOCKED COMMANDS
        - If a guardrail blocks your command, do NOT retry
        - Respond with FORMAT A: Command is what you attempted, Result is failure, Output is the guardrail error

        RESPONSE FORMAT — use exactly one, no deviations, no extra lines

        FORMAT A — a command ran or was blocked:
        <brief message>
        Command: <command>
        Result: <success|failure>
        Output:

            <full tool output or guardrail error indented by 4 spaces>
        Rules: exactly 6 lines, no blank lines, lines 2-4 must start exactly with Command: / Result: / Output:, line 5 is blank and line 6 is the start of the output content

        FORMAT B — no command ran:
        <brief message>
        Rules: exactly 1 line, no Command:/Result:/Output: fields
        """).strip()

    def stream(self, user_input: str, max_iterations: int = 8):
        state = {
            "messages": [HumanMessage(content=user_input)],
            "working_directory": os.getcwd()
        }
        config = {
            "recursion_limit": max_iterations,
            "configurable": {"thread_id": self.thread_id},
            "callbacks": [self.usage_callback]
        }
        
        for msg, metadata in self.graph.stream(state, config, stream_mode="messages"):
            yield msg, metadata

    def _build_graph(self):
        def reasoning_node(state: AgentState) -> AgentState:
            messages = [
                SystemMessage(content=self.system_prompt + f"\nCurrent working directory: {state['working_directory']}"),
                *state["messages"]
            ]

            append_llm_input("reasoning_node", messages)
            response = self.llm.llm.invoke(messages)

            return {
                "messages": [response],
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
                if not any(t.name == tool_call["name"] for t in self.tools):
                    guardrail_errors.append(
                        ToolMessage(
                            content=ToolResult(
                                guardrail="block",
                                success=False,
                                result="",
                                error="(Guardrail) Tool doesn't exist",
                                new_working_directory=None
                            ).model_dump_json(),
                            tool_call_id=tool_call["id"]
                        )
                    )
                    continue

                if tool_call["name"] == "run_command":
                    command = tool_call["args"].get("command", "")

                    # are the arguments valid?
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
                                tool_call_id=tool_call["id"]
                            )
                        )
                        continue
                    
                    # is there a --no-exec flag?
                    if self.no_exec:
                        guardrail_errors.append(ToolMessage(
                            content=ToolResult(
                                guardrail="no-exec",
                                success=False,
                                result="",
                                error="(Guardrail) Execution blocked: --no-exec flag is enabled.",
                                new_working_directory=None
                            ).model_dump_json(),
                            tool_call_id=tool_call["id"]
                        ))
                        continue

                    # does the command contain chained operators?
                    if any(op in command for op in [";", "&&", "||"]):
                        guardrail_errors.append(ToolMessage(
                            content=ToolResult(
                                guardrail="block",
                                success=False,
                                result="",
                                error="(Guardrail) Chained commands are not allowed. Run one command at a time.",
                                new_working_directory=None
                            ).model_dump_json(),
                            tool_call_id=tool_call["id"]
                        ))
                        continue

                    # is it a destructive command?
                    command = tool_call["args"].get("command", "").lower()
                    if any(word in command for word in destructive_words):
                        guardrail_errors.append(ToolMessage(
                            content=ToolResult(
                                guardrail="partial",
                                success=False,
                                result="",
                                error="(Guardrail) Execution blocked: The command is potentially destructive.",
                                new_working_directory=None
                            ).model_dump_json(),
                            tool_call_id=tool_call["id"]
                        ))
                        continue

            if guardrail_errors:
                return {
                    "messages": guardrail_errors, 
                    "working_directory": state["working_directory"]
                }

            return state

        def should_continue(state: AgentState):
            last_message = state["messages"][-1]

            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tool_guardrail"

            if isinstance(last_message, ToolMessage):
                return "reasoning"

            if isinstance(last_message, AIMessage):
                return END

            return END
        
        def after_guardrail(state: AgentState):
            last_message = state["messages"][-1]
            if isinstance(last_message, ToolMessage):
                return "reasoning"
            return "tool"

        def tool_node(state: AgentState):
            tool_results = []
            new_working_directory = state.get("working_directory")

            last_message = state["messages"][-1]

            tools_by_name = {tool.name: tool for tool in self.tools}

            for tool_call in last_message.tool_calls:
                tool = tools_by_name.get(tool_call["name"])

                try:
                    tool.working_directory = state.get("working_directory")
                    result = tool.invoke({
                        "command": tool_call["args"].get("command"),
                    })

                    response = json.loads(result.model_dump_json())

                    if response.get("new_working_directory"):
                        new_working_directory = response["new_working_directory"]

                    tool_results.append(ToolMessage(
                        content=result.model_dump_json(),
                        tool_call_id=tool_call["id"]
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
                        tool_call_id=tool_call["id"]
                    ))

            return {
                "messages": tool_results,
                "working_directory": new_working_directory
            }

        graph = StateGraph(AgentState)
        
        graph.add_node("reasoning", reasoning_node)
        graph.add_node("tool_guardrail", tool_guardrail_node)
        graph.add_node("tool", tool_node)

        graph.add_edge(START, "reasoning")
        graph.add_conditional_edges("reasoning", should_continue)
        graph.add_conditional_edges("tool_guardrail", after_guardrail)
        graph.add_conditional_edges("tool", should_continue)

        return graph.compile(checkpointer=self.memory)
