import ssl
import smtplib
from email.message import EmailMessage
import os
from createpdf import createpdf
import certifi


def send_email(message, pdf_path, client_email):
    email_message = """ 
    Hi,

    Please find attached the invoice.

    Regards,
    Daniel Adekugbe
    """

    host = "smtp.gmail.com"
    port = 465

    username = os.environ.get("USERNAMEEMAIL")
    password = os.environ.get("PASSWORD")

    receiver = client_email  # Replace with the recipient's email address
    subject = "Invoice"  # Email subject

    context = ssl.create_default_context(cafile=certifi.where())

    email = EmailMessage()
    email.set_content(message)
    email["Subject"] = subject
    email["From"] = username
    email["To"] = receiver

    with open(pdf_path, "rb") as pdf_file:
        pdf_data = pdf_file.read()
        email.add_attachment(
            pdf_data, maintype="application", subtype="pdf", filename="invoice.pdf"
        )

    with smtplib.SMTP_SSL(host, port, context=context) as server:
        server.login(username, password)
        server.send_message(email)

    print("Email sent successfully")
