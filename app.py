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

# Limit gegen Absturz
if uploaded_files and len(uploaded_files) > 15:
    st.error("Maximal 15 PDFs gleichzeitig laden")
    st.stop()

# Auswahloptionen
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

# Ausgangskoordinaten
Y1, Y2 = 900, 1400
X1, X2 = 1700, 2200


# ✅ Sichere Crop-Funktion gegen leere oder ungültige Ausschnitte
def safe_crop(img, y1, y2, x1, x2, rotate_angle=None):
    h_img, w_img = img.shape[:2]

    y1 = max(0, min(y1, h_img))
    y2 = max(0, min(y2, h_img))
    x1 = max(0, min(x1, w_img))
    x2 = max(0, min(x2, w_img))

    if y2 <= y1 or x2 <= x1:
        return None

    roi = img[y1:y2, x1:x2]

    if roi.size == 0:
        return None

    try:
        cropped = Image.fromarray(roi).convert("RGB")

        if rotate_angle is not None:
            cropped = cropped.rotate(rotate_angle, expand=True)

        return cropped

    except Exception:
        return None


# ✅ Sichere Anzeige eines Bildes
def show_image_or_warning(image, caption):
    if image is not None:
        st.image(image, caption=caption, width=150)
    else:
        st.warning(f"{caption}: kein gültiger Ausschnitt")


if uploaded_files:
    entries = []
    values = []

    for file in uploaded_files:

        try:
            # Datei sauber als Bytes lesen
            pdf_bytes_input = file.getvalue()

            # Nur erste Seite laden, niedrige DPI für Stabilität
            pages = convert_from_bytes(
                pdf_bytes_input,
                dpi=300,
                first_page=1,
                last_page=1
            )

            if not pages:
                st.error(f"{file.name}: PDF konnte nicht gelesen werden")
                continue

            img = np.array(pages[0])
            h_img, w_img = img.shape[:2]

            page_img = Image.fromarray(img).convert("RGB")

            # ✅ NORMAL
            cropped_normal = safe_crop(
                img,
                Y1, Y2,
                X1, X2,
                rotate_angle=90
            )

            # ✅ 180° Koordinaten spiegeln
            y1_180 = h_img - Y2
            y2_180 = h_img - Y1
            x1_180 = w_img - X2
            x2_180 = w_img - X1

            cropped_180 = safe_crop(
                img,
                y1_180, y2_180,
                x1_180, x2_180,
                rotate_angle=270
            )

            # ✅ 90° rechts
            img_90r = np.array(page_img.rotate(90, expand=True))

            cropped_90r = safe_crop(
                img_90r,
                Y1, Y2,
                X1, X2,
                rotate_angle=90
            )

            # ✅ 90° links + Verschiebung
            img_90l = np.array(page_img.rotate(-90, expand=True))

            y1_90l = Y1 + 150
            y2_90l = Y2 + 250
            x1_90l = X1 - 200
            x2_90l = X2 - 100

            cropped_90l = safe_crop(
                img_90l,
                y1_90l, y2_90l,
                x1_90l, x2_90l,
                rotate_angle=90
            )

            entries.append({
                "datei": file.name,
                "normal": cropped_normal,
                "rot180": cropped_180,
                "rot90r": cropped_90r,
                "rot90l": cropped_90l
            })

        except Exception as e:
            st.error(f"{file.name}: Fehler beim Verarbeiten der Datei")
            st.write(str(e))

        gc.collect()

    if entries:
        st.subheader("Einträge prüfen")

        for i, entry in enumerate(entries):
            st.write(f"**Eintrag {i + 1}: {entry['datei']}**")

            col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 2])

            with col1:
                show_image_or_warning(entry["normal"], "Normal")

            with col2:
                show_image_or_warning(entry["rot180"], "180°")

            with col3:
                show_image_or_warning(entry["rot90r"], "90° rechts")

            with col4:
                show_image_or_warning(entry["rot90l"], "90° links")

            with col5:
                val = st.selectbox(
                    "Name auswählen",
                    optionen,
                    key=f"sel_{i}"
                )

                if val == "Andere":
                    val = st.text_input("Eingabe", key=f"txt_{i}")

                values.append(val)

            st.divider()

        # ✅ Auswertung
        filtered = [v for v in values if v != ""]
        counts = Counter(filtered)

        df = pd.DataFrame(counts.items(), columns=["Name", "Häufigkeit"])

        if not df.empty:
            df = df.sort_values(by="Häufigkeit", ascending=False)

        st.subheader("Häufigkeiten")
        st.dataframe(df)

        # ✅ PDF erzeugen
        gc.collect()

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)

        width, height = A4
        y = height - 50

        for i, entry in enumerate(entries):

            imgs_with_labels = [
                ("Normal", entry["normal"]),
                ("180°", entry["rot180"]),
                ("90° rechts", entry["rot90r"]),
                ("90° links", entry["rot90l"])
            ]

            # Ungültige Bilder entfernen
            imgs_with_labels = [
                item for item in imgs_with_labels
                if item[1] is not None
            ]

            if not imgs_with_labels:
                continue

            new_w = 90
            heights = []

            for label, img in imgs_with_labels:
                w, h = img.size

                if w == 0:
                    continue

                heights.append(new_w * (h / w))

            if not heights:
                continue

            max_h = max(heights)

            if y - max_h < 100:
                c.showPage()
                y = height - 50

            selected_value = values[i] if i < len(values) else ""

            c.drawString(50, y, f"{entry['datei']}")
            c.drawString(350, y, f"{selected_value}")
            y -= 20

            x_pos = [50, 150, 250, 350]

            for idx, (label, img) in enumerate(imgs_with_labels):
                if idx >= len(x_pos):
                    break

                w, h = img.size

                if w == 0:
                    continue

                h_new = new_w * (h / w)

                c.drawString(x_pos[idx], y, label)

                c.drawInlineImage(
                    img,
                    x_pos[idx],
                    y - h_new - 15,
                    width=new_w,
                    height=h_new
                )

            y -= (max_h + 80)

        c.save()

        pdf_bytes = buffer.getvalue()

        # ✅ Vorschau
        st.subheader("Vorschau")

        try:
            preview = convert_from_bytes(
                pdf_bytes,
                dpi=60,
                first_page=1,
                last_page=1
            )

            if preview:
                st.image(preview[0], use_container_width=True)
            else:
                st.warning("Vorschau nicht möglich")

        except Exception:
            st.warning("Vorschau nicht möglich")

        st.download_button(
            "PDF herunterladen",
            pdf_bytes,
            file_name="auswertung.pdf",
            mime="application/pdf"
        )

        st.download_button(
            "CSV herunterladen",
            df.to_csv(index=False).encode("utf-8"),
            file_name="auswertung.csv",
            mime="text/csv"
        )

    else:
        st.warning("Keine gültigen Einträge gefunden.")
