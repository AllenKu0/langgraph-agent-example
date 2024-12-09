
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END
from tools import querys
from state import State


class SubGraph:
    def __init__(self, tool):
        self.tool = tool 
        self.llm = ChatOllama(
                model="llama3.1:8b",
                temperature=0,
            ).bind_tools([tool], parallel_tool_calls=False)
        self.sys_msg = SystemMessage(
            content="""
            You are an AI Agent equipped with various tools to help you complete tasks. You should automatically determine whether these tools are needed based on the user's request. If you can directly answer the question, do not generate a tool message. Only use the corresponding tool when you need to retrieve real-time information. Here are the tools you have access to:

            Flight Status Query: For retrieving real-time flight information.
            Weather Query: For executing weather-related queries.
            When handling each request, follow these steps:

            Determine if you can directly answer the user's question.
            If you cannot, decide which tool can most effectively help you complete the task.
            Only generate the corresponding tool message when necessary.
            Remember to always provide the best answer based on the user's needs and avoid unnecessary tool calls.
                
            """)
        self.querys = {tool.__name__ : querys[tool.__name__]}
        
    def handle_tool_use(self,state):        
        for tool, prompt in self.querys.items():
            if tool not in state["tool_use"]:
                return {"messages": self.get_user_input(prompt)} 
        return {"messages": []}
        
    def get_user_input(self,prompt):
        user_input = input(prompt)
        return [HumanMessage(content=user_input)]

    def assistant(self, state: State):
        # System message
        messages = self.llm.invoke([self.sys_msg] + state["messages"])
        if hasattr(messages, "tool_calls") and len(messages.tool_calls) > 0:
            print("tool name",messages.tool_calls)
            state["tool_use"].append(messages.tool_calls[-1]["name"])
            return {"messages": [messages], "tool_use": state["tool_use"]}
        return {"messages": [messages]}

    def human_feedback(self, state: State):
        return self.handle_tool_use(state)
        
    def llm_call(self,state: State):
        if self.tool.__name__ in state["tool_use"]:
            return "next_graph"
        else:
            return "assistant"
        
    def llm_call_to_end(self,state: State):
        if self.tool.__name__ in state["tool_use"]:
            return END
        else:
            return "assistant"   
        
    def tools_condition_edge(self,state: State):
        if isinstance(state, list):
            ai_message = state[-1]
        elif isinstance(state, dict) and (messages := state.get("messages", [])):
            ai_message = messages[-1]
        elif messages := getattr(state, messages, []):
            ai_message = messages[-1]
        else:
            raise ValueError(f"No messages found in input state to tool_edge: {state}")
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return "human_feedback"    