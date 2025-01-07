import os
import getpass
import json
from graph import Graph
import threading
import time
import gradio as gr
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage
from functools import partial


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

# 請給我Taipei 2024/12/05的天氣
# 請給我2024/12/05 台灣前往東京的航班
# 請給我一天的天氣


service_running = threading.Event()
service_running.set()

config = json.load(open("config.json", "r", encoding="utf-8"))
graph = Graph(config["tool_function_list"]).build_graph(0)
thread = {"configurable": {"thread_id": "2"}}
# Initial input
initial_input = {"messages": "",
                 "tool_use": []}


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


def start_none_task():
    try:
        print("Start None Task")
        message = start_graph(None)
        print("End None Task")
        yield message
    except Exception as e:
        print(f"Task interrupted: {e}")
    finally:
        print("Task completed")


def stop_task():
    stop_service()
    task_thread.join()
    return "Task stopped"


def get_user_input(user_input):
    print("User Input:"+user_input)
    print("next1:", graph.get_state(thread).next)
    message = start_graph(Command(resume=user_input))  # 從中斷開始
    state = graph.get_state(thread)
    print("next2:", graph.get_state(thread).next)
    if "next_graph" in state.next:
        print("next_graph")
        # start_none_task()
        start_graph(Command(resume=None))
    # print("Message----:",message)
    # if not hasattr(message, "__interrupt__"):
    #     start_graph(None) #　走新圖
    return {message}


def start_graph(_input):
    print("Start Graph")
    for event in graph.stream(_input, thread, stream_mode="values", subgraphs=True):
        event[1]["messages"][-1].pretty_print()
        
        print("message type:", event[1]["messages"][-1].type)
        if event[1]["messages"][-1].type == "ai" and len(event[1]["messages"][-1].tool_calls) == 0:
            print("AI Message:"+event[1]["messages"][-1].content)
            state = graph.get_state(thread, subgraphs=True)
            print("parent_graph_state state:", state.next)
            if "next_graph" in state.next:
                graph.update_state(
                    thread, {"messages": ""})
                state = state.tasks[0].state
                print("subgraphs state:", state)
            return event[1]["messages"][-1].content, state


def initialize():
    # initialMessage = [{
    #     "role": "user",
    #     "content": ""
    # }]
    initialMessage = []
    message, state = start_graph(initial_input)
    print("state:", state.next)
    return updateMessageList(message, "assistant", initialMessage)


def updateMessageList(message, role, messageList):
    try:
        messageList.append({
            "role": role,
            "content": message,
        })
    except Exception as e:
        print(f"Error: {e}")

    return messageList


def getResponse(prompt, history=[], messageList={}):
    # 使用者輸入
    updateMessageList(prompt, "user", messageList)
    # LLM
    responeMessage, state = start_graph(Command(resume=prompt))

    # LLM 回覆
    updateMessageList(responeMessage, "assistant", messageList)
    # LLM Next Graph
    print("state:", state.next)
    if "next_graph" in state.next:
        print("next_graph")
        responeMessage, state = start_graph(None)
        updateMessageList(responeMessage, "assistant", messageList)

    # userContext = [content['content']
    #                for content in messageList if content['role'] == 'user']
    # assistantContext = [content['content']
    #                     for content in messageList if content['role'] == 'assistant']

    # response = [(_user, _response)
    #             for _user, _response in zip(userContext[1:], assistantContext[1:])]

    print("messageList:", messageList)
    return messageList, ""


# Create the GUI
# with gr.Blocks() as demo:

    # demo.launch(server_name="0.0.0.0", server_port=7860)
    # gr.Markdown("# Task Control Interface")

    # status_output = gr.Textbox(
    #     label="Current Status", interactive=False, lines=2)
    # result_output = gr.Textbox(label="Result", interactive=False, lines=5)
    # user_input = gr.Textbox(
    #     placeholder="Type here and press enter...", label="User Input", interactive=True)
    # current_status = gr.Interface(
    #     fn=get_user_input,
    #     inputs=[
    #         user_input               # Textbox for user_input
    #     ],
    #     # Output the result of the function
    #     outputs=[result_output],
    #     live=False,                  # Set live=False to use the button to trigger the function
    # )

    # gr_interface = gr.Interface(
    #     fn=start_none_task,
    #     inputs=None,
    #     # Output the result of the function
    #     outputs=[status_output],
    #     live=False,                  # Set live=False to use the button to trigger the function
    # )
    # start_btn = gr.Button("Start Task")
    # stop_btn = gr.Button("Stop Task")

    # start_btn.click(fn=start_task, inputs=None, outputs=[status_output])
    # stop_btn.click(fn=stop_task, inputs=None, outputs=[status_output])


if __name__ == "__main__":
    # graph.invoke(initial_input, thread, stream_mode="values")
    initList = initialize()
    print("messageList:", initList)

    partial_getResponse = partial(getResponse, messageList=initList)

    with gr.Blocks() as demo:
        status_output = gr.Textbox(
            label="Current Status", interactive=False, lines=2)
        chatbot = gr.Chatbot(value=initList, type="messages")
        state = gr.State([])

        with gr.Row():
            user_input = gr.Textbox(show_label=False,
                                    placeholder="輸入問題", container=False)
            submit_btn = gr.Button("送出")
            submit_btn.click(fn=partial_getResponse, inputs=[
                user_input, state], outputs=[chatbot, state])

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
    # Assuming graph.stream can periodically check service_running.is_set()
    # for event in graph.stream(initial_input, thread, stream_mode="values", interrupt_before=["get_human_feedback"]):
    #     # event["messages"][-1].pretty_print()
    # demo.user_input.update(interactive=True)
