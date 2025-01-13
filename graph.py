from subgraph import SubGraph
from state import State

from langgraph.graph import START, StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from tools import all_tools


class Graph:
    def __init__(self, tools, index):
        self.tools = [all_tools[tool] for tool in tools]
        self.now_graph_index = index
        self.now_compile_graph = None
        self.all_compile_graphs = []

    def build_graph(self, start_index):
        tool = self.tools[start_index]
        now_graph = SubGraph(tool)
        # Build graph
        builder = StateGraph(State)
        #  Node
        builder.add_node("assistant", now_graph.assistant)
        builder.add_node("tools", ToolNode([tool]))
        builder.add_node("request_human_feedback",
                         now_graph.request_human_feedback)
        builder.add_node("get_human_feedback",
                         now_graph.get_human_feedback)
        builder.add_node("arg_check_assistant",
                         now_graph.arg_check_assistant)
        builder.add_node("arg_add_assistant", now_graph.arg_add_assistant)

        if start_index != len(self.tools) - 1:
            builder.add_node("next_graph", self.build_graph(
                start_index+1).now_compile_graph)
            builder.add_conditional_edges(
                "assistant",
                now_graph.tools_condition_edge_to_next_graph,
                ["tools", "next_graph", "arg_check_assistant"]
            )
        else:
            builder.add_conditional_edges(
                "assistant",
                now_graph.tools_condition_edge_to_end,
                ["tools", END, "arg_check_assistant"]
            )
        # Edge
        builder.add_edge(START, "request_human_feedback")
        builder.add_conditional_edges("get_human_feedback", now_graph.arg_add_assistant_or_assistant, [
                                      "arg_add_assistant", "assistant"])
        builder.add_edge("request_human_feedback", "get_human_feedback")
        builder.add_edge("arg_check_assistant", "request_human_feedback")
        builder.add_edge("tools", "assistant")
        builder.add_edge("arg_add_assistant", "assistant")
        # Compile graph
        memory = MemorySaver()
        graph = builder.compile(checkpointer=memory)
        
        self.now_compile_graph = graph
        self.all_compile_graphs.insert(0, graph)
        self.save_graph(graph, tool.__name__)
        return self

    def save_graph(self, graph, name):
        try:
            png_data = graph.get_graph(xray=1).draw_mermaid_png()
            output_file = name + ".png"
            with open(output_file, "wb") as f:
                f.write(png_data)
            print(f"圖形已保存到: {output_file}")
        except Exception as e:
            print(f"無法保存圖形：{str(e)}")

    def get_all_graphs(self):
        return self.all_compile_graphs