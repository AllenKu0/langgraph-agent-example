import os
import getpass
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import START, StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from tools import get_weather_info, get_flight_info

class State(MessagesState):
    tool_use: list

def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

tools = [get_flight_info, get_weather_info]

# Define LLM with ollama
llm = ChatOllama(
    model="llama3.1:8b",
    temperature=0,
).bind_tools(tools, parallel_tool_calls=False)

# System message
sys_msg = SystemMessage(
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

# You are an AI Agent capable of querying flight information. You have access to a function for retrieving flight details for specific routes and dates. When a user asks for flight information, use the flight query function to retrieve the relevant data. For subsequent questions based on the initial query results, do not use the function again but rely on the retrieved data to answer.

# Example interactions:

#     1. User: "請問2024年12月01號 台北到東京的航班有哪些"
#     - Use the flight query function to retrieve the flight details for the specified route and date.

#     2. User: "那根據結果給我華航的班機"
#     - Use the previously retrieved data to filter and provide information specifically about China Airlines flights without calling the function again.

#     Ensure to keep track of the initial query results for efficient handling of follow-up questions.

# llm
def assistant(state: State):
    print("state:", "assistant")
    messages = llm.invoke([sys_msg] + state["messages"])
    print("messages.tool_calls",messages.tool_calls)
    if hasattr(messages, "tool_calls") and len(messages.tool_calls) > 0:
        print("tool name",messages.tool_calls)
        state["tool_use"].append(messages.tool_calls[-1]["name"])
        return {"messages": [messages], "tool_use": state["tool_use"]}
    return {"messages": [messages]}

# 中斷等待輸入
def human_feedback(state: State):
    return handle_tool_use(state)
    
# 當兩個tool 都被使用則結束
def llm_call(state: State):
    if "get_weather_info" in state["tool_use"] and "get_flight_info" in state["tool_use"]:
        return END
    else:
        return "assistant"
    
# 是否為tool call
def tools_condition_edge(state: State):
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

# 非Node Function--------------------------------------------------------
# graph 圖片保存
def save_graph(graph):
    try:
        png_data = graph.get_graph().draw_mermaid_png()
        output_file = "graph.png"
        with open(output_file, "wb") as f:
            f.write(png_data)
        print(f"圖形已保存到: {output_file}")
    except Exception as e:
        print(f"無法保存圖形：{str(e)}")

def handle_tool_use(state):
    querys = {
        "get_weather_info": "請根據以下內容輸入你想查詢的天氣: 地名, 天數\n",
        "get_flight_info": "請根據以下內容輸入你想查詢的航班: 出發地, 目的地, 起飛日\n",
    }
    
    for tool, prompt in querys.items():
        if tool not in state["tool_use"]:
            return {"messages": get_user_input(prompt)} 
    return {"messages": []}
    
def get_user_input(prompt):
    user_input = input(prompt)
    return [HumanMessage(content=user_input)]

# Build graph
builder = StateGraph(State)
#  Node
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))
builder.add_node("human_feedback", human_feedback)
# Edge
builder.add_edge(START, "human_feedback")
builder.add_conditional_edges("human_feedback", llm_call, ["assistant", END])
builder.add_conditional_edges(
    "assistant",
    tools_condition_edge,
    ["tools", "human_feedback"]
)
builder.add_edge("tools", "assistant")


# Compile graph
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
save_graph(graph)


thread = {"configurable": {"thread_id": "2"}}

# Initial input
initial_input = {"messages": "",
                 "tool_use": []}

for event in graph.stream(initial_input, thread, stream_mode="values"):
    event["messages"][-1].pretty_print()

# 請給我Taipei 2024/12/05的天氣
# 請給我2024/12/05 台灣前往東京的航班