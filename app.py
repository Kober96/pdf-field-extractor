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

# Sicherheitslimit gegen Streamlit-Abstürze
if uploaded_files and len(uploaded_files) > 15:
    st.error("Bitte maximal 15 PDFs gleichzeitig hochladen.")
    st.stop()

# Bekannte Kürzel/Namen
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
    entries = []
    values = []

    for file in uploaded_files:
        try:
            pages = convert_from_bytes(file.read(), dpi=300)
            img = np.array(pages[0])

            # Original-Koordinaten für normal ausgerichtetes Blatt
            y1, y2 = 900, 1400
            x1, x2 = 2000, 2300

            # Bildhöhe und Bildbreite bestimmen
            h_img, w_img = img.shape[:2]

            # Variante 1: normale Position
            roi_normal = img[y1:y2, x1:x2]

            if roi_normal.size == 0:
                st.error(f"Ausschnitt NORMAL bei Datei {file.name} ist leer. Bitte Koordinaten prüfen.")
                st.stop()

            cropped_normal = Image.fromarray(roi_normal).convert("RGB")
            cropped_normal = cropped_normal.rotate(90, expand=True)

            # Variante 2: Position, falls Blatt um 180° verdreht ist
            y1_180 = h_img - y2
            y2_180 = h_img - y1
            x1_180 = w_img - x2
            x2_180 = w_img - x1

            roi_180 = img[y1_180:y2_180, x1_180:x2_180]

            if roi_180.size == 0:
                st.error(f"Ausschnitt 180° bei Datei {file.name} ist leer. Bitte Koordinaten prüfen.")
                st.stop()

            cropped_180 = Image.fromarray(roi_180).convert("RGB")

            # Damit der zweite Ausschnitt lesbar angezeigt wird
            cropped_180 = cropped_180.rotate(270, expand=True)

            entries.append({
                "datei": file.name,
                "normal": cropped_normal,
                "gedreht_180": cropped_180
            })

        except Exception as e:
            st.error(f"Fehler beim Verarbeiten von {file.name}")
            st.exception(e)
            st.stop()

    st.subheader("Einträge prüfen und zuordnen")

    for i, entry in enumerate(entries):
        st.write(f"**Eintrag {i+1}: {entry['datei']}**")

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            st.image(
                entry["normal"],
                caption="Variante 1",
                width=180,
                output_format="PNG"
            )

        with col2:
            st.image(
                entry["gedreht_180"],
                caption="Variante 2 bei 180°",
                width=180,
                output_format="PNG"
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

    # Detailtabelle
    detail_df = pd.DataFrame({
        "Datei": [entry["datei"] for entry in entries],
        "Zugeordneter Wert": values
    })

    st.subheader("Detailauswertung")
    st.dataframe(detail_df, use_container_width=True)

    gc.collect()

    # PDF erstellen
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    page_width, page_height = A4
    y = page_height - 50

    for i, entry in enumerate(entries):
        img_normal = entry["normal"]
        img_180 = entry["gedreht_180"]

        new_width = 130

        w1, h1 = img_normal.size
        new_height_1 = new_width * (h1 / w1)

        w2, h2 = img_180.size
        new_height_2 = new_width * (h2 / w2)

        max_height = max(new_height_1, new_height_2)

        if y - max_height < 100:
            c.showPage()
            y = page_height - 50

        c.drawString(50, y, f"Eintrag {i+1}: {entry['datei']}")
        c.drawString(350, y, f"Auswertung: {values[i]}")
        y -= 20

        c.drawString(50, y, "Variante 1")
        c.drawInlineImage(
            img_normal,
            50,
            y - new_height_1 - 15,
            width=new_width,
            height=new_height_1
        )

        c.drawString(220, y, "Variante 2 bei 180 Grad")
        c.drawInlineImage(
            img_180,
            220,
            y - new_height_2 - 15,
            width=new_width,
            height=new_height_2
        )

        y -= (max_height + 70)

    c.save()
    pdf_bytes = buffer.getvalue()

    # PDF-Vorschau vor Download
    st.subheader("Vorschau der fertigen PDF")

    try:
        pdf_preview = convert_from_bytes(pdf_bytes, dpi=80)

        if len(pdf_preview) > 0:
            st.image(
                pdf_preview[0],
                caption="Vorschau Seite 1",
                use_column_width=True,
                output_format="PNG"
            )

        if len(pdf_preview) > 1:
            st.info("Es wird aus Stabilitätsgründen nur die erste Seite als Vorschau angezeigt. Die heruntergeladene PDF enthält alle Seiten.")

    except Exception:
        st.warning("Die PDF-Vorschau konnte nicht erzeugt werden. Der Download funktioniert trotzdem.")

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
