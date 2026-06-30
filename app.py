import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image, ImageOps
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
import pytesseract
import pandas as pd
from collections import Counter
import re

st.title("Feld-Extractor mit Auswertung")

uploaded_files = st.file_uploader(
    "PDFs hochladen",
    type="pdf",
    accept_multiple_files=True
)

def clean_text(text):
    text = text.strip()
    text = text.replace("\n", " ")
    text = re.sub(r"[^A-Za-zÄÖÜäöüß0-9.\- ]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def prepare_for_ocr(image):
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)

    # einfacher Kontrastfilter
    bw = gray.point(lambda x: 0 if x < 160 else 255, "1")
    return bw

if uploaded_files:
    images = []
    results = []

    for file in uploaded_files:
        pages = convert_from_bytes(file.read(), dpi=300)
        img = np.array(pages[0])

        # Koordinaten deines Feldes
        roi = img[900:1400, 2000:2300]

        cropped = Image.fromarray(roi)

        # 90° nach links drehen
        cropped = cropped.rotate(90, expand=True)

        # Bild speichern für PDF
        images.append({
            "datei": file.name,
            "bild": cropped
        })

        # OCR vorbereiten
        ocr_image = prepare_for_ocr(cropped)

        # OCR ausführen
        raw_text = pytesseract.image_to_string(
            ocr_image,
            lang="deu",
            config="--psm 7"
        )

        erkannt = clean_text(raw_text)

        results.append({
            "Datei": file.name,
            "OCR-Vorschlag": erkannt
        })

    st.subheader("Automatische OCR-Ergebnisse")

    df = pd.DataFrame(results)

    corrected_values = []

    for i, row in df.iterrows():
        st.write(f"**{row['Datei']}**")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.image(images[i]["bild"], caption="Ausschnitt", width=180)

        with col2:
            corrected = st.text_input(
                "Korrektur / bestätigter Wert",
                value=row["OCR-Vorschlag"],
                key=f"corrected_{i}"
            )
            corrected_values.append(clean_text(corrected))

    df["Bestätigter Wert"] = corrected_values

    st.subheader("Häufigkeiten")

    filtered_values = [
        value for value in corrected_values
        if value != ""
    ]

    counts = Counter(filtered_values)

    count_df = pd.DataFrame(
        counts.items(),
        columns=["Kürzel / Name", "Häufigkeit"]
    ).sort_values(by="Häufigkeit", ascending=False)

    st.dataframe(count_df, use_container_width=True)

    # PDF erstellen
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    for i, item in enumerate(images):
        img = item["bild"]

        w, h = img.size
        new_width = 150
        new_height = new_width * (h / w)

        c.drawString(50, y, f"Eintrag {i+1}: {item['datei']}")
        y -= 20

        c.drawString(220, y + 5, f"Auswertung: {corrected_values[i]}")

        c.drawInlineImage(
            img,
            50,
            y - new_height,
            width=new_width,
            height=new_height
        )

        y -= (new_height + 40)

        if y < 100:
            c.showPage()
            y = height - 50

    c.save()

    pdf_bytes = buffer.getvalue()

    # Vorschau fertige PDF
    st.subheader("Vorschau der fertigen PDF")

    pdf_preview = convert_from_bytes(pdf_bytes, dpi=150)

    for i, page in enumerate(pdf_preview):
        st.image(page, caption=f"Seite {i+1}", use_column_width=True)

    st.download_button(
        "PDF herunterladen",
        pdf_bytes,
        "ergebnis.pdf"
    )

    # CSV Download für Auswertung
    csv = count_df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "Auswertung als CSV herunterladen",
        csv,
        "auswertung.csv",
        "text/csv"
    )

