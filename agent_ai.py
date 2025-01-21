import json
import datetime
from openai import OpenAI
from createpdf import createpdf
from sendMail import send_email
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


class InvoiceAgent:
    def __init__(self):
        pass

    def extract_invoice_details(self, prompt):
        """
        Use OpenAI's GPT to extract invoice details from the user's prompt.
        """
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            """You are an AI assistant that extracts invoice details from user prompts.\n
                            Services need to be a list of objects with description and price in GBP\n
                            {"services": [{"description": "Design", "price": 100}]}.\n
                            Return the data as a valid JSON object. Ensure that all lists and values are JSON-compliant."""
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error during OpenAI API call: {e}")
            return None

    def parse_extracted_details(self, extracted_text):
        """
        Parse the extracted details into a structured format.
        """
        try:
            # Strip the backticks and clean the text
            extracted_text = extracted_text.strip("```").strip()

            # Replace Python tuple syntax with JSON-compatible list syntax
            extracted_text = (
                extracted_text.replace("(", "[").replace(")", "]").replace("json", "")
            )

            print("Cleaned JSON String:", extracted_text)  # For debugging

            # Parse the cleaned JSON string
            details = json.loads(extracted_text)
            return details
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return {}

    def generate_invoice(self, details):
        """
        Generate an invoice using the extracted details.
        """
        try:
            today = datetime.date.today()
            formatted_date = today.strftime("%d-%m-%Y")

            # Default values
            invoice_number = details.get("invoice_number", "INV-001")
            date_input = details.get("date", formatted_date)
            user_details = details.get("user_details", "Your Company Name")
            account_details = details.get("account_details", "Bank: XYZ, Acc: 123456")
            client_name = details.get("client_name", "John Doe")
            client_address = details.get("client_address", "123 Main St, City")
            client_email = details.get("client_email", "john.doe@example.com")
            pdf_name = details.get("pdf_name", "invoice") + ".pdf"

            # Parse services
            services = details.get("services", [])
            if not isinstance(services, list):
                print("Error: 'services' should be a list of dictionaries.")
                services = []

            # Calculate total
            total_price = sum(item["price"] for item in services)
            total_cost = f"{total_price}"

            # Generate PDF
            pdf_path = createpdf(
                invoice_number,
                date_input,
                user_details,
                account_details,
                client_name,
                client_address,
                services,
                total_cost,
                pdf_name,
            )

            return pdf_path, client_email

        except Exception as e:
            print(f"Error generating invoice: {e}")
            return None, None

    def run(self, prompt):
        """
        Run the AI agent to generate and send an invoice based on the user's prompt.
        """
        try:
            # Step 1: Extract details from the prompt
            extracted_text = self.extract_invoice_details(prompt)
            if not extracted_text:
                print("Failed to extract details from prompt.")
                return

            print("Extracted Details:", extracted_text)

            # Step 2: Parse the extracted details
            details = self.parse_extracted_details(extracted_text)
            if not details:
                print("Failed to parse extracted details.")
                return

            print("Parsed Details:", details)

            # Step 3: Generate the invoice
            pdf_path, client_email = self.generate_invoice(details)
            if not pdf_path or not client_email:
                print("Failed to generate invoice.")
                return

            print(f"Invoice generated at: {pdf_path}")

            # Step 4: Send the invoice via email
            email_message = """ 
            Hi,

            Please find attached the invoice.

            Regards,
            InvoiceAgent
            """
            send_email(email_message, pdf_path, client_email)
            print("Invoice sent successfully!")

        except Exception as e:
            print(f"Error running the agent: {e}")


# Example usage
if __name__ == "__main__":
    agent = InvoiceAgent()
    prompt = """
        Generate an invoice for John Doe. 
        Client email: dadekugbe@gmail.com 
        Services: Design: 100, Development: 200, Testing: 50.
        """
    agent.run(prompt)
