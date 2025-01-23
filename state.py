from langgraph.graph import MessagesState
from typing import Annotated
import operator

class State(MessagesState):
    tool_use: set
    args_missing_funcname: str
    tool_calls_args: dict
    summary: str
    is_response: str
