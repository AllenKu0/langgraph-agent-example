import os
import getpass
import json
from graph import Graph
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
import gradio as gr
from langgraph.types import Command
from db import ExternalSaver


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


config = json.load(open("config.json", "r", encoding="utf-8"))
postgres_url = "postgresql://postgres:postgres@localhost:5432/chat_database"
connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
}

checkpointer = ExternalSaver(postgres_url,connection_kwargs).get_checkpointer()
graph = Graph(config["tool_function_list"], 0, checkpointer).build_graph(0)
now_graph_index = graph.now_graph_index
now_compile_graph = None
thread = {"configurable": {"thread_id": "2"}}

# Initial input
initial_input = {"messages": ""}
task_stop = False
executor = ThreadPoolExecutor(max_workers=2)
current_task: Future = None

def start_task(prompt, tools_hints, messageList=[]):
    global current_task
    current_task = executor.submit(getResponse, prompt, tools_hints, messageList)
    return current_task.result()[0], current_task.result()[1], current_task.result()[2]


def stop_task():
    global task_stop
    global current_task
    if current_task and not current_task.done():
        print("取消中")
        task_stop = True
        return "Task canceled"
    return "No Task can be canceled"


def start_graph(_input, graph):
    global task_stop
    for event in graph.stream(_input, thread, stream_mode="values", subgraphs=True):
        if not task_stop:
            event[1]["messages"][-1].pretty_print()
            print("message type:", event[1]["messages"][-1].type)
            if event[1]["messages"][-1].type == "ai" and len(event[1]["messages"][-1].tool_calls) == 0:
                print("AI Message:"+event[1]["messages"][-1].content)
                state = graph.get_state(thread, subgraphs=True)
                task_state = state.tasks
                return event[1]
        else:
            task_stop = False
            return "Task canceled"

def initialize(index, _input={"messages": ""}, messageList=[], is_canceled=False):
    global graph
    global now_graph_index
    global now_compile_graph

    now_compile_graph = graph.all_compile_graphs[index]
    now_compile_graph_state = now_compile_graph.get_state(thread).values
    if is_canceled and now_compile_graph_state['args_missing_funcname'] != "":
        now_compile_graph_state['tool_use'].remove(now_compile_graph_state['args_missing_funcname'])
        now_compile_graph_state['args_missing_funcname'] = ""
        now_compile_graph.update_state(thread, now_compile_graph_state)
    else:
        now_compile_graph.update_state(thread, _input)    
    now_graph_index = index
    event = start_graph(initial_input, now_compile_graph)
    responeMessage = event["messages"][-1].content
    return responeMessage


def updateMessageList(message, role, messageList):
    try:
        messageList.append({
            "role": role,
            "content": message,
        })
    except Exception as e:
        print(f"Error: {e}")

    return messageList


def getResponse(prompt, tools_hints, messageList=[]):
    global graph
    global now_graph_index
    global now_compile_graph
    # 使用者輸入
    updateMessageList(prompt, "user", messageList)
    # LLM
    state = now_compile_graph.get_state(thread, subgraphs=True)

    if "next_graph" not in state.next:
        event = start_graph(Command(resume=prompt), now_compile_graph)
        responeMessage = event["messages"][-1].content if not isinstance(event, str) else event
        updateMessageList(responeMessage, "assistant", messageList)
        state = now_compile_graph.get_state(thread, subgraphs=True)
        if isinstance(event, str):
            tools_hints = initialize(now_graph_index, messageList=messageList, is_canceled=True)
        elif "next_graph" in state.next:
            tools_hints = initialize(now_graph_index + 1, event, messageList)

    return messageList, tools_hints, ""


if __name__ == "__main__":
    
    
    hint = initialize(0)

    with gr.Blocks() as demo:
        tools_hints = gr.Textbox(value=hint, label="Now Tool Hint", interactive=False, lines=2)
        chatbot = gr.Chatbot(type="messages")
        state = gr.State([])

        with gr.Row():
            user_input = gr.Textbox(show_label=False,
                                    placeholder="輸入問題", container=False)
            submit_btn = gr.Button("送出")
            submit_btn.click(fn=start_task, inputs=[
                user_input, tools_hints], outputs=[chatbot, tools_hints, state])

            # clear the textbox
            submit_btn.click(
                fn=lambda: "",
                inputs=None,
                outputs=user_input
            )
        # start_btn = gr.Button("Start Task")
        stop_btn = gr.Button("Stop Task")

        # start_btn.click(fn=start_task, inputs=None, outputs=[status_output])
        stop_btn.click(fn=stop_task, inputs=None, outputs=[tools_hints])

    demo.launch()


# 請給我Taipei 2024/12/05的天氣
# 請給我2024/12/05 台灣前往東京的航班
# 請給我一天的天氣
# 請給我Taipei一天的天氣
