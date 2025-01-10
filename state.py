from langgraph.graph import MessagesState


class State(MessagesState):
    tool_use: set
    now_tool: str
    args_missing_funcname: str
    tool_calls_args: dict
