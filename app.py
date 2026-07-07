import streamlit as st
from pdf2image import convert_from_bytes
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
import pandas as pd
from collections import Counter
import gc
import math


# -------------------------------
# UI-Optimierung
# -------------------------------
st.markdown("""
<style>
[data-testid="stSpinner"] { display: none !important; }
[data-testid="stStatusWidget"] { visibility: hidden !important; }
</style>
""", unsafe_allow_html=True)

st.title("Feld-Extractor mit manueller Auswertung")


# -------------------------------
# Einstellungen
# -------------------------------
DPI = 200
BASE_DPI = 300
SCALE = DPI / BASE_DPI

ITEMS_PER_PAGE = 10

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

# Ursprüngliche Koordinaten bei 300 dpi
Y1, Y2 = 900, 1400
X1, X2 = 1900, 2400


# -------------------------------
# Hilfsfunktionen
# -------------------------------
def scale_value(v):
    return int(v * SCALE)


def safe_crop_pil(img, y1, y2, x1, x2, rotate_angle=None):
    """
    Schneidet einen Bereich aus einem PIL-Bild robust aus.
    Gibt komprimierte JPEG-Bytes zurück, um RAM zu sparen.
    """

    w_img, h_img = img.size

    y1 = max(0, min(y1, h_img))
    y2 = max(0, min(y2, h_img))
    x1 = max(0, min(x1, w_img))
    x2 = max(0, min(x2, w_img))

    if y2 <= y1 or x2 <= x1:
        return None

    cropped = img.crop((x1, y1, x2, y2)).convert("RGB")

    if rotate_angle is not None:
        cropped = cropped.rotate(rotate_angle, expand=True)

    buffer = io.BytesIO()
    cropped.save(buffer, format="JPEG", quality=80, optimize=True)

    return buffer.getvalue()


def process_pdf(pdf_bytes, filename):
    """
    Verarbeitet nur die erste Seite einer PDF.
    Speichert keine großen Bildobjekte dauerhaft.
    """

    try:
        pages = convert_from_bytes(
            pdf_bytes,
            dpi=DPI,
            first_page=1,
            last_page=1
        )

        if not pages:
            return None

        page_img = pages[0].convert("RGB")
        w_img, h_img = page_img.size

        y1 = scale_value(Y1)
        y2 = scale_value(Y2)
        x1 = scale_value(X1)
        x2 = scale_value(X2)

        cropped_normal = safe_crop_pil(
            page_img,
            y1, y2,
            x1, x2,
            rotate_angle=90
        )

        y1_180 = h_img - y2
        y2_180 = h_img - y1
        x1_180 = w_img - x2
        x2_180 = w_img - x1

        cropped_180 = safe_crop_pil(
            page_img,
            y1_180, y2_180,
            x1_180, x2_180,
            rotate_angle=270
        )

        img_90r = page_img.rotate(90, expand=True)

        cropped_90r = safe_crop_pil(
            img_90r,
            y1, y2,
            x1, x2,
            rotate_angle=90
        )

        del img_90r
        gc.collect()

        img_90l = page_img.rotate(-90, expand=True)

        cropped_90l = safe_crop_pil(
            img_90l,
            y1 + scale_value(150),
            y2 + scale_value(250),
            x1 - scale_value(200),
            x2 - scale_value(100),
            rotate_angle=90
        )

        del img_90l
        del page_img
        del pages
        gc.collect()

        return {
            "datei": filename,
            "normal": cropped_normal,
            "rot180": cropped_180,
            "rot90r": cropped_90r,
            "rot90l": cropped_90l
        }

    except Exception as e:
        return {
            "datei": filename,
            "fehler": str(e),
            "normal": None,
            "rot180": None,
            "rot90r": None,
            "rot90l": None
        }


def create_pdf(entries, values_dict):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 50

    c.drawString(50, y, "Datei")
    c.drawString(430, y, "Auswahl")
    y -= 30

    for entry in entries:
        filename = entry["datei"]
        value = values_dict.get(filename, "Andere")

        if y < 50:
            c.showPage()
            y = height - 50
            c.drawString(50, y, "Datei")
            c.drawString(430, y, "Auswahl")
            y -= 30

        c.drawString(50, y, filename[:55])
        c.drawString(430, y, value)
        y -= 25

    c.save()
    return buffer.getvalue()


def get_upload_signature(uploaded_files):
    """
    Erstellt eine Signatur der hochgeladenen Dateien.
    Dadurch erkennt die App, ob neue PDFs hochgeladen wurden.
    """

    return tuple(
        (file.name, getattr(file, "size", 0))
        for file in uploaded_files
    )


# -------------------------------
# Session State initialisieren
# -------------------------------
if "entries" not in st.session_state:
    st.session_state.entries = []

if "values_dict" not in st.session_state:
    st.session_state.values_dict = {}

if "page" not in st.session_state:
    st.session_state.page = 1

if "upload_signature" not in st.session_state:
    st.session_state.upload_signature = None

if "processing_finished" not in st.session_state:
    st.session_state.processing_finished = False

if "jump_to_entries_top" not in st.session_state:
    st.session_state.jump_to_entries_top = False


# -------------------------------
# Upload
# -------------------------------
uploaded_files = st.file_uploader(
    "PDFs hochladen",
    type="pdf",
    accept_multiple_files=True
)


