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

# ✅ UI smoother (kein Ausgrauen)
st.markdown("""
<style>
[data-testid="stSpinner"] {display: none !important;}
[data-testid="stStatusWidget"] {visibility: hidden !important;}
</style>
""", unsafe_allow_html=True)


st.title("Feld-Extractor mit manueller Auswertung")

uploaded_files = st.file_uploader(
    "PDFs hochladen",
    type="pdf",
    accept_multiple_files=True
)

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

Y1, Y2 = 900, 1400
X1, X2 = 1900, 2400


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

    cropped = Image.fromarray(roi).convert("RGB")

    if rotate_angle is not None:
        cropped = cropped.rotate(rotate_angle, expand=True)

    return cropped


@st.cache_data(show_spinner=False)
def process_pdf(pdf_bytes):
    pages = convert_from_bytes(pdf_bytes, dpi=300, first_page=1, last_page=1)

    if not pages:
        return None

    img = np.array(pages[0])
    h_img, w_img = img.shape[:2]
    page_img = Image.fromarray(img).convert("RGB")

    cropped_normal = safe_crop(img, Y1, Y2, X1, X2, rotate_angle=90)

    y1_180 = h_img - Y2
    y2_180 = h_img - Y1
    x1_180 = w_img - X2
    x2_180 = w_img - X1

    cropped_180 = safe_crop(img, y1_180, y2_180, x1_180, x2_180, rotate_angle=270)

    img_90r = np.array(page_img.rotate(90, expand=True))
    cropped_90r = safe_crop(img_90r, Y1, Y2, X1, X2, rotate_angle=90)

    img_90l = np.array(page_img.rotate(-90, expand=True))

    cropped_90l = safe_crop(
        img_90l,
        Y1 + 150, Y2 + 250,
        X1 - 200, X2 - 100,
        rotate_angle=90
    )

    return {
        "normal": cropped_normal,
        "rot180": cropped_180,
        "rot90r": cropped_90r,
        "rot90l": cropped_90l
    }


if uploaded_files:

    entries = []

    for file in uploaded_files:
        data = process_pdf(file.getvalue())
        if data:
            data["datei"] = file.name
            entries.append(data)

    if entries:
        st.subheader("Einträge prüfen")

        with st.form("form"):

            values = []

            for i, entry in enumerate(entries):
                st.write(f"**{entry['datei']}**")

                col1, col2, col3, col4, col5 = st.columns([1,1,1,1,2])

                for col, key, label in zip(
                    [col1, col2, col3, col4],
                    ["normal", "rot180", "rot90r", "rot90l"],
                    ["Normal", "180°", "90° r", "90° l"]
                ):
                    with col:
                        if entry[key]:
                            st.image(entry[key], caption=label, width=150)

                with col5:
                    val = st.radio(
                        "Name",
                        optionen,
                        index=len(optionen) - 1,  # 👉 default = "Andere"
                        key=f"r_{i}"
                    )

                    values.append(val)

                st.divider()

            submitted = st.form_submit_button("Auswertung starten")

        if submitted:

            counts = Counter(values)
            df = pd.DataFrame(counts.items(), columns=["Name", "Häufigkeit"])
            df = df.sort_values(by="Häufigkeit", ascending=False)

            st.dataframe(df)

            # PDF
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)

            y = 800

            for i, entry in enumerate(entries):
                c.drawString(50, y, entry["datei"])
                c.drawString(350, y, values[i])
                y -= 40

            c.save()

            st.download_button(
                "PDF",
                buffer.getvalue(),
                "auswertung.pdf"
            )

            st.download_button(
                "CSV",
                df.to_csv(index=False),
                "auswertung.csv"
            )

    else:
        st.warning("Keine gültigen Einträge")
