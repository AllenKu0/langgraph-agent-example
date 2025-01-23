from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, RemoveMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END
from langgraph.types import interrupt
from tools import querys
from state import State
import re
import ast
from prompt import sys_tool_msg, sys_args_check_msg, sys_args_add_msg, sys_summarize_msg, sys_args_missing_response_msg


class SubGraph:
    def __init__(self, tool):
        self.tool = tool
        self.llm = ChatOllama(
            model="llama3.1:8b",
            temperature=0,
        ).bind_tools([tool], parallel_tool_calls=False)
        self.llm_with_no_tool = ChatOllama(
            model="llama3.1:8b",
            temperature=0,
        )
        self.querys = {tool.__name__: querys[tool.__name__]}

    def request_human_feedback(self, state: State):
        print("now is request_human_feedback ----------------------------------------------------------------------------------------------------")
        print("state[messages][-1].content", state["messages"][-1].content)
        state["args_missing_funcname"] = state.get("args_missing_funcname", "")
        state["tool_calls_args"] = state.get("tool_calls_args", {})
        state["tool_use"] = state.get("tool_use", [])
        state["summary"] = state.get("summary", "")
        state["is_response"] = state.get("is_response", "")
        return self.handle_tool_use(state)
    
    def get_human_feedback(self, state: State):
        feedback = interrupt("Please provide feedback:")
        print("now is get_human_feedback ----------------------------------------------------------------------------------------------------")        
        messages = self.get_user_input(
            feedback, state["messages"][-1].content, state["args_missing_funcname"], state["tool_calls_args"])
        
        # response = self.llm_with_no_tool.invoke(
        #     [sys_args_missing_response_msg] + [AIMessage(content=state["messages"][-1].content)] + [HumanMessage(content=feedback)] )
        
        # print("messages:", response.content)
        # state["is_response"] = response.content
        # if response.content == "yes":
        #     missing_funcname = state["args_missing_funcname"]
        #     tool_calls_args = state["tool_calls_args"]
        #     prompt = state["messages"][-1].content
        #     messages = HumanMessage(content=f"我原本是要進行{missing_funcname}，並且之前提供過參數{tool_calls_args}，這是我根據 {prompt} 補上的參數:{feedback}")
        # else:
        #     messages = HumanMessage(content=feedback)
        
        return self.state_builder(state, [messages])
        
    def arg_add_assistant(self, state: State):
        print("now is arg_add_assistant ----------------------------------------------------------------------------------------------------")
        messages = self.llm_with_no_tool.invoke(
            [sys_args_add_msg] + [state["messages"][-1]])
        tool_args = self.arg_extract_json_from_string(messages.content)
        if tool_args != None:
            state["tool_calls_args"] = tool_args
        messages = HumanMessage(content=messages.content)
        return self.state_builder(state, [messages])
        
    def assistant(self, state: State):
        # System message
        print("now is assistant ----------------------------------------------------------------------------------------------------")
        summary = state["summary"]
        if summary:
            # Add summary to system message
            system_message = f"Summary of conversation earlier: {summary}"

            # Append summary to any newer messages
            messages = [SystemMessage(content=system_message)] + state["messages"]
        else:
            messages = [state["messages"][-1]]
        messages = self.llm.invoke([sys_tool_msg] + messages)
        
        if hasattr(messages, "tool_calls") and len(messages.tool_calls) > 0:
            state["args_missing_funcname"] = messages.tool_calls[-1]["name"] if self.check_args_null_or_blank(
                messages.tool_calls[-1]["args"]) else ""
            state["tool_calls_args"] = messages.tool_calls[-1]["args"]
            state["tool_use"].append(messages.tool_calls[-1]["name"])
            if state["args_missing_funcname"] != "":
                messages = HumanMessage(content=str(messages.tool_calls[-1]))

        return self.state_builder(state, [messages])
    
    def summarize_assistant(self, state: State):
        feedback = interrupt("Please activate summarize_assistant")
        print("now is summarize_assistant ----------------------------------------------------------------------------------------------------")
        if len(state["messages"]) > 3:
            summary = state["summary"]
            if summary:
                summary_message = (
                    f"This is summary of the conversation to date: {summary}\n\n"
                    "Extend the summary by taking into account the new messages above:"
                )
            else:
                summary_message = "Create a summary of the conversation above:"
            messages = state["messages"] + [HumanMessage(content=summary_message)]
            response = self.llm_with_no_tool.invoke([sys_summarize_msg] + messages)
            delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-1]]
            state['summary'] = response.content
            return {"messages": delete_messages, "summary": state["summary"]}
        pass
        
    def arg_check_assistant(self, state: State):
        print("now is arg_check_assistant ----------------------------------------------------------------------------------------------------")
        messages = self.llm_with_no_tool.invoke(
            [sys_args_check_msg] + [state["messages"][-1]])
        
        return self.state_builder(state, [HumanMessage(content=messages.content)])

    
    def arg_add_assistant_or_assistant(self, state: State):
        if state["is_response"] == "yes":
            return "arg_add_assistant"
        else:
            return "assistant"
            
        # if state["args_missing_funcname"] != "":
        #     return "arg_add_assistant"
        # else:
        #     return "assistant"

    def tools_condition_edge_to_summarize_assistant(self, state: State):
        if isinstance(state, list):
            ai_message = state[-1]
        elif isinstance(state, dict) and (messages := state.get("messages", [])):
            ai_message = messages[-1]
        elif messages := getattr(state, messages, []):
            ai_message = messages[-1]
        else:
            raise ValueError(
                f"No messages found in input state to tool_edge: {state}")
        if state["args_missing_funcname"] != "":
            return "arg_check_assistant"
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return "summarize_assistant"

    def tools_condition_edge_to_end(self, state: State):
        if isinstance(state, list):
            ai_message = state[-1]
        elif isinstance(state, dict) and (messages := state.get("messages", [])):
            ai_message = messages[-1]
        elif messages := getattr(state, messages, []):
            ai_message = messages[-1]
        else:
            raise ValueError(
                f"No messages found in input state to tool_edge: {state}")
        if state["args_missing_funcname"] != "":
            return "arg_check_assistant"
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return END

    def handle_tool_use(self, state):
        if state["args_missing_funcname"] != "":  
            return self.state_builder(state, AIMessage(content=state["messages"][-1].content))
        for tool, prompt in self.querys.items():
            if tool not in state["tool_use"]:
                print(
                    f"now is {self.tool.__name__}  Agent----------------------------------------------------------------------------------------------------")
                return self.state_builder(state, [AIMessage(content=prompt)])
        return self.state_builder(state)

    def get_user_input(self, user_input, prompt, missing_funcname="", old_args={}):
        if missing_funcname != "":
            return HumanMessage(content=f"我原本是要進行{missing_funcname}，並且之前提供過參數{old_args}，這是我根據 {prompt} 補上的參數:{user_input}")
        return HumanMessage(content=user_input)

    def check_args_null_or_blank(self, json):
        for key, value in json.items():
            if value is None or (isinstance(value, str) and value.strip() == ""):
                return True
        return False

    def arg_extract_json_from_string(self, message):
        # Regular expression to match JSON content
        dict_pattern = re.compile(r'\{.*?\}')

        # Find the first match of the dictionary pattern in the string
        match = dict_pattern.search(message)

        if match:
            # Extract the matched dictionary-like string
            dict_str = match.group(0)

            # Convert the string to a dictionary
            try:
                dict_obj = ast.literal_eval(dict_str)
                return dict_obj
            except (ValueError, SyntaxError):
                return None
        return None

    def state_builder(self, state, message=[]):
        return {"messages": message, "tool_use": state["tool_use"], "args_missing_funcname": state["args_missing_funcname"], "tool_calls_args": state["tool_calls_args"],"summary": state["summary"], "is_response": state["is_response"]}
