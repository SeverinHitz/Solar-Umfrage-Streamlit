import streamlit as st
import pandas as pd
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import matplotlib.pyplot as plt

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


# === Button Style ===
def set_button_style():
    st.markdown(
        """
        <style>
        div[role="radiogroup"] > label {
            background: #f7f7f7;
            padding: 1rem 1.5rem;
            margin: 0.5rem 0;
            border-radius: 12px;
            display: flex;
            align-items: center;
            gap: 1rem;
            border: 2px solid transparent;
            transition: all 0.2s ease-in-out;
            cursor: pointer;
            font-size: 1.1rem;
        }

        div[role="radiogroup"] > label:hover {
            border-color: #4e8cff;
            background-color: #eef5ff;
        }

        div[role="radiogroup"] input:checked + div {
            background-color: #4e8cff !important;
            color: white !important;
        }

        div[role="radiogroup"] svg {
            width: 1.2rem;
            height: 1.2rem;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )


# === UI ===
st.title("Umfrage: Bedeutung von Landschaftsmerkmalen")
set_button_style()
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
        label=frage,
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
        else:
            # === Auswertung ===

            # === AUSWERTUNG NACH ANTWORTEN ===
            st.markdown("---")
            st.subheader("🧮 Deine Prioritäten auf einen Blick")

            # Zähler initialisieren
            haupt_counts = {"Provisioning": 0, "Regulating": 0, "Cultural": 0}
            sub_counts = {}

            for idx, row in fragen_df.iterrows():
                frage_key = f"Frage_{idx + 1}"
                antwort = antworten[frage_key]

                # Entscheide, ob Option A oder B gewählt wurde
                if antwort == row["Option A"]:
                    sub = row["Subkategorie A"]
                    cat = row["Kategorie A"]
                else:
                    sub = row["Subkategorie B"]
                    cat = row["Kategorie B"]

                # Zähle Hauptkategorie
                if cat in haupt_counts:
                    haupt_counts[cat] += 1
                else:
                    haupt_counts[cat] = 1

                # Zähle Subkategorie
                sub_counts[sub] = sub_counts.get(sub, 0) + 1

            # === 1. Hauptkategorien-PieChart
            fig1, ax1 = plt.subplots()
            ax1.pie(
                haupt_counts.values(),
                labels=haupt_counts.keys(),
                autopct="%1.1f%%",
                startangle=90,
            )
            ax1.axis("equal")
            st.markdown("#### Verteilung der Hauptkategorien")
            st.pyplot(fig1)

            # === 2.–4. Subkategorien-PieCharts je Hauptkategorie
            for haupt in haupt_counts.keys():
                subkats = [
                    sub
                    for sub in sub_counts
                    if sub
                    in fragen_df.loc[
                        (fragen_df["Kategorie A"] == haupt), "Subkategorie A"
                    ].values
                    or sub
                    in fragen_df.loc[
                        (fragen_df["Kategorie B"] == haupt), "Subkategorie B"
                    ].values
                ]

                if subkats:
                    fig, ax = plt.subplots()
                    werte = [sub_counts[s] for s in subkats]
                    ax.pie(werte, labels=subkats, autopct="%1.1f%%", startangle=90)
                    ax.axis("equal")
                    st.markdown(f"#### Subkategorien: {haupt}")
                    st.pyplot(fig)
