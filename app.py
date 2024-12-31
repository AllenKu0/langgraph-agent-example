import os
import getpass
import json
from graph import Graph


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

# 請給我Taipei 2024/12/05的天氣
# 請給我2024/12/05 台灣前往東京的航班
# 請給我一天的天氣


if __name__ == "__main__":
    config = json.load(open("config.json", "r", encoding="utf-8"))
    graph = Graph(config["tool_function_list"]).build_graph(0)

    thread = {"configurable": {"thread_id": "2"}}

    # Initial input
    initial_input = {"messages": "",
                     "tool_use": []}

    # graph.invoke(initial_input, thread, stream_mode="values")

    for event in graph.stream(initial_input, thread, stream_mode="values"):
        # print("Event:", event)
        event["messages"][-1].pretty_print()
