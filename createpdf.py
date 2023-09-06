from fpdf import FPDF, XPos, YPos
import os


def createpdf(invoice_number, date_input, user_details, account_details, client_name, client_address, services, total_cost, pdf_name="tuto1.pdf"):
    LMARGIN = 10
    CENTER = 105  # Halfway = 210 / 2
    RMARGIN = 200
    LINE_HEIGHT = 10

    class MyPDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 16)
            self.cell(0, 10, "Invoice", 0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
        def footer(self):
            self.set_y(-15)
            self.set_font("Arial", "I", 8)
            self.cell(0, 10, f"Page {self.page_no()}", 0, new_x=XPos.RIGHT, new_y=YPos.TOP)

    pdf = MyPDF("P", "mm", "Letter")
    pdf.add_page()

    pdf.set_font("Arial", "", 12)

    # Invoice Details Section
    pdf.ln(10)
    pdf.cell(40, LINE_HEIGHT, f"Invoice #: {invoice_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
    pdf.cell(40, LINE_HEIGHT, f"Date: {date_input}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    # User Details Section
    pdf.ln(10)
    pdf.cell(40, LINE_HEIGHT, f"My Details: {user_details}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    # Account Details Section
    pdf.ln(10)
    pdf.cell(40, LINE_HEIGHT, f"Account Details: {account_details}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    # Client Details Section
    pdf.ln(10)
    pdf.cell(40, LINE_HEIGHT, f"Client Name: {client_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
    pdf.cell(40, LINE_HEIGHT, f"Client Address: {client_address}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    # Line separator
    pdf.ln(10)
    pdf.line(LMARGIN, pdf.get_y(), RMARGIN, pdf.get_y())

    # Services Table
    pdf.ln(10)
    pdf.cell(100, LINE_HEIGHT, "Service", border=1, align="C")
    pdf.cell(40, LINE_HEIGHT, "Price", border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    for serve, price in services:
        pdf.cell(100, LINE_HEIGHT, serve, border=1)
        pdf.cell(40, LINE_HEIGHT, f"£{price}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

    # Total Cost
    pdf.cell(100, LINE_HEIGHT, "Total", border=1)
    pdf.cell(40, LINE_HEIGHT, f"£{total_cost}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

    desktop_path = os.path.expanduser("~/Desktop")
    pdf_path = os.path.join(desktop_path, "tuto1.pdf")
    pdf.output(pdf_path)

    print("Your invoice has been created")

    return pdf_path