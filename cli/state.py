from langgraph.graph import MessagesState

class AgentState(MessagesState):
    working_directory: str
