from fpdf import FPDF
import qrcode
import os
import tempfile

from .models import Ticket

def generate_pdf_ticket(ticket:Ticket, template_path=None):
    """
    Generate a PDF ticket for the given Ticket instance.
    """
    # Create a QR code from the ticket ID
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(ticket.id)
    qr.make(fit=True)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
        qr_image_path = temp_file.name
        qr_image = qr.make_image(fill_color="black", back_color="white")
        qr_image.save(qr_image_path)

    try:
        # Create the PDF
        pdf = FPDF(unit="cm", format=(21.0, 8.5))  # Standard event ticket size
        #pdf.set_display_mode(zoom="default", layout="single") # Set display mode to default and layout to single
        pdf.set_margins(0.5, 0.5)  # Set margins 
        pdf.set_auto_page_break(auto=True, margin=0.2)  # Enable auto page break with a margin of 0.2 cm
        # Set font for the PDF
        font = "Helvetica"  # Default font
        pdf.set_font(font)

        # If a template is provided, use it as the canvas
        if template_path:
            if os.path.exists(template_path):
                try:
                    pdf.set_page_background(template_path)
                except Exception as e:
                    print(f"Error loading template image: {e}")
            else:
                pdf.set_page_background(None)  # Proceed without a template if not found
                print("Template file not found. Proceeding without it.")
        
        pdf.add_page()
        borders = 0
        
        # Add Event Title
        pdf.set_font(font, size=18, style='B')
        pdf.cell(14, 0.65, text=f"{ticket.event.name}", border=borders, align='L')
        
        # Add Ticket Details in a Layout
        pdf.set_font(font, size=15)
        pdf.ln(1.25)  # Move to the next line

        pdf.cell(4.0, 0.6, text="Start:", border=borders, align='L')
        pdf.cell(5.0, 0.6, text=f"{ticket.event.start_time.strftime('%H:%M %d.%m.%Y')}", border=borders, align='L')

        pdf.cell(2.5, 0.6, text="Duration:", border=borders, align='R')
        pdf.cell(2.5, 0.6, text=f"{ticket.event.get_duration_minutes()} min", border=borders, align='L')

        pdf.ln(0.75)  # Move to the next line
        pdf.cell(4.0, 0.6, text="Venue:", border=borders, align='L')
        pdf.cell(10.0, 0.6, text=f"{ticket.event.location.get_address()}", border=borders,  align='L')
        
        pdf.ln(0.75)  # Move to the next line
        pdf.cell(4.0, 0.6, text="Seat Number:", border=borders, align='L')
        pdf.cell(2.0, 0.6, text=f"{ticket.seat}", border=borders,  align='L')

        pdf.ln(1.25)  # Move to the next line
        pdf.cell(4.0, 0.6, text="Price Class:", border=borders, align='L')
        pdf.cell(4.0, 0.6, text=f"{ticket.price_class.name}", border=borders, align='L')        
        pdf.ln(0.75)  # Move to the next line
        pdf.cell(4.0, 0.6, text="Price:", border=borders, align='L')
        pdf.cell(4.0, 0.6, text=f"{ticket.price_class.price.amount} EUR", border=borders, align='L')


        # render ticket footer
        pdf.set_font(font, size=10)
        pdf.ln(2.25)  # Move to the next line
        pdf.cell(9.0, 0.4, text=f"{ticket.id}", border=borders, align='L')

        # vertical line to divide ticket into two parts
        pdf.line(14.75, 0.1, 14.75, 8.4)

        # Add QR Code to the Bottom Right
        pdf.image(qr_image_path, x=15.5, y=0.0, w=5, h=5)  # Adjust size and position of the QR code

        pdf.set_font(font, size=8)
        pdf.set_y(5.2)  # Set x position for ticket check side
        pdf.set_x(15.2)  # Set x position for ticket check side
        pdf.cell(5.5, 0.5, text=f"{ticket.event.name}", border=borders, align='C', new_y="NEXT", new_x="LEFT")
        pdf.cell(5.5, 0.5, text=f"{ticket.event.start_time.strftime('%H:%M %d.%m.%Y')} {ticket.event.get_duration_minutes()} min", border=borders, align='C', new_y="NEXT", new_x="LEFT")
        pdf.cell(5.5, 0.5, text=f"{ticket.seat}", border=borders, align='C', new_y="NEXT", new_x="LEFT")
        pdf.cell(5.5, 0.5, text=f"{ticket.event.location.get_address()}", border=borders, align='C', new_y="NEXT", new_x="LEFT")
        
        # Save the PDF
        # If save_path is provided, create directory if it does not exist
        #if save_path:
        #    os.makedirs(save_path, exist_ok=True)
        #    pdf_file_name = os.path.join(save_path, f"ticket_{ticket.id}.pdf")
        #else:
        #    pdf_file_name = f"ticket_{ticket.id}.pdf"

        # Save the PDF
        #pdf.output(pdf_file_name)
        #print(f"Ticket generated: {pdf_file_name}")

    finally:
        # Clean up the temporary QR code image
        if os.path.exists(qr_image_path):
            os.remove(qr_image_path)

    return pdf