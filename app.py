import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
import pandas as pd
from collections import Counter
import gc

st.title("Feld-Extractor mit manueller Auswertung")

uploaded_files = st.file_uploader(
    "PDFs hochladen",
    type="pdf",
    accept_multiple_files=True
)

# ✅ Sicherheitslimit (verhindert Absturz)
if uploaded_files and len(uploaded_files) > 15:
    st.error("Maximal 15 PDFs gleichzeitig laden")
    st.stop()

optionen = [
    "",
    "Andreas Bayer",
    "Frank Feißt",
    "Manuel Huber",
    "Patrick Schuler",
    "Stefan Lehmann",
    "Christian Wylegalla",
    "Günter Obert",
    "Markus Schnaitter",
    "Andere"
]

if uploaded_files:
    images = []
    values = []

    # ✅ PDFs mit reduzierter Auflösung laden (RAM FIX)
    for file in uploaded_files:
        pages = convert_from_bytes(file.read(), dpi=120)
        img = np.array(pages[0])

        roi = img[900:1400, 2000:2300]
        cropped = Image.fromarray(roi)

        # 90° drehen
        cropped = cropped.rotate(90, expand=True)

        images.append({
            "datei": file.name,
            "bild": cropped
        })

    st.subheader("Einträge prüfen und zuordnen")

    for i, item in enumerate(images):
        st.write(f"**Eintrag {i+1}: {item['datei']}**")

        col1, col2 = st.columns([1, 2])

        with col1:
            st.image(item["bild"], width=200)

        with col2:
            auswahl = st.selectbox(
                "Kürzel / Name auswählen",
                optionen,
                key=f"select_{i}"
            )

            if auswahl == "Andere":
                auswahl = st.text_input(
                    "Anderen Wert eingeben",
                    key=f"other_{i}"
                )

            values.append(auswahl)

    # ✅ Auswertung
    filtered_values = [v for v in values if v != ""]
    counts = Counter(filtered_values)

    count_df = pd.DataFrame(
        counts.items(),
        columns=["Kürzel / Name", "Häufigkeit"]
    ).sort_values(by="Häufigkeit", ascending=False)

    st.subheader("Häufigkeiten")
    st.dataframe(count_df, use_container_width=True)

    detail_df = pd.DataFrame({
        "Datei": [item["datei"] for item in images],
        "Zugeordneter Wert": values
    })

    st.subheader("Detailauswertung")
    st.dataframe(detail_df, use_container_width=True)

    # ✅ Speicher aufräumen vor PDF (wichtig)
    gc.collect()

    # ✅ PDF erstellen
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    page_width, page_height = A4
    y = page_height - 50

    for i, item in enumerate(images):
        img = item["bild"]

        w, h = img.size
        new_width = 150
        new_height = new_width * (h / w)

        if y - new_height < 80:
            c.showPage()
            y = page_height - 50

        c.drawString(50, y, f"Eintrag {i+1}: {item['datei']}")
        y -= 20

        c.drawString(220, y + 5, f"Auswertung: {values[i]}")

        c.drawInlineImage(
            img,
            50,
            y - new_height,
            width=new_width,
            height=new_height
        )

        y -= (new_height + 40)

    c.save()
    pdf_bytes = buffer.getvalue()

    # ✅ 🔥 STABILE VORSCHAU (nur erste Seite, niedrige DPI)
    st.subheader("Vorschau der fertigen PDF")

    preview = convert_from_bytes(pdf_bytes, dpi=80)

    if len(preview) > 0:
        st.image(preview[0], caption="Seite 1", use_column_width=True)

    # ✅ Download
    st.download_button(
        "PDF herunterladen",
        pdf_bytes,
        "ergebnis.pdf"
    )

    # CSV Export
    st.download_button(
        "Häufigkeiten als CSV herunterladen",
        count_df.to_csv(index=False).encode("utf-8-sig"),
        "haeufigkeiten.csv"
    )
