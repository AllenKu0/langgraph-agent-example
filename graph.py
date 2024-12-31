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
        builder.add_node("human_feedback", sub_graph.human_feedback)
        builder.add_node("arg_check_assistant", sub_graph.arg_check_assistant)
        builder.add_node("arg_add_assistant", sub_graph.arg_add_assistant)
        
        if start_index != len(self.tools) - 1:
            builder.add_node("next_graph", self.build_graph(start_index+1))
            builder.add_conditional_edges("human_feedback", sub_graph.llm_call, [
                                          "assistant", "next_graph", "arg_add_assistant"])
        else:
            builder.add_conditional_edges(
                "human_feedback", sub_graph.llm_call_to_end, ["assistant", END, "arg_add_assistant"])
        # Edge
        builder.add_edge(START, "human_feedback")
        builder.add_conditional_edges(
            "assistant",
            sub_graph.tools_condition_edge,
            ["tools", "human_feedback", "arg_check_assistant"]
        )
        builder.add_edge("arg_check_assistant","human_feedback")
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
