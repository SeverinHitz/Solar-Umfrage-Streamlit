import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import matplotlib.pyplot as plt

# === CONFIG ===
FRAGEN_DATEI = "implizite_fragen_ecosystem_services.csv"
GOOGLE_SHEET_NAME = "Solarumfrage_Antworten"
CREDENTIALS_FILE = "credentials.json"


# === GOOGLE SHEETS SETUP ===
def init_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            CREDENTIALS_FILE, scope
        )

    client = gspread.authorize(creds)
    return client.open(GOOGLE_SHEET_NAME).sheet1


# === SPEICHERN IN SHEET ===
def speichere_antwort_in_sheet(antwortzeile):
    try:
        sheet = init_gsheet()
        antwort_liste = [str(v) if v is not None else "" for v in antwortzeile.values()]
        existing_rows = sheet.get_all_values()
        if len(existing_rows) == 0 or all(
            cell.strip() == "" for cell in existing_rows[0]
        ):
            sheet.update(range_name="A1", values=[list(antwortzeile.keys())])
        sheet.append_row(antwort_liste)
        return True, None
    except Exception as e:
        return False, str(e)


# === STYLE ===
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
        div[role="radiogroup"] > label[data-selected="true"] {
            background-color: #d9eaff !important;
            border-color: #4e8cff;
        }
        div[role="radiogroup"] svg {
            width: 1.2rem;
            height: 1.2rem;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )


# === FRAGEN LADEN ===
try:
    fragen_df = pd.read_csv(FRAGEN_DATEI)
except FileNotFoundError:
    st.error(f"Fragen-Datei '{FRAGEN_DATEI}' nicht gefunden.")
    st.stop()

# Alle Subkategorien erfassen (für einheitliche Struktur)
alle_subkategorien = sorted(
    set(fragen_df["Subkategorie A"]).union(set(fragen_df["Subkategorie B"]))
)

# === UI ===
st.title("Umfrage: Bedeutung von Landschaftsmerkmalen")
set_button_style()
st.markdown(
    "Bitte beantworte die folgenden Fragen ehrlich. Es gibt keine richtigen oder falschen Antworten."
)

# === Nutzerinformationen ===
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

# === Fragen ===
st.markdown("---")
st.subheader("Fragen")
antworten = {}

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
        # Auswertung vorbereiten
        haupt_counts = {
            "Versorgungsleistungen": 0,
            "Regulierungsleistungen": 0,
            "Kulturelle Leistungen": 0,
        }
        sub_counts = {}

        for idx, row in fragen_df.iterrows():
            frage_key = f"Frage_{idx + 1}"
            antwort = antworten[frage_key]
            if antwort == row["Option A"]:
                sub = row["Subkategorie A"]
                cat = row["Kategorie A"]
            else:
                sub = row["Subkategorie B"]
                cat = row["Kategorie B"]

            haupt_counts[cat] += 1
            sub_counts[sub] = sub_counts.get(sub, 0) + 1

        # Antwortzeile vorbereiten
        antwortzeile = {
            "Zeitstempel": datetime.now().isoformat(),
            "Teilnehmer": nutzer_id,
            "Stakeholder": stakeholder_typ,
            "Versorgungsleistungen": haupt_counts["Versorgungsleistungen"],
            "Regulierungsleistungen": haupt_counts["Regulierungsleistungen"],
            "Kulturelle Leistungen": haupt_counts["Kulturelle Leistungen"],
        }

        # Subkategorie-Zählungen (auch 0-Werte sichern)
        for sub in alle_subkategorien:
            antwortzeile[f"Subkategorie: {sub}"] = sub_counts.get(sub, 0)

        # Alle Antworten pro Frage
        antwortzeile.update(antworten)

        # Speichern
        erfolg, fehler = speichere_antwort_in_sheet(antwortzeile)
        if erfolg:
            st.success("Vielen Dank! Deine Antworten wurden gespeichert.")
        else:
            st.error(f"Fehler beim Speichern in Google Sheets: {fehler}")

        # === VISUELLE AUSWERTUNG ===
        st.markdown("---")
        st.subheader("🧮 Deine Prioritäten auf einen Blick")

        # Hauptkategorien
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

        # Subkategorien nach Hauptkategorie
        for haupt in haupt_counts.keys():
            subkats = [
                sub
                for sub in sub_counts
                if sub
                in fragen_df.loc[
                    fragen_df["Kategorie A"] == haupt, "Subkategorie A"
                ].values
                or sub
                in fragen_df.loc[
                    fragen_df["Kategorie B"] == haupt, "Subkategorie B"
                ].values
            ]
            if subkats:
                fig, ax = plt.subplots()
                werte = [sub_counts[s] for s in subkats]
                ax.pie(werte, labels=subkats, autopct="%1.1f%%", startangle=90)
                ax.axis("equal")
                st.markdown(f"#### Subkategorien: {haupt}")
                st.pyplot(fig)
