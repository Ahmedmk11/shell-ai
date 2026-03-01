import os
import json
import platform

from uuid import uuid4

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.callbacks import UsageMetadataCallbackHandler

from cli.state import AgentState
from cli.utils.tool_result import ToolResult

class LLMClient:
    def __init__(self, temperature: float = 0.15, tools: list | None = None) -> None:
        self.llm = init_chat_model(
            model=os.getenv("GROQ_MODEL"),
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

        self.system_prompt = f"""You are a CLI reasoning agent that decides which shell commands to execute.

        EXECUTION ENVIRONMENT
        Shell: {shell_path}
        Flag: {shell_flag}

        Only use syntax compatible with {shell_path}.

        REASONING RULES
        - Execute a command ONLY if the user directly asks for it OR if it's essential to answer their question
        - Do NOT execute commands speculatively or to "check" things
        - Do NOT chain commands, only one command at a time
        - If the user asks a question (not a command), answer without running anything
        - NEVER execute commands without being asked

        AVAILABLE TOOL
        - run_command: Runs a command in the shell and returns the output.

        TOOL RESPONSE FORMAT
        Responses are JSON with:
        - guardrail (string): "" = success, "block" = invalid, "partial" = dangerous, "no-exec" = read-only
        - success (bool): Whether command succeeded
        - result (string): Command output
        - error (string): Error messages
        - new_working_directory (string or null): Updated working directory if changed, otherwise null

        HANDLING BLOCKED COMMANDS
        - guardrail="block": Do NOT retry. Pass the error to the responder.
        - guardrail="partial": Do NOT execute NOR retry. Pass to responder.
        - guardrail="no-exec": Do NOT execute. Pass to responder.
        """

        self.responder_prompt = """
        You are a CLI assistant that communicates results to the user.

        You will receive conversation history that may include tool execution results.

        You MUST output EXACTLY one of the two formats below.
        The structure and line breaks are mandatory.

        ========================
        FORMAT A (if a tool ran or was blocked)
        ========================

        <message>
        Command: <command>
        Result: <success|failure>
        Output: <tool output>

        Rules for FORMAT A:
        - The response must contain exactly four lines.
        - Line 1 is a brief friendly message to the user.
        - Line 2 must start exactly with: Command:
        - Line 3 must start exactly with: Result:
        - Line 4 must start exactly with: Output:
        - Each of the four fields must be on its own line.
        - Do not merge multiple fields onto one line.
        - Do not add blank lines.
        - Do not add extra commentary before or after.
        - Do not indent any lines.

        ========================
        FORMAT B (if no tool ran)
        ========================

        <message>

        Rules for FORMAT B:
        - The response must contain exactly one line.
        - Do not add additional lines.
        - Do not include Command:, Result:, or Output:.
        - Keep the message brief.

        Decision Rules:
        - Use FORMAT A only if a command was executed or blocked.
        - Use FORMAT B only if no tool was called.

        If the required structure is not followed exactly, the output is invalid.
        """

    def invoke(self, user_input: str, max_iterations: int = 8):
        state = {
            "messages": [HumanMessage(content=user_input)],
            "working_directory": os.getcwd()
        }
        config = {
            "recursion_limit": max_iterations,
            "configurable": {"thread_id": self.thread_id},
            "callbacks": [self.usage_callback]
        }
        return self.graph.invoke(state, config)

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
                    "messages": state["messages"] + guardrail_errors, 
                    "working_directory": state["working_directory"]
                }

            return state

        def should_continue(state: AgentState):
            last_message = state["messages"][-1]

            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tool"

            if isinstance(last_message, ToolMessage):
                tool_result = json.loads(last_message.content)
                if tool_result.get("success") and tool_result.get("guardrail") == "":
                    return "responder"
                return "reasoning"

            return "responder"

        def tool_node(state: AgentState):
            tool_results = []
            new_working_directory = state.get("working_directory")

            last_message = state["messages"][-1]

            tools_by_name = {tool.name: tool for tool in self.tools}

            for tool_call in last_message.tool_calls:
                tool = tools_by_name.get(tool_call["name"])

                try:
                    result = tool.invoke({
                        "command": tool_call["args"].get("command"),
                        "shell_path": self.shell_path,
                        "shell_flag": self.shell_flag,
                        "working_directory": state.get("working_directory"),
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
                "messages": state["messages"] + tool_results,
                "working_directory": new_working_directory
            }
        
        def responder_node(state: AgentState) -> AgentState:
            messages = [
                SystemMessage(content=self.responder_prompt + f"\nCurrent working directory: {state['working_directory']}"),
                *state["messages"]
            ]
            
            responder_llm = init_chat_model(model=os.getenv("GROQ_MODEL"), temperature=0.15)
            response = responder_llm.invoke(messages)
            
            return {
                "messages": state["messages"] + [response],
                "working_directory": state["working_directory"]
            }

        graph = StateGraph(AgentState)
        
        graph.add_node("reasoning", reasoning_node)
        graph.add_node("tool_guardrail", tool_guardrail_node)
        graph.add_node("tool", tool_node)
        graph.add_node("responder", responder_node)

        graph.add_edge(START, "reasoning")
        graph.add_conditional_edges("tool_guardrail", should_continue)
        graph.add_conditional_edges("tool", should_continue)
        graph.add_conditional_edges("reasoning", should_continue, {
            "tool": "tool_guardrail",
            "responder": "responder",
            END: END
        })
        graph.add_edge("responder", END)

        return graph.compile(checkpointer=self.memory)
