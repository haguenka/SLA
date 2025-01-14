import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import requests
from io import BytesIO
import numpy as np
import os
import re

# Streamlit app
@st.cache_data
def load_logo(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

@st.cache_data
def load_excel(file):
    return pd.read_excel(file)

@st.cache_data
def load_excel_from_github():
    try:
        url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_excel(BytesIO(response.content))
    except requests.exceptions.RequestException:
        return None

def main():
    st.title("Análise IBAM")

    # Load and display logo from GitHub
    url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
    logo = load_logo(url)
    st.sidebar.image(logo, use_container_width=True)

    # Load Excel file from GitHub if available
    df = load_excel_from_github()

    # File upload if GitHub file is not available
    if df is None:
        st.sidebar.header("Carregar arquivo")
        uploaded_file = st.sidebar.file_uploader("Escolher um arquivo Excel", type=['xlsx'])
        if uploaded_file is not None:
            df = load_excel(uploaded_file)
        else:
            st.warning("Nenhum arquivo disponível. Por favor, carregue um arquivo Excel.")
            return

    try:
        # Verifica a existência de colunas essenciais
        if 'MEDICO_SOLICITANTE' not in df.columns:
            st.error("'MEDICO_SOLICITANTE' column not found in the data.")
            return

        if 'UNIDADE' not in df.columns or 'TIPO_ATENDIMENTO' not in df.columns:
            st.error("'UNIDADE' or 'TIPO_ATENDIMENTO' column not found.")
            return

        # Padroniza 'MEDICO_SOLICITANTE'
        df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].astype(str).str.strip().str.lower()

        # Exclude rows with NaN in 'MEDICO_SOLICITANTE', 'UNIDADE', or 'TIPO_ATENDIMENTO'
        df = df.dropna(subset=['MEDICO_SOLICITANTE', 'UNIDADE', 'TIPO_ATENDIMENTO'])

        # Filtro de grupos
        allowed_groups = [
            'GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA',
            'GRUPO RAIO-X', 'GRUPO MAMOGRAFIA',
            'GRUPO MEDICINA NUCLEAR', 'GRUPO ULTRASSOM'
        ]
        df = df[df['GRUPO'].isin(allowed_groups)]

        # Conversão de colunas em datetime
        df['STATUS_ALAUDAR'] = pd.to_datetime(df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')
        df['STATUS_PRELIMINAR'] = pd.to_datetime(df['STATUS_PRELIMINAR'], dayfirst=True, errors='coerce')
        df['STATUS_APROVADO'] = pd.to_datetime(df['STATUS_APROVADO'], dayfirst=True, errors='coerce')

        # Remove linhas sem STATUS_PRELIMINAR e STATUS_APROVADO (ambos vazios)
        df = df.dropna(subset=['STATUS_PRELIMINAR', 'STATUS_APROVADO'], how='all')

        # Selections
        unidade = st.sidebar.selectbox("Selecione a Unidade", options=df['UNIDADE'].dropna().unique())
        date_range = st.sidebar.date_input("Selecione o Período", [])
        tipo_atendimento = st.sidebar.selectbox("Selecione o Tipo de Atendimento", options=df['TIPO_ATENDIMENTO'].dropna().unique())

        # Filtrar com base nas seleções
        filtered_df = df[(df['UNIDADE'] == unidade) & (df['TIPO_ATENDIMENTO'] == tipo_atendimento)]
        if date_range:
            if len(date_range) == 2:
                start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
                filtered_df = filtered_df[(filtered_df['STATUS_ALAUDAR'] >= start_date) & (filtered_df['STATUS_ALAUDAR'] <= end_date)]

        # Display filtered data
        st.subheader("Dados Filtrados")
        st.dataframe(filtered_df)

        # Calcular os top 10 médicos solicitantes
        top_doctors = filtered_df['MEDICO_SOLICITANTE'].value_counts().head(10)

        # Contar exames por médico (apenas para os top 10)
        top_doctor_exam_counts = (
            filtered_df[filtered_df['MEDICO_SOLICITANTE'].isin(top_doctors.index)]
            .groupby(['MEDICO_SOLICITANTE', 'GRUPO']).size()
            .unstack(fill_value=0)
        )

        # Add total count per group
        group_totals = top_doctor_exam_counts.sum().rename('Total')
        top_doctor_exam_counts = top_doctor_exam_counts.append(group_totals)

        st.subheader("Contagem de Exames por Médico (Top 10)")
        st.dataframe(top_doctor_exam_counts)

        # Gerar gráfico
        st.subheader("Top 10 Médicos Solicitantes")
        if not top_doctors.empty:
            fig, ax = plt.subplots()
            top_doctors.plot(kind='bar', ax=ax, color='skyblue')
            ax.set_title("Top 10 Médicos Solicitantes")
            ax.set_ylabel("Quantidade de Solicitações")
            ax.set_xlabel("Médicos")

            # Annotate with total counts
            for i, v in enumerate(top_doctors):
                ax.text(i, v + 0.5, str(v), ha='center', va='bottom', fontsize=10)

            st.pyplot(fig)
        else:
            st.write("Nenhum dado disponível para o filtro selecionado.")

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()
