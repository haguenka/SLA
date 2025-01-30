import streamlit as st
import pandas as pd
from fuzzywuzzy import fuzz, process

@st.cache_data
def load_excel(file):
    return pd.read_excel(file)

@st.cache_data
def load_excel_from_github(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_excel(BytesIO(response.content))
    except requests.exceptions.RequestException:
        return None

def match_names_fuzzy(name, name_list, threshold=70):
    match, score = process.extractOne(name, name_list, scorer=fuzz.token_sort_ratio)
    return match if score >= threshold else None

def highlight_rows(row):
    if pd.notna(row['Destaque']):
        return ['background-color: yellow'] * len(row)
    return [''] * len(row)

def main():
    st.title("Análise IBAM")

    # Carregar dados
    url_sla = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
    df = load_excel_from_github(url_sla)
    url_lista = 'https://raw.githubusercontent.com/haguenka/SLA/main/lista.xlsx'
    df_consultas = load_excel_from_github(url_lista)

    if df is None or df_consultas is None:
        st.error("Erro ao carregar os dados.")
        return

    # Normalizar dados
    df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].str.strip().str.lower()
    df_consultas['Prestador'] = df_consultas['Prestador'].str.strip().str.lower()

    # Aplicar fuzzy matching
    if 'Matched_Medico' not in df_consultas.columns:
        solicitantes = df['MEDICO_SOLICITANTE'].unique()
        df_consultas['Matched_Medico'] = df_consultas['Prestador'].apply(lambda x: match_names_fuzzy(x, solicitantes))

    # Seleção de período
    date_range = st.sidebar.date_input("Selecione o Período", [])
    if date_range:
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1])
        df = df[(df['Data'] >= start_date) & (df['Data'] <= end_date)]
        df_consultas = df_consultas[(df_consultas['Data'] >= start_date) & (df_consultas['Data'] <= end_date)]

    # Seleção de médico
    if not df_consultas.empty:
        selected_doctor = st.sidebar.selectbox("Selecione o Médico", df_consultas['Matched_Medico'].unique())
        exames_doctor_df = df[df['MEDICO_SOLICITANTE'] == selected_doctor]
        consultas_doctor_df = df_consultas[df_consultas['Matched_Medico'] == selected_doctor]

        st.subheader(f"Exames de {selected_doctor.capitalize()}")
        if not exames_doctor_df.empty:
            for modalidade in exames_doctor_df['GRUPO'].unique():
                exames_mod_df = exames_doctor_df[exames_doctor_df['GRUPO'] == modalidade]
                st.dataframe(exames_mod_df)

        st.subheader("Consultas")
        if not consultas_doctor_df.empty:
            st.dataframe(consultas_doctor_df)

if __name__ == "__main__":
    main()
