import streamlit as st
import pandas as pd
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# === CONFIG ===
FRAGEN_DATEI = "implizite_fragen_ecosystem_services.csv"
GOOGLE_SHEET_NAME = "Solarumfrage_Antworten"  # Name des Google Sheets
CREDENTIALS_FILE = "credentials.json"  # Der private Schlüssel (nicht ins Git!)


# === GOOGLE SHEETS SETUP ===
def init_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    # 🤖 Automatisch zwischen lokal und online unterscheiden
    if "gcp_service_account" in st.secrets:
        # Online (Streamlit Cloud): lese aus st.secrets
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Lokal: lese aus credentials.json
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "credentials.json", scope
        )

    client = gspread.authorize(creds)
    sheet = client.open("Solarumfrage_Antworten").sheet1
    return sheet


# === LADEN DER FRAGEN ===
try:
    fragen_df = pd.read_csv(FRAGEN_DATEI)
except FileNotFoundError:
    st.error(
        f"Fragen-Datei '{FRAGEN_DATEI}' nicht gefunden. Bitte sicherstellen, dass sie im selben Ordner liegt."
    )
    st.stop()

# === UI ===
st.title("Umfrage: Bedeutung von Landschaftsmerkmalen")
st.markdown(
    "Bitte beantworte die folgenden Fragen ehrlich. Es gibt keine richtigen oder falschen Antworten."
)

# === NUTZERINFOS ===
st.subheader("Allgemeine Informationen")
nutzer_id = st.text_input("Deine ID oder Initialen (freiwillig):")
stakeholder_typ = st.selectbox(
    "Ich bin ...",
    [
        "Bitte auswählen",
        "Anwohnende:r",
        "Landwirt:in",
        "Planer:in",
        "Tourist:in",
        "Andere",
    ],
)

st.markdown("---")
st.subheader("Fragen")

antworten = {}

# === FRAGEBOGEN ===
for idx, row in fragen_df.iterrows():
    frage = row["Frage"]
    optionen = (row["Option A"], row["Option B"])
    st.markdown(f"**{frage}**")
    antwort = st.radio(
        label=frage,  # statt ""
        options=optionen,
        index=None,
        key=f"frage_{idx}",
        label_visibility="collapsed",
    )
    antworten[f"Frage_{idx + 1}"] = antwort

# === ABSENDEN ===
if st.button("Antworten absenden"):
    if stakeholder_typ == "Bitte auswählen":
        st.warning("Bitte wähle einen Stakeholder-Typ aus.")
    else:
        # Erstelle Antwortzeile
        zeile = {
            "Zeitstempel": datetime.now().isoformat(),
            "Teilnehmer": nutzer_id,
            "Stakeholder": stakeholder_typ,
        }
        zeile.update(antworten)

        # In Google Sheet schreiben
        try:
            sheet = init_gsheet()
            antwort_liste = list(zeile.values())
            sheet.append_row(antwort_liste)
            st.success("Vielen Dank! Deine Antworten wurden gespeichert.")
        except Exception as e:
            st.error(f"Fehler beim Speichern in Google Sheets: {e}")
