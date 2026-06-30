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

        # 👉 Koordinaten
        roi = img[900:1300, 2200:2400]

        # 👉 in PIL umwandeln
        cropped = Image.fromarray(roi)

        # ✅ 90° nach links drehen
        cropped = cropped.rotate(90, expand=True)

        images.append(cropped)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    for i, img in enumerate(images):

        # ✅ Größe automatisch proportional (halb so breit)
        w, h = img.size
        new_width = 150   # vorher 300 → jetzt halb
        new_height = new_width * (h / w)

        c.drawString(50, y, f"Eintrag {i+1}")
        y -= 20

        # ✅ korrekt gedreht + skaliert einfügen
        c.drawInlineImage(img, 50, y - new_height, width=new_width, height=new_height)

        y -= (new_height + 20)

        if y < 100:
            c.showPage()
            y = height - 50

    c.save()

    st.download_button("PDF herunterladen", buffer.getvalue(), "ergebnis.pdf")

