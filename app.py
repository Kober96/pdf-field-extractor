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


# ------------------------------------------------------------
# UI-Optimierung: Spinner / Ausgrauen reduzieren
# ------------------------------------------------------------
st.markdown("""
<style>
/* Spinner möglichst ausblenden */
[data-testid="stSpinner"] {
    display: none !important;
}

/* Status Widget möglichst ausblenden */
[data-testid="stStatusWidget"] {
    visibility: hidden !important;
}

/* App nicht abdunkeln */
.stApp {
    opacity: 1 !important;
}

[data-testid="stAppViewContainer"] {
    opacity: 1 !important;
}

/* Etwas kompaktere Radio-Buttons */
div[role="radiogroup"] label {
    margin-bottom: 2px !important;
}
</style>
""", unsafe_allow_html=True)


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


optionen = [
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
X1, X2 = 1900, 2400


# ------------------------------------------------------------
# Sichere Crop-Funktion
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# Sichere Bildanzeige
# ------------------------------------------------------------
def show_image_or_warning(image, caption):
    if image is not None:
        st.image(image, caption=caption, width=150)
    else:
        st.warning(f"{caption}: kein gültiger Ausschnitt")


# ------------------------------------------------------------
# PDF-Verarbeitung gecacht
# Dadurch wird beim Anklicken eines Namens nicht alles neu berechnet
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def process_pdf_cached(pdf_bytes_input, file_name):
    pages = convert_from_bytes(
        pdf_bytes_input,
        dpi=300,
        first_page=1,
        last_page=1
    )

    if not pages:
        return None

    img = np.array(pages[0])
    h_img, w_img = img.shape[:2]

    page_img = Image.fromarray(img).convert("RGB")

    # Normal
    cropped_normal = safe_crop(
        img,
        Y1, Y2,
        X1, X2,
        rotate_angle=90
    )

    # 180° Koordinaten spiegeln
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

    # 90° rechts
    img_90r = np.array(page_img.rotate(90, expand=True))

    cropped_90r = safe_crop(
        img_90r,
        Y1, Y2,
        X1, X2,
        rotate_angle=90
    )

    # 90° links mit Verschiebung
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

    return {
        "datei": file_name,
        "normal": cropped_normal,
        "rot180": cropped_180,
        "rot90r": cropped_90r,
        "rot90l": cropped_90l
    }


# ------------------------------------------------------------
# PDF erzeugen
# ------------------------------------------------------------
def create_pdf(entries, values):
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

            if w > 0:
                heights.append(new_w * (h / w))

        if not heights:
            continue

        max_h = max(heights)

        if y - max_h < 100:
            c.showPage()
            y = height - 50

        selected_value = values[i] if i < len(values) else ""

        c.drawString(50, y, entry["datei"])
        c.drawString(350, y, selected_value)
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

    return pdf_bytes


# ------------------------------------------------------------
# Hauptlogik
# ------------------------------------------------------------
if uploaded_files:

    entries = []

    with st.spinner("PDFs werden verarbeitet..."):
        for file in uploaded_files:
            try:
                pdf_bytes_input = file.getvalue()

                entry = process_pdf_cached(
                    pdf_bytes_input,
                    file.name
                )

                if entry is None:
                    st.error(f"{file.name}: PDF konnte nicht gelesen werden")
                    continue

                entries.append(entry)

            except Exception as e:
                st.error(f"{file.name}: Fehler beim Verarbeiten der Datei")
                st.write(str(e))

            gc.collect()

    if entries:
        st.subheader("Einträge prüfen")

        # --------------------------------------------------------
        # FORM verhindert Rerun bei jeder einzelnen Auswahl
        # Auswertung passiert erst bei Button-Klick
        # --------------------------------------------------------
        with st.form("auswertung_form"):

            values = []

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
                    val = st.radio(
                        "Name auswählen",
                        optionen,
                        index=len(optionen) - 1,
                        key=f"radio_{i}"
                    )

                    other_val = st.text_input(
                        "Eingabe nur falls 'Andere' gewählt ist",
                        key=f"txt_{i}"
                    )

                    if val == "Andere":
                        if other_val.strip():
                            selected_value = other_val.strip()
                        else:
                            selected_value = "Andere"
                    else:
                        selected_value = val

                    values.append(selected_value)

                st.divider()

            submitted = st.form_submit_button("Auswertung starten")

        # --------------------------------------------------------
        # Auswertung erst nach Button-Klick
        # --------------------------------------------------------
        if submitted:

            filtered = [v for v in values if v != ""]
            counts = Counter(filtered)

            df = pd.DataFrame(
                counts.items(),
                columns=["Name", "Häufigkeit"]
            )

            if not df.empty:
                df = df.sort_values(
                    by="Häufigkeit",
                    ascending=False
                )

            st.subheader("Häufigkeiten")
            st.dataframe(df)

            # PDF erzeugen
            pdf_bytes = create_pdf(entries, values)

            # Vorschau
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
