from typing import Annotated, List, Dict, Any, Optional
import datetime
import os

from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.memory import MemorySaver
from typing_extensions import TypedDict
from langchain_core.tools import tool

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser

from createpdf import createpdf
from sendMail import send_email


class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)


class Invoice(BaseModel):
    invoice_number: str
    service_details: str
    service_price: float
    client_name: str
    client_address: str
    client_email: str


class InvoiceResponse(BaseModel):
    success: bool
    message: str
    pdf_path: str | None = None


class EmailResponse(BaseModel):
    success: bool
    message: str


@tool
def generate_invoice(invoice_data: Invoice) -> InvoiceResponse:
    """Generate an invoice PDF based on the provided data"""
    try:
        today = datetime.date.today()
        formatted_date = today.strftime("%d-%m-%Y")

        # Format the services for createpdf
        services = [
            {
                "description": invoice_data.service_details,
                "price": invoice_data.service_price,
            }
        ]

        # Calculate total
        total_cost = str(invoice_data.service_price)

        # Generate PDF name
        pdf_name = "invoice_" + invoice_data.invoice_number + ".pdf"

        # Get user details from environment or use defaults
        user_details = os.environ.get("USER_DETAILS", "Your Company Name\nYour Address")
        account_details = os.environ.get("ACCOUNT_DETAILS", "Bank: XYZ, Acc: 123456")

        pdf_path = createpdf(
            invoice_number=invoice_data.invoice_number,
            date_input=formatted_date,
            user_details=user_details,
            account_details=account_details,
            client_name=invoice_data.client_name,
            client_address=invoice_data.client_address,
            services=services,
            total_cost=total_cost,
            pdf_name=pdf_name,
        )

        return InvoiceResponse(
            success=True,
            message="Invoice generated successfully. Please review the PDF at "
            + pdf_path
            + " before sending.",
            pdf_path=pdf_path,
        )
    except Exception as e:
        return InvoiceResponse(
            success=False, message=f"Failed to generate invoice: {str(e)}"
        )


@tool
def send_invoice_email(
    pdf_path: str, client_email: str, custom_message: str = None
) -> EmailResponse:
    """Send the generated invoice to the client via email"""
    try:
        # Use custom message if provided, otherwise use default
        message = (
            custom_message
            if custom_message
            else """
        Hi,

        Please find attached the invoice.

        Regards,
        Daniel Adekugbe
        """
        )

        send_email(message, pdf_path, client_email)

        return EmailResponse(
            success=True, message=f"Invoice successfully sent to {client_email}"
        )
    except Exception as e:
        return EmailResponse(success=False, message=f"Failed to send email: {str(e)}")


tool = TavilySearchResults(max_results=2)
tools = [tool, generate_invoice, send_invoice_email]
llm = ChatAnthropic(model="claude-3-7-sonnet-20250219")
parser = PydanticOutputParser(pydantic_object=Invoice)

llm_with_tools = llm.bind_tools(tools)


def chatbot(state: State):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a helpful Invoice assistant. Be concise and clear in your responses.
        
        You can:
        1. Generate invoices using the generate_invoice tool
        2. Send invoices via email using the send_invoice_email tool
        
        When a user asks to create an invoice, collect all necessary information and use the generate_invoice tool.
        Only use the send_invoice_email tool when specifically asked to send an invoice.
        
        {format_instructions}""",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

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
