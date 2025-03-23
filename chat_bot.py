from typing import Annotated, List, Dict, Any, Optional
import datetime
import os
import re

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
from pdf_parser import search_invoices
from update_client import update_client_info, add_client, get_client_details


class State(TypedDict):
    messages: Annotated[list, add_messages]
    client_info: Optional[Dict[str, Any]]


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


class UpdateClientResponse(BaseModel):
    success: bool
    message: str
    client_name: str = ""
    updated_fields: Dict[str, str] = {}


class ClientInfoResponse(BaseModel):
    success: bool
    message: str
    client_name: str = ""
    client_address: str = ""
    previous_services: List[Dict[str, str]] = []
    invoice_history: List[Dict[str, str]] = []


@tool
def get_client_info(client_name: str) -> ClientInfoResponse:
    """Retrieve information about a client from previous invoices"""
    try:
        # Search for client in the invoice database
        results = search_invoices(client_name, n_results=3)

        if not results:
            return ClientInfoResponse(
                success=False,
                message=f"No information found for client: {client_name}",
            )

        # Get the most relevant result
        best_match = results[0]

        # Extract client information
        client_name = best_match.get("client_name", "")
        client_address = best_match.get("client_address", "")

        # Extract services from previous invoices
        previous_services = []
        for result in results:
            services = result.get("services", [])
            if isinstance(services, list):
                for service in services:
                    if (
                        isinstance(service, dict)
                        and "service_name" in service
                        and "service_price" in service
                    ):
                        # Filter out services that don't look like actual services
                        service_name = service["service_name"]

                        # Skip if it looks like an address, phone number, or other non-service text
                        if (
                            # Skip if it contains the user's address or phone number
                            not "277 shooters hill road" in service_name.lower()
                            and not "07946670601" in service_name
                            and not "dadekugbe@gmail.com" in service_name
                            and
                            # Skip if it contains common address patterns
                            not re.search(
                                r"\b(?:road|street|avenue|lane|way|london|se\d|sw\d|n\d|e\d|w\d)\b",
                                service_name,
                                re.IGNORECASE,
                            )
                            and
                            # Skip if it contains a phone number pattern
                            not re.search(
                                r"\b(?:0\d{10}|\d{5}\s?\d{6}|07\d{9})\b", service_name
                            )
                            and
                            # Skip if it contains an email pattern
                            not re.search(r"\S+@\S+\.\S+", service_name)
                            and
                            # Skip if it contains common non-service text
                            not re.search(
                                r"invoice|date|utr|account|bank|sort|code|iban|swift",
                                service_name,
                                re.IGNORECASE,
                            )
                            and
                            # Skip if it's too long to be a service name
                            len(service_name.split()) < 10
                            and
                            # Skip if it's just a number or very short text
                            len(service_name) > 5
                            and
                            # Skip if it's just the invoice number repeated
                            not re.match(
                                r"^INVOICE\s+\d+$", service_name, re.IGNORECASE
                            )
                        ):
                            # Only include if it looks like a real service
                            # Check if it contains words that suggest it's a service
                            if (
                                re.search(
                                    r"\b(?:gig|performance|recording|session|piano|quartet|trio|music|band|choir|concert|event|solo)\b",
                                    service_name,
                                    re.IGNORECASE,
                                )
                                or
                                # Or if it contains a venue name
                                re.search(
                                    r"\b(?:park chinois|sky garden|quaglinos|wardour|peninsula|maison|estelle)\b",
                                    service_name,
                                    re.IGNORECASE,
                                )
                                or
                                # Or if it contains a date followed by a venue or event type
                                re.search(
                                    r"\d{1,2}[/-\.]\d{1,2}[/-\.]\d{2,4}\s+.*(?:gig|performance|piano|quartet|trio|band|choir)",
                                    service_name,
                                    re.IGNORECASE,
                                )
                                or
                                # Or if it starts with a date format like DD.MM.YY or DD.MM.YYYY
                                re.search(
                                    r"^\d{1,2}\.\d{1,2}\.\d{2,4}\s+",
                                    service_name,
                                )
                            ):
                                previous_services.append(service)

        # Extract invoice history
        invoice_history = []
        for result in results:
            invoice_history.append(
                {
                    "invoice_number": result.get("invoice_number", ""),
                    "invoice_date": result.get("invoice_date", ""),
                    "invoice_amount": result.get("invoice_amount", ""),
                }
            )

        return ClientInfoResponse(
            success=True,
            message=f"Found information for client: {client_name}",
            client_name=client_name,
            client_address=client_address,
            previous_services=previous_services,
            invoice_history=invoice_history,
        )
    except Exception as e:
        return ClientInfoResponse(
            success=False,
            message=f"Error retrieving client information: {str(e)}",
        )


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
def update_client(
    client_name: str,
    email: str = None,
    address: str = None,
    phone: str = None,
    notes: str = None,
) -> UpdateClientResponse:
    """
    Update client information in the database or add a new client.

    Args:
        client_name: The name of the client to update
        email: Client email address
        address: Client address
        phone: Client phone number
        notes: Additional notes about the client

    Returns:
        UpdateClientResponse: Result of the update operation
    """
    # Collect updates from provided parameters
    updates = {}
    if email:
        updates["email"] = email
    if address:
        updates["client_address"] = address
    if phone:
        updates["phone"] = phone
    if notes:
        updates["notes"] = notes

    # Check if client exists
    client_exists = len(search_invoices(client_name, n_results=1)) > 0

    if client_exists:
        # Update existing client
        result = update_client_info(client_name, updates, verbose=False)
    else:
        # Add new client
        # Convert updates to client_info format
        client_info = {}
        if "email" in updates:
            client_info["email"] = updates["email"]
        if "client_address" in updates:
            client_info["address"] = updates["client_address"]
        if "phone" in updates:
            client_info["phone"] = updates["phone"]
        if "notes" in updates:
            client_info["notes"] = updates["notes"]

        result = add_client(client_name, client_info, verbose=False)

    # Convert result to UpdateClientResponse
    return UpdateClientResponse(
        success=result["success"],
        message=result["message"],
        client_name=result.get("client_name", ""),
        updated_fields=updates,
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


def extract_client_names(text: str) -> List[str]:
    """
    Extract potential client names from the user's input.
    This is a simple implementation that looks for capitalized words and common client names.
    """
    # List of known clients from our database
    known_clients = [
        "ALR Music",
        "ALR",
        "Warner Music",
        "Peninsula",
        "Park Chinois",
        "Sky Garden",
        "Quaglinos",
        "Wardour Street",
        "Maison Estelle",
    ]

    # Check for known clients first
    found_clients = []
    for client in known_clients:
        if re.search(r"\b" + re.escape(client) + r"\b", text, re.IGNORECASE):
            found_clients.append(client)

    # If no known clients found, look for capitalized words that might be names
    if not found_clients:
        # Look for sequences of capitalized words (potential names)
        potential_names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        found_clients = potential_names

    return found_clients


def router(state: State):
    """
    Router node that checks if client names are mentioned and retrieves client information.
    """
    # Get the last user message
    messages = state["messages"]
    last_user_message = None

    for message in reversed(messages):
        # Check if message is a dictionary with a 'role' key
        if (
            isinstance(message, dict)
            and "role" in message
            and message["role"] == "user"
        ):
            last_user_message = message["content"]
            break
        # Check if message is a LangChain message object with a 'type' attribute
        elif hasattr(message, "type") and message.type == "human":
            last_user_message = message.content
            break

    if not last_user_message:
        return {"messages": state["messages"], "client_info": None}

    # Extract potential client names
    client_names = extract_client_names(last_user_message)

    # If client names found, retrieve client information
    if client_names:
        client_info = get_client_info(client_names[0])
        if client_info.success:
            return {
                "messages": state["messages"],
                "client_info": client_info.model_dump(),
            }

    # No client information found
    return {"messages": state["messages"], "client_info": None}


tool = TavilySearchResults(max_results=2)
tools = [tool, get_client_info, generate_invoice, send_invoice_email, update_client]
llm = ChatAnthropic(model="claude-3-7-sonnet-20250219")
parser = PydanticOutputParser(pydantic_object=Invoice)

llm_with_tools = llm.bind_tools(tools)


def chatbot(state: State):
    # Get client information if available
    client_info = state.get("client_info")

    # Create the base system prompt
    system_prompt = """You are a helpful Invoice assistant. Be concise and clear in your responses.
        
You can:
1. Generate invoices using the generate_invoice tool
2. Send invoices via email using the send_invoice_email tool
3. Retrieve client information using the get_client_info tool
4. Update client information using the update_client tool

When a user asks to create an invoice, collect all necessary information and use the generate_invoice tool.
Only use the send_invoice_email tool when specifically asked to send an invoice.

If a user provides new client information (like an email address or phone number), use the update_client tool to save this information for future use. This way, you'll remember client details and won't need to ask for them again in future conversations.
"""

    # Add client information to the system prompt if available
    if client_info:
        client_name = client_info.get("client_name", "")
        client_address = client_info.get("client_address", "")
        previous_services = client_info.get("previous_services", [])
        invoice_history = client_info.get("invoice_history", [])

        client_info_prompt = f"""
I notice you're talking about {client_name}. Here's what I know about this client:

Client Name: {client_name}
Client Address: {client_address}

"""

        if previous_services:
            client_info_prompt += "Previous Services:\n"
            for service in previous_services[:3]:  # Limit to 3 services
                service_name = service.get("service_name", "")
                service_price = service.get("service_price", "")
                client_info_prompt += f"- {service_name}: {service_price}\n"
            client_info_prompt += "\n"

        if invoice_history:
            client_info_prompt += "Recent Invoices:\n"
            for invoice in invoice_history[:3]:  # Limit to 3 invoices
                invoice_number = invoice.get("invoice_number", "")
                invoice_date = invoice.get("invoice_date", "")
                invoice_amount = invoice.get("invoice_amount", "")
                client_info_prompt += (
                    f"- Invoice #{invoice_number} ({invoice_date}): {invoice_amount}\n"
                )
            client_info_prompt += "\n"

        client_info_prompt += (
            "Use this information when generating a new invoice for this client.\n"
        )

        # Append client information to the system prompt
        system_prompt += client_info_prompt

    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt + "\n{format_instructions}",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    messages = prompt.format_messages(messages=state["messages"])
    return {"messages": [llm_with_tools.invoke(messages)], "client_info": client_info}


graph_builder.add_node("router", router)
graph_builder.add_node("chatbot", chatbot)

tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

# Set the entry point to the router
graph_builder.set_entry_point("router")

# Add edge from router to chatbot
graph_builder.add_edge("router", "chatbot")

# Add conditional edges from chatbot
graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)

# Any time a tool is called, we return to the chatbot to decide the next step
graph_builder.add_edge("tools", "chatbot")

memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "1"}}


def stream_graph_updates(user_input: str):
    events = graph.stream(
        {"messages": [{"role": "user", "content": user_input}], "client_info": None},
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
