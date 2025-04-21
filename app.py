import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import matplotlib.pyplot as plt
import traceback
import random

# === CONFIG ===
FRAGEN_DATEI = "implizite_fragen_ecosystem_services.csv"
GOOGLE_SHEET_NAME = "Solarumfrage_Antworten"
CPT_TEMPLATE_SHEET = "Templates_CPT_Matrices"
CPT_OUTPUT_SHEET = "CPT_Matrices"
CREDENTIALS_FILE = "credentials.json"
EXPERTEN_PASSWORT = "Solar"
# CPT-Kürzel → Klartextname (Dropdown-Anzeige)
CPT_MAPPINGS = {
    "FF": "Suitability for Agriculture",
    "MAT": "Wood Provision Potential",
    "WY": "Annual Water Yield",
    "REC": "Recreational potential",
    "LI": "Picture taking",
    "ID": "Emblematic species",
    "SR": "Sediment retention",
    "CAR": "Carbon stored biomass",
    "AIR": "Removal of PM10 by vegetation",
    "HAB": "Habitat quality",
}


# === GOOGLE SHEETS SETUP ===
def init_gsheet(sheet_name):
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
    return client.open(sheet_name)


def speichere_antwort_in_sheet(antwortzeile):
    try:
        sheet = init_gsheet(GOOGLE_SHEET_NAME).sheet1
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


