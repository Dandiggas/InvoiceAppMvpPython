from fpdf import FPDF, XPos, YPos
import os


def createpdf(invoice_number, date_input, user_details, account_details, client_name, client_address, services, total_cost, pdf_name="tuto1.pdf"):
    pdf = FPDF('P', 'mm', 'Letter')
    pdf.add_page()
    pdf.set_font("helvetica", "", 16)
    pdf.cell(0, 10, "Invoice", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(40, 10, f"{invoice_number}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(40, 10, f"{date_input}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(40, 10, f"{user_details}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(40, 10, f"{account_details}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(40, 10, f"{client_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(40, 10, f"{client_address}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    for serve, price in services:
        pdf.cell(40, 10, f"{serve} £{price}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(40, 10, f"{total_cost}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    desktop_path = os.path.expanduser("~/Desktop")
    pdf_path = os.path.join(desktop_path, "tuto1.pdf")
    pdf.output(pdf_path)

    print("Your invoice has been created")

    return pdf_path