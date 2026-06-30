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

        # 👉 HIER KOORDINATEN ANPASSEN
        roi = img[1200:1400, 2000:2200]

        cropped = Image.fromarray(roi)
        images.append(cropped)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    for i, img in enumerate(images):
        temp = io.BytesIO()
        img.save(temp, format="PNG")

        c.drawString(50, y, f"Eintrag {i+1}")
        y -= 20

        c.drawInlineImage(Image.open(temp), 50, y - 100, width=300, height=100)

        y -= 150

        if y < 100:
            c.showPage()
            y = height - 50

    c.save()

    st.download_button("PDF herunterladen", buffer.getvalue(), "ergebnis.pdf")
