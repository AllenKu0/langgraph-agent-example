from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END
from langgraph.types import interrupt
from tools import querys
from state import State
import re
import ast


class SubGraph:
    def __init__(self, tool, ):
        self.tool = tool
        self.llm = ChatOllama(
            model="llama3.1:8b",
            temperature=0,
        ).bind_tools([tool], parallel_tool_calls=False)
        self.llm_with_no_tool = ChatOllama(
            model="llama3.1:8b",
            temperature=0,
        )
        self.sys_msg = SystemMessage(
            content="""
                You are an AI Agent equipped with various tools to help you complete tasks and give a anwser to user. 
                Please Follow below steps to think, and do the decision in the end.
                1. If you can directly answer the question, do not generate a tool message.
                2. You should automatically determine whether these tools are needed based on the user's request. 
                3. When calling a tool, ensure that every argument used in the tool call is explicitly mentioned in the user's question. If any required argument not mentioned in the user's question, do not attempt to fill in or guess the value by yourself.
                4. Only proceed with tool calls if all arguments are clearly provided by the user.
                
                Here are the tools you have access to:
                    Flight Status Query: For retrieving real-time flight information.
                    Weather Query: For executing weather-related queries.
            """)
        self.sys_args_check_msg = SystemMessage(
            content="""
                You are an AI Agent and response short and precise messages to the user. 
                Please According to the missing arguments for the tool call.
                And follow below example to ask user for the missing arguments.Don't Give any code, just give a question.
                Example:
                    Please provide the day for the weather query.
                    Please provide the destination for the flight query.
            """)
        self.sys_args_add_msg = SystemMessage(content="""
            You are an AI Agent and response short and precise messages to the user.
            If user query is about weather :check get_weather_info argument
            If user query is about flight :check get_flight_info argument
            
            Here are the tools Argument have to be set:
                get_weather_info: location, days, zone
                get_flight_info: DepartureAirportID, ArrivalAirportID, ScheduleStartDate, ScheduleEndDate
                
            According to the user query, you have to regenerate a complete query with now argument.
            Example:
                I want use get_weather_info tool with below arguments:
                Current arguments: {"date": "2024-12-05"}
        """)
        self.querys = {tool.__name__: querys[tool.__name__]}

    def request_human_feedback(self, state: State):
        print("now is request_human_feedback ----------------------------------------------------------------------------------------------------")
        print("state[messages][-1].content", state["messages"][-1].content)
        state["args_missing_funcname"] = state.get("args_missing_funcname", "")
        state["tool_calls_args"] = state.get("tool_calls_args", {})
        state["tool_use"] = state.get("tool_use", [])
        state["now_tool"] = state.get("now_tool", "")
        return self.handle_tool_use(state)

    def assistant(self, state: State):
        # System message
        print("now is assistant ----------------------------------------------------------------------------------------------------")
        messages = self.llm.invoke([self.sys_msg] + [state["messages"][-1]])
        print("assistant messages:", messages)
        if hasattr(messages, "tool_calls") and len(messages.tool_calls) > 0:
            state["args_missing_funcname"] = messages.tool_calls[-1]["name"] if self.check_args_null_or_blank(
                messages.tool_calls[-1]["args"]) else ""
            state["tool_calls_args"] = messages.tool_calls[-1]["args"]
            state["tool_use"].append(messages.tool_calls[-1]["name"])
            if state["args_missing_funcname"] != "":
                messages = HumanMessage(content=str(messages.tool_calls[-1]))

        return self.state_builder(state, [messages])

    def arg_check_assistant(self, state: State):
        print("now is arg_check_assistant ----------------------------------------------------------------------------------------------------")
        messages = self.llm_with_no_tool.invoke(
            [self.sys_args_check_msg] + [state["messages"][-1]])
        print("arg_check_assistant", messages)
        return self.state_builder(state, [HumanMessage(content=messages.content)])

    def arg_add_assistant(self, state: State):
        print("now is arg_add_assistant ----------------------------------------------------------------------------------------------------")
        messages = self.llm_with_no_tool.invoke(
            [self.sys_args_add_msg] + [state["messages"][-1]])

        print("arg_add_assistant messages:", messages)
        tool_args = self.arg_extract_json_from_string(messages.content)
        if tool_args != None:
            state["tool_calls_args"] = tool_args
        print("tool_calls_args", state["tool_calls_args"])
        messages = HumanMessage(content=messages.content)
        return self.state_builder(state, [messages])

    def get_human_feedback(self, state: State):
        feedback = interrupt("Please provide feedback:")
        print("now is get_human_feedback ----------------------------------------------------------------------------------------------------")
        print("feedback:", feedback)

        messages = self.get_user_input(
            feedback, state["messages"][-1].content, state["args_missing_funcname"], state["tool_calls_args"])

        return self.state_builder(state, [messages])

    def arg_add_assistant_or_assistant(self, state: State):
        if state["args_missing_funcname"] != "":
            return "arg_add_assistant"
        else:
            return "assistant"

    def tools_condition_edge_to_next_graph(self, state: State):
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
        return "next_graph"

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
            return {"messages": AIMessage(content=state["messages"][-1].content), "tool_use": state["tool_use"], "args_missing_funcname": state["args_missing_funcname"], "tool_calls_args": state["tool_calls_args"]}
        for tool, prompt in self.querys.items():
            if tool not in state["tool_use"]:
                print(
                    f"now is {self.tool.__name__}  Agent----------------------------------------------------------------------------------------------------")
                state["now_tool"] = tool
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
        return {"messages": message, "tool_use": state["tool_use"], "now_tool": state["now_tool"], "args_missing_funcname": state["args_missing_funcname"], "tool_calls_args": state["tool_calls_args"]}
