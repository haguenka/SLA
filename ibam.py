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

    # File upload if GitHub file is not available
    if df is None or df_consultas is None:
        st.sidebar.header("Carregar arquivo")
        uploaded_file = st.sidebar.file_uploader("Escolher um arquivo Excel", type=['xlsx'])
        if uploaded_file is not None:
            df = load_excel(uploaded_file)
        else:
            st.warning("Nenhum arquivo disponível. Por favor, carregue um arquivo Excel.")
            return

    try:
        # Verifica a existência de colunas essenciais no SLA dataset
        required_columns = ['MEDICO_SOLICITANTE', 'NOME_PACIENTE', 'SAME', 'STATUS_ALAUDAR', 'UNIDADE', 'TIPO_ATENDIMENTO', 'GRUPO']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error(f"As seguintes colunas estão faltando no dataset SLA: {', '.join(missing_columns)}")
            return

        # Verifica a existência de colunas essenciais no Consultas dataset
        required_columns_consultas = ['Prestador', 'Paciente', 'Data']
        missing_columns_consultas = [col for col in required_columns_consultas if col not in df_consultas.columns]

        if missing_columns_consultas:
            st.error(f"As seguintes colunas estão faltando no dataset Consultas: {', '.join(missing_columns_consultas)}")
            return

        # Padroniza 'MEDICO_SOLICITANTE' e 'PRESTADOR'
        df.loc[:, 'MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].astype(str).str.strip().str.lower()
        df_consultas.loc[:, 'Prestador'] = df_consultas['Prestador'].astype(str).str.strip().str.lower()

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
        tipo_atendimento = st.sidebar.selectbox("Selecione o Tipo de Atendimento", options=df['TIPO_ATENDIMENTO'].unique())

        # Filtrar SLA dataset
        filtered_df = df[(df['UNIDADE'] == unidade) & (df['TIPO_ATENDIMENTO'] == tipo_atendimento)]

        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[(filtered_df['Data'] >= start_date) & (filtered_df['Data'] <= end_date)]
            df_consultas = df_consultas[(df_consultas['Data'] >= start_date) & (df_consultas['Data'] <= end_date)]

        # Seleção de Médico Prescritor
        selected_doctor = st.sidebar.selectbox("Selecione o Médico Prescritor", options=filtered_df['MEDICO_SOLICITANTE'].unique())

        # Filtrar dados pelo médico selecionado no SLA dataset
        doctor_df = filtered_df[filtered_df['MEDICO_SOLICITANTE'] == selected_doctor]

        # Filtrar dados pelo médico selecionado no Consultas dataset
        consultas_doctor_df = df_consultas[df_consultas['Prestador'] == selected_doctor]

        # Exibir tabelas de pacientes por modalidade no SLA dataset
        if not doctor_df.empty:
            for modality in doctor_df['GRUPO'].unique():
                modality_df = doctor_df[doctor_df['GRUPO'] == modality][['NOME_PACIENTE', 'SAME', 'DATA', 'GRUPO', 'TIPO_ATENDIMENTO', 'MEDICO_SOLICITANTE']]
                st.subheader(f"{modality} - Total de Exames: {len(modality_df)}")
                st.dataframe(modality_df)

        # Exibir consultas do médico selecionado
        st.subheader(f"Consultas - Total de Pacientes: {len(consultas_doctor_df)}")
        st.dataframe(consultas_doctor_df)

        # Calcular o total de exames prescritos por médico (Top 10)
        exams_per_doctor = filtered_df.groupby('MEDICO_SOLICITANTE').size().nlargest(10)

        # Gráfico de médicos com total de exames prescritos (Top 10)
        st.subheader("Top 10 Médicos Prescritores - Exames Prescritos")
        if not exams_per_doctor.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            bars = ax.bar(exams_per_doctor.index, exams_per_doctor.values, color='skyblue')

            ax.set_title("Top 10 Médicos Prescritores - Exames Prescritos")
            ax.set_ylabel("Quantidade de Exames")
            ax.set_xlabel("Médicos")
            ax.set_xticks(range(len(exams_per_doctor.index)))
            ax.set_xticklabels(exams_per_doctor.index, rotation=45, ha='right')

            # Exibir números acima das barras
            for bar in bars:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2, str(int(bar.get_height())), 
                        ha='center', va='bottom', fontsize=10, fontweight='bold')

            st.pyplot(fig)
        else:
            st.write("Nenhum dado disponível para o filtro selecionado.")

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()
