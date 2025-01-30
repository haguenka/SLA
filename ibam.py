import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import requests
from io import BytesIO
import numpy as np

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

def main():
    st.title("Análise IBAM")

    # Load and display logo from GitHub
    url_logo = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
    logo = load_logo(url_logo)
    st.sidebar.image(logo, use_container_width=True)

    # Load primary dataset (SLA)
    url_sla = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
    df = load_excel_from_github(url_sla)

    # Load secondary dataset (Consultas)
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
        if any(col not in df.columns for col in required_columns):
            st.error(f"Colunas faltando no dataset SLA: {', '.join([col for col in required_columns if col not in df.columns])}")
            return

        required_columns_consultas = ['Prestador', 'Paciente', 'Data', 'Convênio']
        if any(col not in df_consultas.columns for col in required_columns_consultas):
            st.error(f"Colunas faltando no dataset Consultas: {', '.join([col for col in required_columns_consultas if col not in df_consultas.columns])}")
            return

        # Padroniza 'MEDICO_SOLICITANTE' e 'PRESTADOR'
        df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].astype(str).str.strip().str.lower()
        df_consultas['Prestador'] = df_consultas['Prestador'].astype(str).str.strip().str.lower()
        df_consultas['Convênio'] = df_consultas['Convênio'].astype(str).str.strip().str.upper()  # Padronizar convênios

        # Filtro de grupos
        allowed_groups = [
            'GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA',
            'GRUPO RAIO-X', 'GRUPO MAMOGRAFIA',
            'GRUPO MEDICINA NUCLEAR', 'GRUPO ULTRASSOM'
        ]
        df = df[df['GRUPO'].isin(allowed_groups)]

        # Conversão de colunas em datetime
        df['STATUS_ALAUDAR'] = pd.to_datetime(df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')
        df.rename(columns={'STATUS_ALAUDAR': 'Data'}, inplace=True)
        df_consultas['Data'] = pd.to_datetime(df_consultas['Data'], dayfirst=True, errors='coerce')

        # Selections
        unidade = st.sidebar.selectbox("Selecione a Unidade", options=df['UNIDADE'].unique())
        date_range = st.sidebar.date_input("Selecione o Período", [])

        # Garantir que o dataframe filtrado não esteja vazio antes de selecionar médicos
        filtered_df = df[df['UNIDADE'] == unidade]

        if date_range and len(date_range) == 2:
            start_date = pd.to_datetime(date_range[0])  
            end_date = pd.to_datetime(date_range[1])  

            filtered_df = filtered_df[(filtered_df['Data'] >= start_date) & (filtered_df['Data'] <= end_date)]
            df_consultas = df_consultas[(df_consultas['Data'] >= start_date) & (df_consultas['Data'] <= end_date)]

        if filtered_df.empty:
            st.warning("Nenhum dado disponível para o período selecionado.")
            return

        # Seleção de Médico Prescritor
        selected_doctor = st.sidebar.selectbox("Selecione o Médico Prescritor", options=filtered_df['MEDICO_SOLICITANTE'].unique())

        # Filtrar dados pelo médico selecionado
        doctor_df = filtered_df[filtered_df['MEDICO_SOLICITANTE'] == selected_doctor]
        consultas_doctor_df = df_consultas[df_consultas['Prestador'] == selected_doctor] if selected_doctor in df_consultas['Prestador'].values else pd.DataFrame()

        # Exibir consultas do médico selecionado
        st.subheader(f"Consultas - Total de Pacientes: {len(consultas_doctor_df)}")
        st.dataframe(consultas_doctor_df)

        # Criar a lista de convênios atendidos pelo médico e a contagem de atendimentos
        if not consultas_doctor_df.empty:
            convenio_counts = consultas_doctor_df['Convênio'].value_counts().reset_index()
            convenio_counts.columns = ['Convênio', 'Total de Atendimentos']

            st.subheader(f"Convênios Atendidos - Total: {len(convenio_counts)}")
            st.dataframe(convenio_counts)

        # Exibir tabelas de pacientes por modalidade no SLA dataset
        if not doctor_df.empty:
            for modality in doctor_df['GRUPO'].unique():
                modality_df = doctor_df[doctor_df['GRUPO'] == modality][['NOME_PACIENTE', 'SAME', 'Data', 'GRUPO', 'TIPO_ATENDIMENTO', 'MEDICO_SOLICITANTE']]
                st.subheader(f"{modality} - Total de Exames: {len(modality_df)}")
                st.dataframe(modality_df)

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()