# -------------------------------
# Automatische Verarbeitung nach Upload
# -------------------------------
if uploaded_files:

    current_signature = get_upload_signature(uploaded_files)

    if current_signature != st.session_state.upload_signature:

        st.session_state.entries = []
        st.session_state.values_dict = {}
        st.session_state.page = 1
        st.session_state.upload_signature = current_signature
        st.session_state.processing_finished = False
        st.session_state.jump_to_entries_top = False

        progress = st.progress(0)
        status = st.empty()

        total = len(uploaded_files)

        for i, file in enumerate(uploaded_files):

            status.write(f"Verarbeite PDF {i + 1} von {total}")

            try:
                pdf_bytes = file.getvalue()

                result = process_pdf(
                    pdf_bytes,
                    file.name
                )

                if result:
                    st.session_state.entries.append(result)
                    st.session_state.values_dict[file.name] = "Andere"

                del pdf_bytes
                gc.collect()

            except Exception as e:
                st.session_state.entries.append({
                    "datei": file.name,
                    "fehler": str(e),
                    "normal": None,
                    "rot180": None,
                    "rot90r": None,
                    "rot90l": None
                })

            progress.progress((i + 1) / total)

        st.session_state.processing_finished = True

        progress.empty()
        status.empty()

        st.rerun()


# -------------------------------
# Einträge anzeigen
# -------------------------------
entries = st.session_state.entries

if entries:

    # Ankerpunkt für automatisches Hochspringen nach Seitenwechsel
    st.markdown(
        "<div id='entries_top'></div>",
        unsafe_allow_html=True
    )

    if st.session_state.jump_to_entries_top:
        st.markdown("""
        <script>
            setTimeout(function() {
                const element = window.parent.document.getElementById("entries_top");
                if (element) {
                    element.scrollIntoView({behavior: "instant", block: "start"});
                } else {
                    window.parent.scrollTo(0, 0);
                }
            }, 100);
        </script>
        """, unsafe_allow_html=True)

        st.session_state.jump_to_entries_top = False

    st.subheader("Einträge prüfen")

    total_entries = len(entries)
    total_pages = math.ceil(total_entries / ITEMS_PER_PAGE)

    if st.session_state.page > total_pages:
        st.session_state.page = total_pages

    start_idx = (st.session_state.page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_entries)

    current_entries = entries[start_idx:end_idx]

    st.write(
        f"Einträge {start_idx + 1} bis {end_idx} von {total_entries}"
    )

    for i, entry in enumerate(current_entries, start=start_idx):

        st.write(f"**Eintrag {i + 1}: {entry['datei']}**")

        if "fehler" in entry:
            st.error(f"Fehler beim Verarbeiten: {entry['fehler']}")

        img_cols = st.columns(4)

        for col, key, label in zip(
            img_cols,
            ["normal", "rot180", "rot90r", "rot90l"],
            ["Normal", "180°", "90° rechts", "90° links"]
        ):
            with col:
                if entry[key] is not None:
                    st.image(
                        entry[key],
                        caption=label,
                        width="stretch"
                    )
                else:
                    st.warning("kein Bild")

        current_value = st.session_state.values_dict.get(
            entry["datei"],
            "Andere"
        )

        selected_value = st.radio(
            "Name auswählen",
            optionen,
            index=optionen.index(current_value),
            key=f"radio_{entry['datei']}"
        )

        st.session_state.values_dict[entry["datei"]] = selected_value

        st.divider()


    # -------------------------------
    # Seitennavigation unten
    # -------------------------------
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.session_state.page > 1:
            if st.button("⬅ Vorherige Seite"):
                st.session_state.page -= 1
                st.session_state.jump_to_entries_top = True
                st.rerun()

    with col2:
        st.markdown(
            f"<div style='text-align:center; font-weight:bold;'>"
            f"Seite {st.session_state.page} von {total_pages}"
            f"</div>",
            unsafe_allow_html=True
        )

    with col3:
        if st.session_state.page < total_pages:
            if st.button("Nächste Seite ➡"):
                st.session_state.page += 1
                st.session_state.jump_to_entries_top = True
                st.rerun()


    # -------------------------------
    # Auswertung
    # -------------------------------
    st.divider()
    st.subheader("Auswertung")

    if st.session_state.page == total_pages:

        st.success("Letzte Seite erreicht. Die Auswertung kann nun gestartet werden.")

        auswertung = st.button("Auswertung starten")

    else:

        st.info(
            f"Die Auswertung wird freigeschaltet, "
            f"sobald die letzte Seite ({total_pages}) erreicht ist."
        )

        auswertung = st.button(
            "Auswertung starten",
            disabled=True
        )

    if auswertung:

        values = [
            st.session_state.values_dict.get(entry["datei"], "Andere")
            for entry in entries
        ]

        counts = Counter(values)

        df = pd.DataFrame(
            counts.items(),
            columns=["Name", "Häufigkeit"]
        )

        df = df.sort_values(
            by="Häufigkeit",
            ascending=False
        )

        st.subheader("Häufigkeiten")
        st.dataframe(df, width="stretch")

        pdf_bytes = create_pdf(
            entries,
            st.session_state.values_dict
        )

        st.download_button(
            "PDF herunterladen",
            pdf_bytes,
            "auswertung.pdf",
            mime="application/pdf"
        )

        st.download_button(
            "CSV herunterladen",
            df.to_csv(index=False).encode("utf-8"),
            "auswertung.csv",
            mime="text/csv"
        )


else:
    if not uploaded_files:
        st.info("Bitte PDFs hochladen.")
