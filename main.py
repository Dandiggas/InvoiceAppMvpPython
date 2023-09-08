from fpdf import FPDF, XPos, YPos
import datetime
import os
from sendMail import send_email
from createpdf import createpdf

def main():

    today = datetime.date.today()
    formatted_date = today.strftime("%d-%m-%Y")


    # Input user and invoice details
    invoice_number = input("Enter invoice number: ")
    date_input = input(f"Enter date (or press enter for today's date {formatted_date}): ")
    if not date_input:
        date_input = formatted_date

    user_details = input("Enter your details: ")
    account_details = input("Enter your account details: ")

    # Input client details
    client_name = input("Enter client name: ")
    client_address = input("Enter client address: ")
    client_email = input("Enter client email: ")

    #Input multiple services 

    services = []
    while True:
        service_desc = input("Enter service description(or press enter to finish): ")
        if not service_desc:
            break

        service_price = float(input("Enter service price: "))
        services.append((service_desc, service_price))

    #Calculate total 
    total_price = sum(price for _, price in services)
    total_cost = f"{total_price}"
    

    pdf_path = createpdf(invoice_number, date_input, user_details, account_details, client_name, client_address, services, total_cost, pdf_name="tuto1.pdf")

    email_message = """ 
    Hi,

    Please find attached the invoice.

    Regards,
    Daniel Adekugbe
    """
    print("Please check invoice")
    invoice_check = input("Would you like me to email the invoice to the client, yes or no? ") 
    invoice_check.strip()   
    if invoice_check == "yes":
        send_email(email_message, pdf_path, client_email)
    else:
        ("Please recreate invoice")
        
    return f"thank you for using this app"








if __name__ == "__main__":
    print(main())