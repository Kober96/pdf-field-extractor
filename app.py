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
Y1, Y2 = 800, 1300
X1, X2 = 2000, 2300

if uploaded_files:
    entries = []
    values = []

    for file in uploaded_files:
        pages = convert_from_bytes(file.read(), dpi=300)
        img = np.array(pages[0])
        h_img, w_img = img.shape[:2]

        page_img = Image.fromarray(img).convert("RGB")

        # ✅ NORMAL
        roi_normal = img[Y1:Y2, X1:X2]
        cropped_normal = Image.fromarray(roi_normal).convert("RGB").rotate(90, expand=True)

        # ✅ 180° (Koordinaten spiegeln)
        y1_180 = h_img - Y2
        y2_180 = h_img - Y1
        x1_180 = w_img - X2
        x2_180 = w_img - X1

        roi_180 = img[y1_180:y2_180, x1_180:x2_180]
        cropped_180 = Image.fromarray(roi_180).convert("RGB").rotate(270, expand=True)

        # ✅ 90° rechts
        img_90r = np.array(page_img.rotate(90, expand=True))
        roi_90r = img_90r[Y1:Y2, X1:X2]
        cropped_90r = Image.fromarray(roi_90r).convert("RGB").rotate(90, expand=True)

        # ✅ 90° links + Verschiebung
        img_90l = np.array(page_img.rotate(-90, expand=True))

        # Verschiebung (60px rechts, 250px runter)
        y1_90l = Y1 + 150
        y2_90l = Y2 + 250
        x1_90l = X1 + -200
        x2_90l = X2 + -200

        roi_90l = img_90l[y1_90l:y2_90l, x1_90l:x2_90l]
        cropped_90l = Image.fromarray(roi_90l).convert("RGB").rotate(90, expand=True)

        entries.append({
            "datei": file.name,
            "normal": cropped_normal,
            "rot180": cropped_180,
            "rot90r": cropped_90r,
            "rot90l": cropped_90l
        })

    st.subheader("Einträge prüfen")

    for i, entry in enumerate(entries):
        st.write(f"**Eintrag {i+1}: {entry['datei']}**")

        col1, col2, col3, col4, col5 = st.columns([1,1,1,1,2])

        with col1:
            st.image(entry["normal"], caption="Normal", width=150)

        with col2:
            st.image(entry["rot180"], caption="180°", width=150)

        with col3:
            st.image(entry["rot90r"], caption="90° rechts", width=150)

        with col4:
            st.image(entry["rot90l"], caption="90° links", width=150)

        with col5:
            val = st.selectbox(
                "Name auswählen",
                optionen,
                key=f"sel_{i}"
            )

            if val == "Andere":
                val = st.text_input("Eingabe", key=f"txt_{i}")

            values.append(val)

    # ✅ Auswertung
    filtered = [v for v in values if v != ""]
    counts = Counter(filtered)

    df = pd.DataFrame(counts.items(), columns=["Name", "Häufigkeit"])
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

        imgs = [
            entry["normal"],
            entry["rot180"],
            entry["rot90r"],
            entry["rot90l"]
        ]

        new_w = 90
        heights = []

        for img in imgs:
            w, h = img.size
            heights.append(new_w * (h / w))

        max_h = max(heights)

        if y - max_h < 100:
            c.showPage()
            y = height - 50

        c.drawString(50, y, f"{entry['datei']}")
        c.drawString(350, y, f"{values[i]}")
        y -= 20

        x_pos = [50, 150, 250, 350]

        for idx, img in enumerate(imgs):
            w, h = img.size
            h_new = new_w * (h / w)

            c.drawInlineImage(
                img,
                x_pos[idx],
                y - h_new,
                width=new_w,
                height=h_new
            )

        y -= (max_h + 60)

    c.save()

    pdf_bytes = buffer.getvalue()

    # ✅ Vorschau (stabil)
    st.subheader("Vorschau")

    try:
        preview = convert_from_bytes(pdf_bytes, dpi=80)
        st.image(preview[0], use_column_width=True)
    except:
        st.warning("Vorschau nicht möglich")

    st.download_button("PDF herunterladen", pdf_bytes)

    st.download_button(
        "CSV herunterladen",
        df.to_csv(index=False).encode("utf-8"),
        "auswertung.csv"
    )
