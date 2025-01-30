import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import requests
from io import BytesIO
import numpy as np
from fuzzywuzzy import fuzz, process

# Streamlit app
@st.cache_data
def load_logo(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

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

def match_names_fuzzy(consulta_name, solicitante_names, threshold=70):
    """ Realiza fuzzy matching entre um nome e uma lista de nomes """
    match, score = process.extractOne(consulta_name, solicitante_names, scorer=fuzz.token_sort_ratio)
    return match if score >= threshold else None

def highlight_rows(row):
    """ Destaca toda a linha em amarelo se houver match """
    if pd.notna(row['Destaque']):
        return ['background-color: yellow'] * len(row)
    return [''] * len(row)

def main():
    st.title("Análise IBAM")

    # Load and display logo from GitHub
    url_logo = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
    logo = load_logo(url_logo)
    st.sidebar.image(logo, use_container_width=True)

    # Load datasets
    url_sla = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
    df = load_excel_from_github(url_sla)

    url_lista = 'https://raw.githubusercontent.com/haguenka/SLA/main/lista.xlsx'
    df_consultas = load_excel_from_github(url_lista)

    # Verifica se os arquivos foram carregados corretamente
    if df is None or df_consultas is None:
        st.sidebar.header("Carregar arquivo")
        uploaded_file = st.sidebar.file_uploader("Escolher um arquivo Excel", type=['xlsx'])
        if uploaded_file is not None:
            df = load_excel(uploaded_file)
        else:
            st.warning("Nenhum arquivo disponível. Por favor, carregue um arquivo Excel.")
            return

    try:
        # Verifica a existência de colunas essenciais
        required_columns = ['MEDICO_SOLICITANTE', 'NOME_PACIENTE', 'SAME', 'STATUS_ALAUDAR', 'UNIDADE', 'TIPO_ATENDIMENTO', 'GRUPO']
        required_columns_consultas = ['Prestador', 'Paciente', 'Data']

        if 'Convênio' in df_consultas.columns:
            required_columns_consultas.append('Convênio')

        if any(col not in df.columns for col in required_columns):
            st.error(f"Colunas faltando no dataset SLA: {', '.join([col for col in required_columns if col not in df.columns])}")
            return

        if any(col not in df_consultas.columns for col in required_columns_consultas):
            st.error(f"Colunas faltando no dataset Consultas: {', '.join([col for col in required_columns_consultas if col not in df_consultas.columns])}")
            return

        # Padronizar colunas
        df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].str.strip().str.lower()
        df_consultas['Prestador'] = df_consultas['Prestador'].str.strip().str.lower()

        if 'Convênio' in df_consultas.columns:
            df_consultas['Convênio'] = df_consultas['Convênio'].str.strip().str.upper()

        # 🔹 **Fuzzy Matching entre "Prestador" e "MEDICO_SOLICITANTE"**
        solicitantes = df['MEDICO_SOLICITANTE'].unique()
        df_consultas['Matched_Medico'] = df_consultas['Prestador'].apply(lambda x: match_names_fuzzy(x, solicitantes))

        # 🔹 **Remover registros sem correspondência**
        df_consultas.dropna(subset=['Matched_Medico'], inplace=True)
        df_consultas['Matched_Medico'] = df_consultas['Matched_Medico'].str.lower()

        # 🔹 **Converter "STATUS_ALAUDAR" para datetime**
        df['STATUS_ALAUDAR'] = pd.to_datetime(df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['STATUS_ALAUDAR'])  # Remove valores inválidos
        df.rename(columns={'STATUS_ALAUDAR': 'Data'}, inplace=True)

        df_consultas['Data'] = pd.to_datetime(df_consultas['Data'], dayfirst=True, errors='coerce')

        # Filtragem por período
        unidade = st.sidebar.selectbox("Selecione a Unidade", options=df['UNIDADE'].unique())
        date_range = st.sidebar.date_input("Selecione o Período", [])

        filtered_df = df[df['UNIDADE'] == unidade]

        if date_range and len(date_range) == 2:
            start_date = pd.to_datetime(date_range[0])  
            end_date = pd.to_datetime(date_range[1])  
            
            filtered_df = filtered_df[(filtered_df['Data'] >= start_date) & (filtered_df['Data'] <= end_date)]
            df_consultas = df_consultas[(df_consultas['Data'] >= start_date) & (df_consultas['Data'] <= end_date)]

        if filtered_df.empty:
            st.warning("Nenhum dado disponível para o período selecionado.")
            return

        # Usar o nome consolidado (Matched_Medico) para o menu
        selected_doctor = st.sidebar.selectbox("Selecione o Médico Prescritor", options=df_consultas['Matched_Medico'].unique())

        # 🔹 **Filtrar exames e consultas usando o nome consolidado**
        exames_doctor_df = filtered_df[filtered_df['MEDICO_SOLICITANTE'] == selected_doctor]
        consultas_doctor_df = df_consultas[df_consultas['Matched_Medico'] == selected_doctor]

        # 🔹 **Marcar pacientes encontrados nos exames**
        exam_patients = set(exames_doctor_df['NOME_PACIENTE'].dropna().str.lower())

        if not consultas_doctor_df.empty:
            consultas_doctor_df['Destaque'] = consultas_doctor_df['Paciente'].apply(lambda x: match_names_fuzzy(x.lower(), exam_patients))

        if not exames_doctor_df.empty:
            exames_doctor_df['Destaque'] = exames_doctor_df['NOME_PACIENTE'].apply(lambda x: match_names_fuzzy(x.lower(), set(consultas_doctor_df['Paciente'].dropna().str.lower())))

        # 🔹 **Exibir lista de exames por modalidade separadamente**
        st.subheader(f"Exames por Modalidade - {selected_doctor.capitalize()}")
        if not exames_doctor_df.empty:
            for modalidade in exames_doctor_df['GRUPO'].unique():
                exames_mod_df = exames_doctor_df[exames_doctor_df['GRUPO'] == modalidade]
                total_exames = len(exames_mod_df)
                total_grifados = exames_mod_df['Destaque'].notna().sum()
                st.subheader(f"{modalidade} - Total: {total_exames} (Grifados: {total_grifados})")
                st.dataframe(exames_mod_df.style.apply(highlight_rows, axis=1))
        else:
            st.warning("Nenhum exame encontrado para este médico.")

        # 🔹 **Exibir lista de consultas destacadas**
        st.subheader(f"Consultas - Total de Pacientes: {len(consultas_doctor_df)}")
        if not consultas_doctor_df.empty:
            st.dataframe(consultas_doctor_df.style.apply(highlight_rows, axis=1))
        else:
            st.warning("Nenhuma consulta encontrada para este médico.")

        # 🔹 **Criar lista de convênios atendidos pelo médico**
        if 'Convênio' in df_consultas.columns and not consultas_doctor_df.empty:
            convenio_counts = consultas_doctor_df['Convênio'].value_counts().reset_index()
            convenio_counts.columns = ['Convênio', 'Total de Atendimentos']
            st.subheader(f"Convênios Atendidos - Total: {len(convenio_counts)}")
            st.dataframe(convenio_counts)
        else:
            st.warning("Nenhuma informação de convênio disponível para este médico.")

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()
