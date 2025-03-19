from typing import Annotated

from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.memory import MemorySaver
from typing_extensions import TypedDict

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
# from langchain_core.tools import tool
from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser


class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

# @tool
# def multiply(a: int, b: int) -> int:
#     """Multiply two numbers"""
#     return a * b

class Invoice(BaseModel):
    invoice_number: str
    service_details: str
    service_price: float
    client_name: str
    client_address: str
    client_email: str


tool = TavilySearchResults(max_results=2)
tools = [tool]
llm = ChatAnthropic(model="claude-3-7-sonnet-20250219")
parser = PydanticOutputParser(pydantic_object=Invoice)

llm_with_tools = llm.bind_tools(tools)


def chatbot(state: State):

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful Invoice assistant. Be concise and clear in your responses.\n {format_instructions}"),
        MessagesPlaceholder(variable_name="messages"),
    ]).partial(format_instructions=parser.get_format_instructions())

    messages = prompt.format_messages(messages=state["messages"])
    return {"messages": [llm_with_tools.invoke(messages)]}


graph_builder.add_node("chatbot", chatbot)

tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)
# Any time a tool is called, we return to the chatbot to decide the next step
graph_builder.add_edge("tools", "chatbot")
graph_builder.set_entry_point("chatbot")
memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "1"}}


def stream_graph_updates(user_input: str):
    events = graph.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
        stream_mode="values",
    )
    for event in events:
        event["messages"][-1].pretty_print()


while True:
    try:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        stream_graph_updates(user_input)
    except:
        # fallback if input() is not available
        user_input = "What do you know about LangGraph?"
        print("User: " + user_input)
        stream_graph_updates(user_input)
        break
