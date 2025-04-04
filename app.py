import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import matplotlib.pyplot as plt
import traceback

# === CONFIG ===
FRAGEN_DATEI = "implizite_fragen_ecosystem_services.csv"
GOOGLE_SHEET_NAME = "Solarumfrage_Antworten"
CPT_TEMPLATE_SHEET = "Templates_CPT_Matrices"
CPT_OUTPUT_SHEET = "CPT_Matrices"
CREDENTIALS_FILE = "credentials.json"
EXPERTEN_PASSWORT = "Solar"
# CPT-Kürzel → Klartextname (Dropdown-Anzeige)
CPT_MAPPINGS = {
    "SR": "Sediment retention",
    "FF": "Suitability for Agriculture",
    "POL": "Pollinator abundance",
    "REC": "Recreational potential",
    "LI": "Picture taking",
    "ID": "Emblematic species",
    "CAR": "Carbon stored biomass",
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


# === CPT MATRIX TAB ===
def experten_tab():
    st.subheader("🔐 Experten-Zugang")
    pw = st.text_input("Passwort", type="password")
    if pw != EXPERTEN_PASSWORT:
        st.warning("Bitte Passwort eingeben.")
        return

    st.success("Zugang gewährt – bitte CPT-Matrix auswählen und ausfüllen.")
    name = st.text_input("Name (freiwillig):")

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
        "Wähle einen Ecosystem Service", list(CPT_MAPPINGS.values())
    )
    sheet_key = reverse_mapping[selected_label]

    try:
        ws = template_sheet.worksheet(sheet_key)
        df = pd.DataFrame(ws.get_all_values())

        df.columns = df.iloc[0]
        df = df[1:]
        df = df.set_index(df.columns[0])

        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.fillna(0.0)
    except Exception as e:
        traceback.print_exc()
        st.error(f"Fehler beim Laden und Vorverarbeiten der Matrix '{sheet_key}'.")
        return

    try:
        st.markdown(f"### Matrix: {selected_label} ({sheet_key})")
        editable_df = st.data_editor(df, key=f"{sheet_key}_editor")
    except Exception as e:
        traceback.print_exc()
        st.error("Fehler beim Anzeigen der bearbeitbaren Matrix.")
        return

    # Nur prüfen & speichern wenn Button gedrückt wird
    if st.button(f"Matrix '{selected_label}' absenden"):
        try:
            # === Validierung ===
            valid = True
            for idx, row in editable_df.iterrows():
                row_sum = row.sum()
                if abs(row_sum - 1.0) > 0.01:
                    valid = False
                    st.error(
                        f"⚠️ Zeile '{idx}' summiert sich zu {row_sum:.2f} statt 1.0"
                    )

            if not valid:
                st.warning("Bitte korrigiere die Matrix bevor du sie absendest.")
                return

            # === Flatten & speichern ===
            now = datetime.now().isoformat()
            flat_data = {
                "Zeit": now,
                "Name": name,
                "Matrix": sheet_key,
                "Service": selected_label,
            }
            for row in editable_df.index:
                for col in editable_df.columns:
                    key = f"{row} → {col}"
                    flat_data[key] = editable_df.loc[row, col]

            try:
                sheet = output_sheet.worksheet(sheet_key)
            except gspread.exceptions.WorksheetNotFound:
                sheet = output_sheet.add_worksheet(
                    title=sheet_key, rows="100", cols="30"
                )

            headers = sheet.row_values(1)
            if not headers:
                sheet.append_row(list(flat_data.keys()))
                headers = flat_data.keys()

            sheet.append_row([flat_data.get(h, "") for h in headers])
            st.success(f"Matrix '{selected_label}' erfolgreich gespeichert!")

        except Exception as e:
            traceback.print_exc()
            st.error("Fehler beim Verarbeiten oder Speichern der Matrix.")


# === HAUPTTAB ===
def umfrage_tab():
    try:
        fragen_df = pd.read_csv(FRAGEN_DATEI)
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
    st.markdown(
        "Bitte beantworte die folgenden Fragen ehrlich. Es gibt keine richtigen oder falschen Antworten."
    )

    st.subheader("Allgemeine Informationen")
    nutzer_id = st.text_input("Deine ID oder Initialen (freiwillig):")
    stakeholder_typ = st.selectbox(
        "Ich bin ...",
        [
            "Bitte auswählen",
            "Anwohnende:r",
            "Landwirt:in",
            "Tourist:in",
            "Experte:in",
            "Naturschützer:in",
            "Andere",
        ],
    )

    st.markdown("---")
    st.subheader("Fragen")
    antworten = {}
    for idx, row in fragen_df.iterrows():
        frage = row["Frage"]
        optionen = (row["Option A"], row["Option B"])
        st.markdown(f"**{frage}**")
        antwort = st.radio(
            frage,
            optionen,
            index=None,
            key=f"frage_{idx}",
            label_visibility="collapsed",
        )
        antworten[f"Frage_{idx + 1}"] = antwort

    if st.button("Antworten absenden"):
        if stakeholder_typ == "Bitte auswählen":
            st.warning("Bitte wähle einen Stakeholder-Typ aus.")
        else:
            haupt_counts = {cat: 0 for cat in alle_hauptkategorien}
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

            antwortzeile = {
                "Zeitstempel": datetime.now().isoformat(),
                "Teilnehmer": nutzer_id,
                "Stakeholder": stakeholder_typ,
                "Versorgungsleistungen": haupt_counts["Versorgungsleistungen"],
                "Regulierungsleistungen": haupt_counts["Regulierungsleistungen"],
                "Kulturelle Leistungen": haupt_counts["Kulturelle Leistungen"],
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


# === TABS ===
tab1, tab2 = st.tabs(["🌿 Umfrage", "📊 Experten (CPT-Matrix)"])
with tab1:
    umfrage_tab()
with tab2:
    experten_tab()
