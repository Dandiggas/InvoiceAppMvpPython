import tkinter as tk
from tkinter import messagebox, scrolledtext
from createpdf import createpdf
from sendMail import send_email
import datetime


def preview_invoice():
    # Get inputs from Tkinter
    invoice_number = invoice_number_entry.get()
    date_input = (
        date_entry.get()
        if date_entry.get()
        else datetime.date.today().strftime("%d-%m-%Y")
    )
    user_details = user_details_entry.get()
    account_details = account_details_entry.get()
    client_name = client_name_entry.get()
    client_address = client_address_entry.get()
    client_email = client_email_entry.get()
    pdf_name = pdf_name_entry.get() + ".pdf"

    # Get services and prices
    services = []
    for service_frame in service_frames:
        service_desc = service_frame.children["service_desc_entry"].get()
        service_price = float(service_frame.children["service_price_entry"].get())
        services.append((service_desc, service_price))

    # Ensure the invoice preview text widget is editable
    invoice_preview_text.config(state=tk.NORMAL)
    invoice_preview_text.delete("1.0", tk.END)

    # Construct the preview text
    preview_text = f"Invoice Number: {invoice_number}\nDate: {date_input}\n\nUser Details:\n{user_details}\nAccount Details:\n{account_details}\n\nClient Name: {client_name}\nClient Address:\n{client_address}\n\nServices:\n"
    for desc, price in services:
        preview_text += f"{desc}: ${price}\n"
    preview_text += f"\nTotal Cost: ${sum(price for _, price in services)}"

    # Update the text widget with the preview text
    invoice_preview_text.insert(tk.END, preview_text)
    invoice_preview_text.config(state=tk.DISABLED)

    send_email_button.config(state=tk.NORMAL)


def generate_pdf():
    # Gather data from entry widgets
    invoice_number = invoice_number_entry.get()
    date_input = (
        date_entry.get()
        if date_entry.get()
        else datetime.date.today().strftime("%d-%m-%Y")
    )
    user_details = user_details_entry.get()
    account_details = account_details_entry.get()
    client_name = client_name_entry.get()
    client_address = client_address_entry.get()
    client_email = client_email_entry.get()
    pdf_name = pdf_name_entry.get() + ".pdf"

    # Gather services and prices
    services = []
    for service_frame in service_frames:
        service_desc = service_frame.children["service_desc_entry"].get()
        service_price = float(service_frame.children["service_price_entry"].get())
        services.append((service_desc, service_price))

    # Calculate total price
    total_price = sum(price for _, price in services)

    # Create the PDF
    try:
        createpdf(
            invoice_number,
            date_input,
            user_details,
            account_details,
            client_name,
            client_address,
            services,
            str(total_price),
            pdf_name,
        )
        messagebox.showinfo("Success", "PDF generated successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create PDF: {e}")


def send_invoice():
    invoice_number = invoice_number_entry.get()
    date_input = (
        date_entry.get()
        if date_entry.get()
        else datetime.date.today().strftime("%d-%m-%Y")
    )
    user_details = user_details_entry.get()
    account_details = account_details_entry.get()
    client_name = client_name_entry.get()
    client_address = client_address_entry.get()
    client_email = client_email_entry.get()
    pdf_name = pdf_name_entry.get() + ".pdf"

    # Fetch services and prices
    services = []
    for service_frame in service_frames:
        service_desc = service_frame.children["service_desc_entry"].get()
        service_price = float(service_frame.children["service_price_entry"].get())
        services.append((service_desc, service_price))

    # Generate PDF
    total_price = sum(price for _, price in services)
    pdf_path = createpdf(
        invoice_number,
        date_input,
        user_details,
        account_details,
        client_name,
        client_address,
        services,
        f"{total_price}",
        pdf_name,
    )

    # Send email
    email_message = """ 
    Hi,

    Please find attached the invoice.

    Regards,
    Daniel Adekugbe
    """
    send_email(email_message, pdf_path, client_email)
    messagebox.showinfo("Success", "Invoice sent successfully!")


def add_service_frame():
    service_frame = tk.Frame(service_container)
    service_frame.pack(fill="x", expand=True)

    tk.Label(service_frame, text="Service Description:").pack(side="left")
    tk.Entry(service_frame, name="service_desc_entry").pack(side="left")

    tk.Label(service_frame, text="Price:").pack(side="left")
    tk.Entry(service_frame, name="service_price_entry").pack(side="left")

    service_frames.append(service_frame)


def labeled_entry(parent, label_text, **kwargs):
    frame = tk.Frame(parent)
    frame.pack(fill="x", expand=True)
    tk.Label(frame, text=label_text).pack(side="left")
    entry = tk.Entry(frame, **kwargs)
    entry.pack(side="right", expand=True, fill="x")
    return entry


# Tkinter window setup
root = tk.Tk()
root.title("Invoice Generator")

# Entry widgets with labels
invoice_number_entry = labeled_entry(root, "Invoice Number:")
date_entry = labeled_entry(root, "Date (dd-mm-yyyy):")
user_details_entry = labeled_entry(root, "Your Details:")
account_details_entry = labeled_entry(root, "Your Account Details:")
client_name_entry = labeled_entry(root, "Client Name:")
client_address_entry = labeled_entry(root, "Client Address:")
client_email_entry = labeled_entry(root, "Client Email:")
pdf_name_entry = labeled_entry(root, "PDF Name (without extension):")

# Service entries container
service_container = tk.Frame(root)
service_container.pack(fill="both", expand=True)
service_frames = []

# Invoice preview text area
invoice_preview_text = scrolledtext.ScrolledText(root, state=tk.DISABLED, height=10)
invoice_preview_text.pack(fill="both", expand=True)

# Buttons
add_service_button = tk.Button(root, text="Add Service", command=add_service_frame)
add_service_button.pack()

preview_invoice_button = tk.Button(
    root, text="Preview Invoice", command=preview_invoice
)
preview_invoice_button.pack()

generate_pdf_button = tk.Button(root, text="Generate PDF", command=generate_pdf)
generate_pdf_button.pack()

send_email_button = tk.Button(
    root, text="Send Invoice", command=send_invoice, state=tk.DISABLED
)
send_email_button.pack()

# Start Tkinter event loop
root.mainloop()
