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

# Koordinaten deines Feldes im korrekt ausgerichteten Dokument
Y1, Y2 = 900, 1400
X1, X2 = 2000, 2300

def crop_field(page_img, correction_angle, offset_x_percent=0, offset_y_percent=0):
    """
    Dreht die komplette Seite in eine mögliche Ausrichtung
    und schneidet danach den Feldbereich aus.
    Optional kann der Ausschnitt pro Variante verschoben werden.
    """

    rotated_page = page_img.rotate(correction_angle, expand=True)
    img_array = np.array(rotated_page)

    h_img, w_img = img_array.shape[:2]

    # Grundgröße des Ausschnitts
    crop_width = X2 - X1
    crop_height = Y2 - Y1

    # Verschiebung berechnen
    offset_x = int(crop_width * offset_x_percent)
    offset_y = int(crop_height * offset_y_percent)

    # Koordinaten mit Verschiebung
    y1 = Y1 + offset_y
    y2 = Y2 + offset_y
    x1 = X1 + offset_x
    x2 = X2 + offset_x

    # Sicherheitsbegrenzung
    y1 = max(0, min(y1, h_img))
    y2 = max(0, min(y2, h_img))
    x1 = max(0, min(x1, w_img))
    x2 = max(0, min(x2, w_img))

    roi = img_array[y1:y2, x1:x2]

    if roi.size == 0:
        return None

    cropped = Image.fromarray(roi).convert("RGB")

    # Ausschnitt lesbar drehen
    cropped = cropped.rotate(90, expand=True)

    return cropped

if uploaded_files:
    entries = []
    values = []

    for file in uploaded_files:
        try:
            pages = convert_from_bytes(file.read(), dpi=300)
            img = np.array(pages[0])
            page_img = Image.fromarray(img).convert("RGB")

            # Variante 1: Dokument ist normal
            variant_normal = crop_field(page_img, 0)

            # Variante 2: Dokument ist 180° verdreht
            variant_180 = crop_field(page_img, 180)

            # Variante 3: Dokument ist 90° nach rechts gedreht
            # Korrektur: Seite 90° nach links drehen
            variant_90_rechts = crop_field(page_img, 90)

            # Variante 4: Dokument ist 90° nach links gedreht
            # Korrektur: Seite 90° nach rechts drehen
            variant_90_links = crop_field(page_img, -90)

            if variant_normal is None and variant_180 is None and variant_90_rechts is None and variant_90_links is None:
                st.error(f"Bei Datei {file.name} konnte kein gültiger Ausschnitt erzeugt werden. Bitte Koordinaten prüfen.")
                st.stop()

            entries.append({
                "datei": file.name,
                "normal": variant_normal,
                "gedreht_180": variant_180,
                "gedreht_90_rechts": variant_90_rechts,
                "gedreht_90_links": variant_90_links
            })

        except Exception as e:
            st.error(f"Fehler beim Verarbeiten von {file.name}")
            st.exception(e)
            st.stop()

    st.subheader("Einträge prüfen und zuordnen")

    for i, entry in enumerate(entries):
        st.write(f"**Eintrag {i+1}: {entry['datei']}**")

        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 2])

        with col1:
            if entry["normal"] is not None:
                st.image(
                    entry["normal"],
                    caption="Normal",
                    width=140,
                    output_format="PNG"
                )
            else:
                st.warning("Kein Bild")

        with col2:
            if entry["gedreht_180"] is not None:
                st.image(
                    entry["gedreht_180"],
                    caption="180°",
                    width=140,
                    output_format="PNG"
                )
            else:
                st.warning("Kein Bild")

        with col3:
            if entry["gedreht_90_rechts"] is not None:
                st.image(
                    entry["gedreht_90_rechts"],
                    caption="90° rechts",
                    width=140,
                    output_format="PNG"
                )
            else:
                st.warning("Kein Bild")

        with col4:
            if entry["gedreht_90_links"] is not None:
                st.image(
                    entry["gedreht_90_links"],
                    caption="90° links",
                    width=140,
                    output_format="PNG"
                )
            else:
                st.warning("Kein Bild")

        with col5:
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

        variants = [
            ("Normal", entry["normal"]),
            ("180 Grad", entry["gedreht_180"]),
            ("90 Grad rechts", entry["gedreht_90_rechts"]),
            ("90 Grad links", entry["gedreht_90_links"])
        ]

        valid_variants = [(label, img) for label, img in variants if img is not None]

        new_width = 90
        heights = []

        for label, img in valid_variants:
            w, h = img.size
            heights.append(new_width * (h / w))

        max_height = max(heights) if heights else 100

        if y - max_height < 120:
            c.showPage()
            y = page_height - 50

        c.drawString(50, y, f"Eintrag {i+1}: {entry['datei']}")
        c.drawString(350, y, f"Auswertung: {values[i]}")
        y -= 20

        x_positions = [50, 160, 270, 380]

        for idx, (label, img) in enumerate(valid_variants):
            w, h = img.size
            new_height = new_width * (h / w)

            x_pos = x_positions[idx]

            c.drawString(x_pos, y, label)
            c.drawInlineImage(
                img,
                x_pos,
                y - new_height - 15,
                width=new_width,
                height=new_height
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
