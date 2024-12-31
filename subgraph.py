
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END
from tools import querys
from state import State


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
        self.sys_msg = SystemMessage(
            content="""
                You are an AI Agent equipped with various tools to help you complete tasks. 
                Please Follow below steps to think, and do the decision in the end.
                1. If you can directly answer the question, do not generate a tool message.
                2. You should automatically determine whether these tools are needed based on the user's request. 
                3. When calling a tool, ensure that every argument used in the tool call is explicitly mentioned in the user's question. If any required argument not mentioned in the user's question, do not attempt to fill in or guess the value by yourself.
                4. Only proceed with tool calls if all arguments are clearly provided by the user.
                
                Here are the tools you have access to:
                    Flight Status Query: For retrieving real-time flight information.
                    Weather Query: For executing weather-related queries.
            """)
        # 1. Determine if you can directly answer the user's question. just give an answer. and don't do above steps.
        # 2. If you cannot, decide which tool can most effectively help you complete the task.
        # 3. Only generate the corresponding tool message when necessary.
        # 4. You have to check every ToolCall argument is missing or not, if missing you should ask the user for the missing arguments.and don't according the tool call result to generate response.
        # 5. Remember to always provide the best answer based on the user's needs and avoid unnecessary tool calls.
        self.sys_args_msg = SystemMessage(
            content="""
                You are an AI Agent and response short and precise messages to the user.
                If user query is about weather :check get_weather_info argument
                If user query is about flight :check get_flight_info argument
                Here are the tools Argument have to be set:
                    get_weather_info: location, days, zone
                    get_flight_info: DepartureAirportID, ArrivalAirportID, ScheduleStartDate, ScheduleEndDate
                     
                If all arguments key have value,you shoud regenerate a new complete query as output with "Argument is complete" in the end.
                Or    
                Please According to the missing arguments for the tool call.
                And follow below example to ask user for the missing arguments.Don't Give any code, just give a question.
                Example:
                    Please provide the day for the weather query.
                    Please provide the destination for the flight query.
                    
                    
            """)
        # Current arguments: {"date": "2024-12-05"}
        self.querys = {tool.__name__: querys[tool.__name__]}

    def assistant(self, state: State):
        # System message
        messages = self.llm.invoke([self.sys_msg] + [state["messages"][-1]])
        if hasattr(messages, "tool_calls") and len(messages.tool_calls) > 0:
            state["args_missing_funcname"] = messages.tool_calls[-1]["name"] if self.check_args_null_or_blank(
                messages.tool_calls[-1]["args"]) else ""
            state["tool_calls_args"] = messages.tool_calls[-1]["args"]
            state["tool_use"].append(messages.tool_calls[-1]["name"])
        if state["args_missing_funcname"] != "":
            messages = HumanMessage(content=str(messages.tool_calls[-1]))
            return {"messages": [messages], "tool_use": state["tool_use"], "args_missing_funcname": state["args_missing_funcname"], "tool_calls_args": state["tool_calls_args"]}
        else:
            return {"messages": [messages], "args_missing_funcname": state["args_missing_funcname"], "tool_calls_args": state["tool_calls_args"]}

    def arg_assistant(self, state: State):
        messages = self.llm_with_no_tool.invoke(
            [self.sys_args_msg] + [state["messages"][-1]])
        if ("Argument is complete" in messages.content):
            state["args_missing_funcname"] = ""
            state["tool_calls_args"] = {}
            messages = HumanMessage(content=messages.content)
        return {"messages": [messages], "args_missing_funcname": state["args_missing_funcname"], "tool_calls_args": state["tool_calls_args"]}

    def human_feedback(self, state: State):
        try:
            if (state["args_missing_funcname"] != ""):
                return self.handle_tool_use(state, state["messages"][-1].content)
        except Exception as e:
            state["args_missing_funcname"] = ""
            state["tool_calls_args"] = {}
        return self.handle_tool_use(state)

    def llm_call(self, state: State):
        if state["args_missing_funcname"] != "":
            return "arg_assistant"
        elif self.tool.__name__ in state["tool_use"]:
            return "next_graph"
        else:
            return "assistant"

    def llm_call_to_end(self, state: State):
        if state["args_missing_funcname"] != "":
            return "arg_assistant"
        elif self.tool.__name__ in state["tool_use"]:
            return END
        else:
            return "assistant"

    def tools_condition_edge(self, state: State):
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
            return "arg_assistant"
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return "human_feedback"

    def handle_tool_use(self, state, missing_message=""):
        if missing_message.strip() != "":
            return {"messages": self.get_user_input(missing_message, state["args_missing_funcname"], state["tool_calls_args"]), "args_missing_funcname": state["args_missing_funcname"]}
        for tool, prompt in self.querys.items():
            if tool not in state["tool_use"]:
                print(
                    f"now is {self.tool.__name__}  Agent----------------------------------------------------------------------------------------------------")
                return {"messages": self.get_user_input(prompt), "args_missing_funcname": state["args_missing_funcname"], "tool_calls_args": state["tool_calls_args"]}
        return {"messages": [], "args_missing_funcname": state["args_missing_funcname"], "tool_calls_args": state["tool_calls_args"]}

    def get_user_input(self, prompt, missing_funcname="", old_args={}):
        if missing_funcname != "":
            # print("prompt:", prompt)
            # prompt = prompt.split('Current arguments: ', 1)[0].strip()
            # args = prompt[1].strip()
            user_input = input(prompt)
            return [HumanMessage(content=f"我原本是要進行{missing_funcname}，並且之前提供過參數{old_args}，這是我根據 {prompt} 補上的參數:{user_input}")]
        user_input = input(prompt)
        return [HumanMessage(content=user_input)]

    def check_args_null_or_blank(self, json):
        for key, value in json.items():
            if value is None or (isinstance(value, str) and value.strip() == ""):
                return True
        return False

    def is_arg_complete(self, state: State):
        if state["args_missing_funcname"] != "":
            return "human_feedback"
        return "assistant"
