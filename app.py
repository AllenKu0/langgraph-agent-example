import os
import getpass
import json
from graph import Graph
from concurrent.futures import ThreadPoolExecutor, Future
import gradio as gr
import uuid
from langgraph.types import Command
from db import ExternalSaver
from langgraph.checkpoint.memory import MemorySaver
from tools import querys

def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


config = json.load(open("config.json", "r", encoding="utf-8"))
mongodb_url = "mongodb://root:root@localhost:27017/"

external_saver = ExternalSaver(mongodb_url)
checkpointer = external_saver.get_checkpointer()
# 
# checkpointer = MemorySaver()
graph = Graph(config["tool_function_list"], 0, checkpointer).build_graph(0)
now_graph_index = graph.now_graph_index
now_compile_graph = None
thread = {"configurable": {"thread_id": "2"}}
thread_ids = external_saver.get_all_thread_id()
print("thread_ids:", thread_ids)

# Initial input
initial_input = {"messages": ""}
task_stop = False
executor = ThreadPoolExecutor(max_workers=2)
current_task: Future = None

def start_task(prompt, tools_hint, messageList):
    global current_task
    print("start_task messageList有清?", messageList)
    current_task = executor.submit(getResponse, prompt, tools_hint, messageList)
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
    global thread
    for event in graph.stream(_input, thread, stream_mode="values", subgraphs=True):
        if not task_stop:
            event[1]["messages"][-1].pretty_print()
            if event[1]["messages"][-1].type == "ai" and len(event[1]["messages"][-1].tool_calls) == 0:
                # print("AI Message:"+event[1]["messages"][-1].content)
                return event[1]
        else:
            task_stop = False
            return "Task canceled"

def initialize(index, _input={"messages": ""}, is_canceled=False):
    global graph
    global now_graph_index
    global now_compile_graph
    global thread

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


def updateMessageList(message, role, messageList, now_graph_index):
    try:
        messageList.append({
            "role": role,
            "content": message,
        })
        print("更新的thread_id", thread["configurable"]["thread_id"])
        print("更新的對話List:", messageList)
        external_saver.update_thread(thread["configurable"]["thread_id"], messageList, now_graph_index)
    except Exception as e:
        print(f"Error: {e}")

    return messageList


def getResponse(prompt, tools_hint, messageList=[]):
    global graph
    global now_graph_index
    global now_compile_graph
    global thread
    
    print("messageList有清?", messageList)
    # 使用者輸入
    updateMessageList(prompt, "user", messageList, now_graph_index)
    # LLM
    state = now_compile_graph.get_state(thread, subgraphs=True)

    if "summarize_assistant" not in state.next:
        event = start_graph(Command(resume=prompt), now_compile_graph)
        responeMessage = event["messages"][-1].content if not isinstance(event, str) else event
        updateMessageList(responeMessage, "assistant", messageList, now_graph_index)
        state = now_compile_graph.get_state(thread, subgraphs=True)
        if isinstance(event, str):
            tools_hint = initialize(now_graph_index, messageList=messageList, is_canceled=True)
        elif "summarize_assistant" in state.next:
            event = start_graph(Command(resume="啟動summarize_assistant"), now_compile_graph)
            responeMessage = event["summary"]
            tools_hint = initialize(now_graph_index + 1)
    print("state.next", type(state.next))
    
    if not bool(state.next):
        tools_hint = "Task is done"
    return messageList, tools_hint, ""

def create_new_thread():
    global thread_ids
    random_uuid = str(uuid.uuid4())
    thread_ids.append(random_uuid)
    external_saver.create_thread(random_uuid, [], 0)
    # external_saver.update_thread(random_uuid, [], 0)
    return gr.update(choices=thread_ids)


def change_thread(thread_id):
    global graph
    global thread
    global now_graph_index
    global now_compile_graph

    thread['configurable']['thread_id'] = thread_id
    chat_thread = external_saver.get_thread(thread_id)
    if chat_thread is None:
        print("thread not found")
        external_saver.insert_thread(thread_id, [], 0)
        chat_thread = external_saver.get_thread(thread_id)
    print("thread:",chat_thread)
    
    chat_history = chat_thread['threads'][0]['chat_history']
    print("chat_history:",chat_history)
    now_graph_index = chat_thread['threads'][0]['now_graph_index']
    print("now_graph_index:",now_graph_index)
    now_compile_graph = graph.all_compile_graphs[now_graph_index]
    
    if not chat_thread['threads'][0]['is_initailized']:
        hint = initialize(0)
        external_saver.update_thread_initailized(thread_id, True)
    else: 
        hint = querys[graph.tools[now_graph_index].__name__]    

    return chat_history, hint
    

if __name__ == "__main__":
    chat_history, hint = change_thread(thread["configurable"]["thread_id"])
        
    with gr.Blocks() as demo:
        tools_hint = gr.Textbox(value=hint, label="Now Tool Hint", interactive=False, lines=2)
        chatbot = gr.Chatbot(type="messages", value=chat_history)
        state = gr.State([])
        with gr.Row():
            thread_dropdown = gr.Dropdown(
                choices=thread_ids, label="Now Thread", info="You can change your thred by thid dropdown", interactive=True)
            thread_dropdown.input(fn=change_thread, inputs=[thread_dropdown],outputs=[chatbot, tools_hint])
            create_thread_btn = gr.Button("Create New Thread")
            create_thread_btn.click(fn=create_new_thread, outputs=[thread_dropdown])
        
        
        with gr.Row():
            user_input = gr.Textbox(show_label=False,
                                    placeholder="輸入問題", container=False)
            submit_btn = gr.Button("送出")
            submit_btn.click(fn=start_task, inputs=[
                user_input, tools_hint, chatbot], outputs=[chatbot, tools_hint, state])

            # clear the textbox
            submit_btn.click(
                fn=lambda: "",
                inputs=None,
                outputs=user_input
            )
        # start_btn = gr.Button("Start Task")
        stop_btn = gr.Button("Stop Task")

        # start_btn.click(fn=start_task, inputs=None, outputs=[status_output])
        stop_btn.click(fn=stop_task, inputs=None, outputs=[tools_hint])

    demo.launch(server_name="0.0.0.0", server_port=7860)


# 請給我Taipei 2024/12/05的天氣
# 請給我2024/12/05 台灣前往東京的航班
# 請給我一天的天氣
# 請給我Taipei一天的天氣
