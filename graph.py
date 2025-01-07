from subgraph import SubGraph
from state import State

from langgraph.graph import START, StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from tools import all_tools


class Graph:
    def __init__(self, tools):
        self.tools = [all_tools[tool] for tool in tools]

    def build_graph(self, start_index):
        tool = self.tools[start_index]
        sub_graph = SubGraph(tool)
        # Build graph
        builder = StateGraph(State)
        #  Node
        builder.add_node("assistant", sub_graph.assistant)
        builder.add_node("tools", ToolNode([tool]))
        builder.add_node("request_human_feedback", sub_graph.request_human_feedback)
        builder.add_node("get_human_feedback", sub_graph.get_human_feedback)
        builder.add_node("arg_check_assistant", sub_graph.arg_check_assistant)
        builder.add_node("arg_add_assistant", sub_graph.arg_add_assistant)
        
        if start_index != len(self.tools) - 1:
            builder.add_node("next_graph", self.build_graph(start_index+1))
            # builder.add_conditional_edges("request_human_feedback", sub_graph.get_human_feedback_or_to_next_graph, [
            #                               "get_human_feedback", "next_graph"])
            builder.add_conditional_edges(
                "assistant",
                sub_graph.tools_condition_edge_to_next_graph,
                ["tools", "next_graph", "arg_check_assistant"]
            )
        else:
            # builder.add_conditional_edges(
            #     "request_human_feedback", sub_graph.get_human_feedback_or_to_end, ["get_human_feedback", END])
            builder.add_conditional_edges(
                "assistant",
                sub_graph.tools_condition_edge_to_end,
                ["tools", END, "arg_check_assistant"]
            )
        # Edge
        builder.add_edge(START, "request_human_feedback")
        builder.add_conditional_edges("get_human_feedback", sub_graph.arg_add_assistant_or_assistant, ["arg_add_assistant", "assistant"])
        builder.add_edge("request_human_feedback", "get_human_feedback")
        # builder.add_edge("get_human_feedback", "arg_add_assistant")
        builder.add_edge("arg_check_assistant","request_human_feedback")
        builder.add_edge("tools", "assistant")
        builder.add_edge("arg_add_assistant", "assistant")
        # Compile graph
        memory = MemorySaver()
        graph = builder.compile(checkpointer=memory)

        self.save_graph(graph, tool.__name__)
        return graph

    def save_graph(self, graph, name):
        try:
            png_data = graph.get_graph().draw_mermaid_png()
            output_file = name + ".png"
            with open(output_file, "wb") as f:
                f.write(png_data)
            print(f"圖形已保存到: {output_file}")
        except Exception as e:
            print(f"無法保存圖形：{str(e)}")
