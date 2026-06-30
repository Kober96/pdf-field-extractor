import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
import pandas as pd
from collections import Counter

st.title("Feld-Extractor mit manueller Auswertung")

uploaded_files = st.file_uploader(
    "PDFs hochladen",
    type="pdf",
    accept_multiple_files=True
)

# Bekannte Kürzel/Namen
optionen = [
    "",
    "Schu",
    "Pothig S.",
    "Unklar",
    "Andere"
]

if uploaded_files:
    entries = []
    values = []

    for file in uploaded_files:
        pages = convert_from_bytes(file.read(), dpi=150)
        img = np.array(pages[0])

        # Originalseite als PIL-Bild
        page_img = Image.fromarray(img)

        # Variante 1: normale Ausrichtung
        roi_normal = img[900:1400, 2000:2300]
        cropped_normal = Image.fromarray(roi_normal)
        cropped_normal = cropped_normal.rotate(90, expand=True)

        # Variante 2: Seite zuerst 180° drehen, dann denselben Bereich ausschneiden
        page_rotated_180 = page_img.rotate(180, expand=True)
        img_rotated_180 = np.array(page_rotated_180)

        roi_180 = img_rotated_180[900:1400, 2000:2300]
        cropped_180 = Image.fromarray(roi_180)
        cropped_180 = cropped_180.rotate(90, expand=True)

        entries.append({
            "datei": file.name,
            "normal": cropped_normal,
            "gedreht_180": cropped_180
        })

    st.subheader("Einträge prüfen und zuordnen")

    for i, entry in enumerate(entries):
        st.write(f"**Eintrag {i+1}: {entry['datei']}**")

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            st.image(
                entry["normal"],
                caption="Variante 1: normal",
                width=180
            )

        with col2:
            st.image(
                entry["gedreht_180"],
                caption="Variante 2: Blatt 180° gedreht",
                width=180
            )

        with col3:
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

    # Häufigkeiten
    filtered_values = [v for v in values if v != ""]

    counts = Counter(filtered_values)

    count_df = pd.DataFrame(
        counts.items(),
        columns=["Kürzel / Name", "Häufigkeit"]
    ).sort_values(by="Häufigkeit", ascending=False)

    st.subheader("Häufigkeiten")
    st.dataframe(count_df, use_container_width=True)

    # Detailauswertung
    detail_df = pd.DataFrame({
        "Datei": [entry["datei"] for entry in entries],
        "Zugeordneter Wert": values
    })

    st.subheader("Detailauswertung")
    st.dataframe(detail_df, use_container_width=True)

    # PDF erstellen
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    page_width, page_height = A4
    y = page_height - 50

    for i, entry in enumerate(entries):
        img_normal = entry["normal"]
        img_180 = entry["gedreht_180"]

        # Größen
        new_width = 130

        w1, h1 = img_normal.size
        new_height_1 = new_width * (h1 / w1)

        w2, h2 = img_180.size
        new_height_2 = new_width * (h2 / w2)

        max_height = max(new_height_1, new_height_2)

        # Neue Seite, falls nicht genug Platz
        if y - max_height < 100:
            c.showPage()
            y = page_height - 50

        c.drawString(50, y, f"Eintrag {i+1}: {entry['datei']}")
        c.drawString(350, y, f"Auswertung: {values[i]}")
        y -= 20

        # Variante normal
        c.drawString(50, y, "Normal")
        c.drawInlineImage(
            img_normal,
            50,
            y - new_height_1 - 15,
            width=new_width,
            height=new_height_1
        )

        # Variante 180°
        c.drawString(220, y, "180 Grad gedreht")
        c.drawInlineImage(
            img_180,
            220,
            y - new_height_2 - 15,
            width=new_width,
            height=new_height_2
        )

        y -= (max_height + 60)

    c.save()

    pdf_bytes = buffer.getvalue()

    # Vorschau der fertigen PDF
    st.subheader("Vorschau der fertigen PDF")

    pdf_preview = convert_from_bytes(pdf_bytes, dpi=150)

    for i, page in enumerate(pdf_preview):
        st.image(page, caption=f"Seite {i+1}", use_column_width=True)

    # PDF Download
    st.download_button(
        "PDF herunterladen",
        pdf_bytes,
        "ergebnis.pdf",
        "application/pdf"
    )

    # CSV Detailauswertung
    detail_csv = detail_df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "Detailauswertung als CSV herunterladen",
        detail_csv,
        "detailauswertung.csv",
        "text/csv"
    )

    # CSV Häufigkeiten
    count_csv = count_df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "Häufigkeiten als CSV herunterladen",
        count_csv,
        "haeufigkeiten.csv",
        "text/csv"
    )
