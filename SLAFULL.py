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
        url = 'https://raw.githubusercontent.com/haguenka/SLA/main/basesla3.xlsx'
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_excel(BytesIO(response.content))
    except requests.exceptions.RequestException:
        return None

def is_weekend(date):
    return date.weekday() >= 5

def main():
    st.title("Análise de SLA Dashboard")

    # Load and display logo from GitHub
    url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
    logo = load_logo(url)
    st.sidebar.image(logo, use_column_width=True)

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
        # Ensure 'MEDICO_SOLICITANTE' column exists
        if 'MEDICO_SOLICITANTE' not in df.columns:
            st.error("'MEDICO_SOLICITANTE' column not found in the data.")
            return

        # Standardize 'MEDICO_SOLICITANTE' column to handle any inconsistencies in casing or extra spaces
        df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].astype(str).str.strip().str.lower()

        # Filter by GRUPO to include only specific groups
        allowed_groups = ['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO RAIO-X', 'GRUPO MAMOGRAFIA', 'GRUPO MEDICINA NUCLEAR', 'GRUPO ULTRASSOM']
        df = df[df['GRUPO'].isin(allowed_groups)]

        # Parse the relevant datetime columns explicitly with dayfirst=True
        df['STATUS_ALAUDAR'] = pd.to_datetime(df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')
        df['STATUS_PRELIMINAR'] = pd.to_datetime(df['STATUS_PRELIMINAR'], dayfirst=True, errors='coerce')
        df['STATUS_APROVADO'] = pd.to_datetime(df['STATUS_APROVADO'], dayfirst=True, errors='coerce')

        # Eliminate rows where both STATUS_PRELIMINAR and STATUS_APROVADO are null
        df = df.dropna(subset=['STATUS_PRELIMINAR', 'STATUS_APROVADO'], how='all')

        # Check if 'UNIDADE' and 'TIPO_ATENDIMENTO' exist
        if 'UNIDADE' not in df.columns or 'TIPO_ATENDIMENTO' not in df.columns:
            st.error("'UNIDADE' or 'TIPO_ATENDIMENTO' column not found.")
            return

        # Calculate DELTA_TIME excluding weekends, except for 'Pronto Atendimento'
        df['END_DATE'] = df['STATUS_PRELIMINAR'].fillna(df['STATUS_APROVADO'])
        df['DELTA_TIME'] = df.apply(
            lambda row: (np.busday_count(row['STATUS_ALAUDAR'].date(), row['END_DATE'].date()) * 24) + ((row['END_DATE'] - row['STATUS_ALAUDAR']).seconds // 3600)
            if row['TIPO_ATENDIMENTO'] != 'Pronto Atendimento' and not pd.isna(row['STATUS_ALAUDAR']) and not pd.isna(row['END_DATE'])
            else (row['END_DATE'] - row['STATUS_ALAUDAR']).total_seconds() / 3600,
            axis=1
        )

        # Define the conditions for SLA violations
        doctors_of_interest = ['henrique arume guenka', 'marcelo jacobina de abreu']
        condition_1 = (df['GRUPO'] == 'GRUPO MAMOGRAFIA') & (df['MEDICO_SOLICITANTE'].isin(doctors_of_interest)) & (df['DELTA_TIME'] > (10 * 24))
        condition_2 = (df['GRUPO'] == 'GRUPO MAMOGRAFIA') & (~df['MEDICO_SOLICITANTE'].isin(doctors_of_interest)) & (df['DELTA_TIME'] > 120)
        condition_3 = (df['GRUPO'] == 'GRUPO RAIO-X') & (df['DELTA_TIME'] > 72)
        condition_4 = (df['GRUPO'] == 'GRUPO MEDICINA NUCLEAR') & (df['DELTA_TIME'] > 120)
        condition_5 = (df['TIPO_ATENDIMENTO'] == 'Pronto Atendimento') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 1)
        condition_6 = (df['TIPO_ATENDIMENTO'] == 'Internado') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 24)
        condition_7 = (df['TIPO_ATENDIMENTO'] == 'Externo') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 96)

        # Set the default SLA status and apply conditions
        df['SLA_STATUS'] = 'SLA DENTRO DO PERÍODO'
        df.loc[condition_1 | condition_2 | condition_3 | condition_4 | condition_5 | condition_6 | condition_7, 'SLA_STATUS'] = 'SLA FORA DO PERÍODO'

        # Add an observation column for user input
        if 'OBSERVACAO' not in df.columns:
            df['OBSERVACAO'] = ''

        # Select only relevant columns
        selected_columns = [
            'SAME', 'NOME_PACIENTE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO', 'MEDICO_LAUDO_DEFINITIVO',
            'UNIDADE', 'TIPO_ATENDIMENTO', 'STATUS_ALAUDAR', 'STATUS_PRELIMINAR', 'STATUS_APROVADO', 'MEDICO_SOLICITANTE', 'DELTA_TIME', 'SLA_STATUS', 'OBSERVACAO'
        ]

        df_selected = df[selected_columns]

        # Sidebar dropdown for selecting UNIDADE, GRUPO, and TIPO_ATENDIMENTO
        unidade_options = df['UNIDADE'].unique()
        selected_unidade = st.sidebar.selectbox("Selecione a UNIDADE", sorted(unidade_options))

        grupo_options = df['GRUPO'].unique()
        selected_grupo = st.sidebar.selectbox("Selecione o GRUPO", sorted(grupo_options))

        tipo_atendimento_options = df['TIPO_ATENDIMENTO'].unique()
        selected_tipo_atendimento = st.sidebar.selectbox("Selecione o Tipo de Atendimento", sorted(tipo_atendimento_options))

        # Date range selection
        min_date = df['STATUS_ALAUDAR'].min()
        max_date = df['STATUS_ALAUDAR'].max()
        start_date, end_date = st.sidebar.date_input("Selecione o periodo", [min_date, max_date])

        # Filter dataframe based on selected UNIDADE, GRUPO, TIPO_ATENDIMENTO, and date range
        df_filtered = df_selected[(df_selected['UNIDADE'] == selected_unidade) &
                                  (df_selected['GRUPO'] == selected_grupo) &
                                  (df_selected['TIPO_ATENDIMENTO'] == selected_tipo_atendimento) &
                                  (df_selected['STATUS_ALAUDAR'] >= pd.Timestamp(start_date)) &
                                  (df_selected['STATUS_ALAUDAR'] <= pd.Timestamp(end_date))]

        # Allow user to edit the 'OBSERVACAO' field only using st.data_editor
        df_filtered_editable = st.data_editor(df_filtered, num_rows="dynamic", disabled=df_filtered.columns.difference(['OBSERVACAO']).tolist())

        # Save changes to the original dataframe
        df.update(df_filtered_editable[['SAME', 'OBSERVACAO']])

        # Display the filtered dataframe
        # st.dataframe(df_filtered)

        # Display total number of exams
        total_exams = len(df_filtered)
        st.write(f"Total number of exams: {total_exams}")

        # Generate SLA_STATUS pie chart
        sla_status_counts = df_filtered['SLA_STATUS'].value_counts()
        colors = ['lightcoral' if status == 'SLA FORA DO PERÍODO' else 'lightgreen' for status in sla_status_counts.index]
        fig, ax = plt.subplots()
        ax.pie(sla_status_counts, labels=sla_status_counts.index, autopct='%1.1f%%', colors=colors)
        ax.set_title(f'SLA Status - {selected_unidade} - {selected_grupo} - {selected_tipo_atendimento}')

        # Display the pie chart
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

if __name__ == "__main__":
    main()
