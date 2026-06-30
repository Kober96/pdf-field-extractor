import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io

st.title("Feld-Extractor")

uploaded_files = st.file_uploader("PDFs hochladen", type="pdf", accept_multiple_files=True)

if uploaded_files:
    images = []

    for file in uploaded_files:
        pages = convert_from_bytes(file.read(), dpi=300)
        img = np.array(pages[0])

        roi = img[900:1400, 2000:2300]

        cropped = Image.fromarray(roi)
        cropped = cropped.rotate(90, expand=True)

        images.append(cropped)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    for i, img in enumerate(images):
        w, h = img.size
        new_width = 150
        new_height = new_width * (h / w)

        c.drawString(50, y, f"Eintrag {i+1}")
        y -= 20

        c.drawInlineImage(img, 50, y - new_height, width=new_width, height=new_height)

        y -= (new_height + 20)

        if y < 100:
            c.showPage()
            y = height - 50

    c.save()

    # ✅ PDF Bytes holen
    pdf_bytes = buffer.getvalue()

    # ✅ Vorschau
    st.subheader("Vorschau")

    pdf_preview = convert_from_bytes(pdf_bytes, dpi=150)

    for i, page in enumerate(pdf_preview):
        st.image(page, caption=f"Seite {i+1}", use_column_width=True)

    # ✅ EINMALIGER Download-Button (wichtig!)
    st.download_button("PDF herunterladen", pdf_bytes, "ergebnis.pdf")

