import os
import getpass
import json
from graph import Graph
import threading
import time
import gradio as gr
from langgraph.types import Command


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

# 請給我Taipei 2024/12/05的天氣
# 請給我2024/12/05 台灣前往東京的航班
# 請給我一天的天氣
# 請給我Taipei一天的天氣


service_running = threading.Event()
service_running.set()

config = json.load(open("config.json", "r", encoding="utf-8"))
graph = Graph(config["tool_function_list"], 0).build_graph(0)
now_graph_index = graph.now_graph_index
now_compile_graph = None
print("graphs.get_all_graphs():", graph.get_all_graphs())
thread = {"configurable": {"thread_id": "2"}}
# Initial input
initial_input = {"messages": ""}


def long_running_task():
    global service_running
    try:
        for event in graph.stream(initial_input, thread, stream_mode="values"):
            event["messages"][-1].pretty_print()
            print(event["messages"][-1].type)
            if event["messages"][-1].type == "ai":
                print("AI Message:"+event["messages"][-1].content)
                return event["messages"][-1].content
    except Exception as e:
        print(f"Task interrupted: {e}")
    finally:
        print("Task completed")


def stop_service():
    global service_running
    service_running.clear()  # Clear the event to signal the task to stop
    print("Service stopping...")


def start_task():
    # initial_input
    try:
        message = start_graph(initial_input)
        yield message
    except Exception as e:
        print(f"Task interrupted: {e}")
    finally:
        print("Task completed")

    # return "Task started"


def stop_task():
    stop_service()
    task_thread.join()
    return "Task stopped"


def start_graph(_input, graph):
    print("Start Graph")
    for event in graph.stream(_input, thread, stream_mode="values", subgraphs=True):
        event[1]["messages"][-1].pretty_print()
        print("message type:", event[1]["messages"][-1].type)
        if event[1]["messages"][-1].type == "ai" and len(event[1]["messages"][-1].tool_calls) == 0:
            print("AI Message:"+event[1]["messages"][-1].content)
            state = graph.get_state(thread, subgraphs=True)
            task_state = state.tasks
            return event[1]



def initialize(index, _input={"messages": ""}, messageList=[]):
    global graph
    global now_graph_index
    global now_compile_graph

    now_compile_graph = graph.all_compile_graphs[index]
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
        responeMessage = event["messages"][-1].content
        updateMessageList(responeMessage, "assistant", messageList)
        state = now_compile_graph.get_state(thread, subgraphs=True)
        if "next_graph" in state.next:
            tools_hints = initialize(now_graph_index + 1, event, messageList)

    return messageList, tools_hints, ""


if __name__ == "__main__":
    print("config[tool_function_list][0]", config["tool_function_list"][0])
    hint = initialize(0)

    with gr.Blocks() as demo:
        tools_hints = gr.Textbox(value=hint, label="Now Tool Hint", interactive=False, lines=2)
        chatbot = gr.Chatbot(type="messages")
        state = gr.State([])

        with gr.Row():
            user_input = gr.Textbox(show_label=False,
                                    placeholder="輸入問題", container=False)
            submit_btn = gr.Button("送出")
            submit_btn.click(fn=getResponse, inputs=[
                user_input, tools_hints], outputs=[chatbot, tools_hints, state])

            # clear the textbox
            submit_btn.click(
                fn=lambda: "",
                inputs=None,
                outputs=user_input
            )
        start_btn = gr.Button("Start Task")
        stop_btn = gr.Button("Stop Task")

        # start_btn.click(fn=start_task, inputs=None, outputs=[status_output])
        # stop_btn.click(fn=stop_task, inputs=None, outputs=[status_output])

    demo.launch()