def set_button_style():
    st.markdown(
        """
    <style>
    div[role="radiogroup"] > label {
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

    /* Light Mode Styles */
    @media (prefers-color-scheme: light) {
        div[role="radiogroup"] > label {
            background: #f7f7f7;
            color: black;
        }
        div[role="radiogroup"] > label:hover {
            border-color: #4e8cff;
            background-color: #eef5ff;
        }
        div[role="radiogroup"] > label[data-selected="true"] {
            background-color: #d9eaff !important;
            border-color: #4e8cff;
        }
    }

    /* Dark Mode Styles */
    @media (prefers-color-scheme: dark) {
        div[role="radiogroup"] > label {
            background: #2a2a2a;
            color: white;
        }
        div[role="radiogroup"] > label:hover {
            border-color: #91c2ff;
            background-color: #3a3a3a;
        }
        div[role="radiogroup"] > label[data-selected="true"] {
            background-color: #1f4e79 !important;
            border-color: #91c2ff;
        }
    }

    div[role="radiogroup"] svg {
        width: 1.2rem;
        height: 1.2rem;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


# === CPT MATRIX TAB ===
def experten_tab():
    st.subheader("🔐 Experten-Zugang")

    try:
        template_sheet = init_gsheet(CPT_TEMPLATE_SHEET)
        output_sheet = init_gsheet(CPT_OUTPUT_SHEET)
    except Exception as e:
        traceback.print_exc()
        st.error("Fehler beim Laden der Google Sheets.")
        return

    st.markdown("---")

    reverse_mapping = {v: k for k, v in CPT_MAPPINGS.items()}
    selected_label = st.selectbox(
        "Wählen Sie einen Ecosystem Service", list(CPT_MAPPINGS.values())
    )
    sheet_key = reverse_mapping[selected_label]

    try:
        ws = template_sheet.worksheet(sheet_key)
        df = pd.DataFrame(ws.get_all_values())

        df.columns = df.iloc[0]
        df = df[1:]
        df = df.set_index(df.columns[0])
    except Exception as e:
        traceback.print_exc()
        st.error(f"Fehler beim Laden und Vorverarbeiten der Matrix '{sheet_key}'.")
        return

    try:
        st.markdown(f"### Matrix: {selected_label} ({sheet_key})")

        df_info = pd.read_csv("ecosystem_service_beschreibungen.csv", sep=";")
        beschreibung = df_info[df_info["Code"] == sheet_key]["Description"].values[0]
        st.info(f"ℹ️ {beschreibung}")

        st.markdown(
            "Bitte wählen Sie für jede Zeile die Option, die Ihrer Meinung nach die grösste Auswirkung hat."
        )

        selection = {}
        for col in df.columns:
            st.markdown(
                f"**Wie schätzen Sie die Auswirkungen ein, wenn der dargebotene Ecosystem Service {selected_label} `{col}` ist?**"
            )
            zeilenoptionen = df.index.tolist()
            # Default: erste Option ausgewählt
            selection[col] = st.radio(
                label=f"Auswirkung bei '{col}'",
                options=zeilenoptionen,
                key=f"radio_{sheet_key}_{col}",
                index=None,
            )
    except Exception as e:
        traceback.print_exc()
        st.error("Fehler beim Anzeigen der Matrixfragen.")
        return

    if st.button(f"Matrix '{selected_label}' absenden"):
        try:
            now = datetime.now().isoformat()
            antwortzeile = {
                "Zeit": now,
                "Matrix": sheet_key,
            }
            for col in df.columns:
                antwortzeile[col] = selection[col]

            try:
                sheet = output_sheet.worksheet("Antworten")
            except gspread.exceptions.WorksheetNotFound:
                sheet = output_sheet.add_worksheet(
                    title="Antworten", rows="100", cols="30"
                )

            headers = sheet.row_values(1)
            if not headers:
                sheet.append_row(list(antwortzeile.keys()))
                headers = list(antwortzeile.keys())

            sheet.append_row([antwortzeile.get(h, "") for h in headers])
            st.success(f"Matrix '{selected_label}' erfolgreich gespeichert!")
            st.info(
                "Vielen Dank für Ihre Teilnahme! Sie können im Dropdown weitere Ecosystem Services auswählen, um weitere Matrizen auszufüllen."
            )
        except Exception as e:
            traceback.print_exc()
            st.error("Fehler beim Verarbeiten oder Speichern der Matrix.")


# === Public Tab ===
def umfrage_tab():
    try:
        fragen_df = pd.read_csv(FRAGEN_DATEI, sep=";")
    except FileNotFoundError:
        st.error(f"Fragen-Datei '{FRAGEN_DATEI}' nicht gefunden.")
        st.stop()

    alle_hauptkategorien = sorted(
        set(fragen_df["Kategorie A"]).union(set(fragen_df["Kategorie B"]))
    )
    alle_subkategorien = sorted(
        set(fragen_df["Subkategorie A"]).union(set(fragen_df["Subkategorie B"]))
    )

    st.title("Umfrage: Bedeutung von Landschaftsmerkmalen")
    set_button_style()
    st.markdown("""
**Bitte beantworte die folgenden Fragen. Es gibt keine richtigen oder falschen Antworten.**

👉 In jeder Frage siehst du zwei kurze Beschreibungen von Landschaftsmerkmalen oder Eindrücken, die man in den Alpen erleben kann.  
Bitte wähle jeweils die Option aus, die **dich persönlich mehr anspricht** – ganz nach deinem Gefühl oder deiner Vorliebe.

So hilfst du uns zu verstehen, welche Eigenschaften einer Landschaft den Menschen besonders wichtig erscheinen – z. B. für Erholung, Artenvielfalt oder Luftqualität.
""")

    st.subheader("Allgemeine Informationen")
    plz = st.text_input(
        "Bitte gib die ersten zwei Ziffern deiner Postleitzahl ein:",
        max_chars=2,
    )

    st.markdown("---")
    st.subheader("Fragen")

    # Checkbox für kürzere Umfrage
    kurze_umfrage = st.checkbox("Ich möchte nur eine verkürzte Umfrage ausfüllen")

    # Anzahl gewünschter Fragen (z. B. 6 Fragen in der kurzen Version)
    anzahl_kurz = 10
    if "random_state" not in st.session_state:
        st.session_state["random_state"] = random.randint(0, 10_000)
    random_state = st.session_state["random_state"]

    # Fragen vorbereiten
    if kurze_umfrage:
        st.info(f"Du erhältst eine verkürzte Umfrage mit {anzahl_kurz} Fragen.")

        sampled_df = pd.DataFrame()
        used_indices = set()
        fragen_pro_kategorie = anzahl_kurz // 3

        for haupt in ["Provisioning", "Regulation & maintaining", "Cultural services"]:
            fragen_in_kat = fragen_df[
                (
                    (fragen_df["Kategorie A"] == haupt)
                    | (fragen_df["Kategorie B"] == haupt)
                )
                & (~fragen_df.index.isin(used_indices))
            ]
            sampled = fragen_in_kat.sample(
                min(fragen_pro_kategorie, len(fragen_in_kat)),
                random_state=random_state,
            )
            used_indices.update(sampled.index)
            sampled_df = pd.concat([sampled_df, sampled])

        # Fill up if still short
        fehlend = anzahl_kurz - len(sampled_df)
        if fehlend > 0:
            rest = fragen_df[~fragen_df.index.isin(used_indices)]
            sampled_rest = rest.sample(
                min(fehlend, len(rest)),
                random_state=random_state,
            )
            sampled_df = pd.concat([sampled_df, sampled_rest])
            used_indices.update(sampled_rest.index)
        fragen_aktiv = sampled_df
    else:
        fragen_aktiv = fragen_df

    antworten = {}
    for i, (_, row) in enumerate(fragen_aktiv.iterrows()):
        frage = row["Frage"]
        optionen = (row["Option A"], row["Option B"])
        st.markdown(f"**Frage {i + 1}: {frage}**")
        antwort = st.radio(
            frage,
            optionen,
            index=None,
            key=f"frage_{i}",  # i ist garantiert eindeutig und fortlaufend
            label_visibility="collapsed",
        )
        antworten[f"Frage_{i + 1}"] = antwort

    if st.button("Antworten absenden"):
        if stakeholder_typ == "Bitte auswählen":
            st.warning("Bitte wähle einen Stakeholder-Typ aus.")
        if not plz.isdigit() or len(plz) != 2:
            st.warning("Bitte gib genau zwei Ziffern bei PLZ ein.")
        else:
            haupt_counts = {cat: 0 for cat in alle_hauptkategorien}
            sub_counts = {}

            for i, (_, row) in enumerate(fragen_aktiv.iterrows()):
                frage_key = f"Frage_{i + 1}"
                if frage_key not in antworten:
                    continue  # z. B. Frage nicht beantwortet
                antwort = antworten[frage_key]
                if antwort == row["Option A"]:
                    sub = row["Subkategorie A"]
                    cat = row["Kategorie A"]
                else:
                    sub = row["Subkategorie B"]
                    cat = row["Kategorie B"]
                haupt_counts[cat] += 1
                sub_counts[sub] = sub_counts.get(sub, 0) + 1

            antwortzeile = {
                "Zeitstempel": datetime.now().isoformat(),
                "Stakeholder": st.session_state["stakeholder_typ"],
                "PLZ": plz,
                "Regulation & maintaining": haupt_counts["Regulation & maintaining"],
                "Cultural services": haupt_counts["Cultural services"],
                "Provisioning": haupt_counts["Provisioning"],
            }

            for sub in alle_subkategorien:
                antwortzeile[f"Subkategorie: {sub}"] = sub_counts.get(sub, 0)

            antwortzeile.update(antworten)
            erfolg, fehler = speichere_antwort_in_sheet(antwortzeile)
            if erfolg:
                st.success("Vielen Dank! Deine Antworten wurden gespeichert.")
            else:
                st.error(f"Fehler beim Speichern in Google Sheets: {fehler}")

            st.markdown("---")
            st.subheader("🧮 Deine Prioritäten auf einen Blick")

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


# === AUSWAHL STAKEHOLDER TYP ===
st.title("🌍 Teilnahme an der Umfrage")
stakeholder_typ = st.selectbox(
    "Bitte wähle deine Rolle:",
    [
        "Bitte auswählen",
        "Allgemeinheit",
        "Experte:in",
    ],
)

# Speichere Auswahl
st.session_state["stakeholder_typ"] = stakeholder_typ

# === EXPERTENPFAD ===
if stakeholder_typ == "Experte:in":
    pw = st.text_input("🔐 Bitte gib das Expertenpasswort ein:", type="password")
    if pw != EXPERTEN_PASSWORT:
        st.warning("Bitte korrektes Passwort eingeben.")
    else:
        try:
            with open("consent_expert_de.md", "r", encoding="utf-8") as file:
                consent_md = file.read()
            st.markdown(consent_md)
        except FileNotFoundError:
            st.warning("Consent-Datei für Experten nicht gefunden.")
            st.stop()

        st.markdown("---")

        st.session_state["consent_given"] = st.checkbox("Einverstanden")

        if st.session_state.get("consent_given"):
            experten_tab()

# === PUBLIC-PFAD ===
elif stakeholder_typ != "Bitte auswählen":
    try:
        with open("consent_public_de.md", "r", encoding="utf-8") as file:
            consent_md = file.read()
        st.markdown(consent_md)
    except FileNotFoundError:
        st.warning("Consent-Datei für Public nicht gefunden.")
        st.stop()

    st.markdown("---")

    st.session_state["consent_given"] = st.checkbox("Einverstanden")

    if st.session_state.get("consent_given"):
        umfrage_tab()
