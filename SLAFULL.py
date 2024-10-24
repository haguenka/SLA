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
def load_excel():
    url = 'https://raw.githubusercontent.com/haguenka/SLA/main/base.xlsx'
    response = requests.get(url)
    return pd.read_excel(BytesIO(response.content))

def is_weekend(date):
    return date.weekday() >= 5

def main():
    st.title("Análise de SLA Dashboard")

    # Load and display logo from GitHub
    url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
    logo = load_logo(url)
    st.sidebar.image(logo, use_column_width=True)

    # Load the Excel file
    df = load_excel()

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
    conditions = [
        (df['GRUPO'] == 'GRUPO RAIO-X') & (df['DELTA_TIME'] > 72),
        (df['GRUPO'].isin(['GRUPO MAMOGRAFIA', 'GRUPO MEDICINA NUCLEAR'])) & (df['DELTA_TIME'] > (5 * 24)),
        (df['TIPO_ATENDIMENTO'] == 'Pronto Atendimento') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 1),
        (df['TIPO_ATENDIMENTO'] == 'Internado') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 24),
        (df['TIPO_ATENDIMENTO'] == 'Externo') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 96)
    ]

    # Set the default SLA status and apply conditions
    df['SLA_STATUS'] = 'SLA DENTRO DO PERÍODO'
    for condition in conditions:
        df.loc[condition, 'SLA_STATUS'] = 'SLA FORA DO PERÍODO'

    # Select only relevant columns
    selected_columns = [
        'SAME', 'NOME_PACIENTE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO', 'MEDICO_LAUDO_DEFINITIVO',
        'UNIDADE', 'TIPO_ATENDIMENTO', 'STATUS_ALAUDAR', 'STATUS_PRELIMINAR', 'STATUS_APROVADO', 'DELTA_TIME', 'SLA_STATUS'
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

    # Display the filtered dataframe
    st.dataframe(df_filtered)

    # Display total number of exams
    total_exams = len(df_filtered)
    st.write(f"Total number of exams: {total_exams}")

    # Generate SLA_STATUS pie chart
    sla_status_counts = df_filtered['SLA_STATUS'].value_counts()
    colors = ['lightcoral' if status == 'SLA FORA DO PERÍODO' else 'lightgreen' for status in sla_status_counts.index]
    fig, ax = plt.subplots()
    logo_resized = logo.resize((400, 200))
    fig.figimage(logo_resized, 30, fig.bbox.ymax - 450, zorder=1, alpha=0.8)
    ax.pie(sla_status_counts, labels=sla_status_counts.index, autopct='%1.1f%%', colors=colors)
    ax.set_title(f'SLA Status - {selected_unidade} - {selected_grupo} - {selected_tipo_atendimento}')

    # Display the pie chart
    st.pyplot(fig)

if __name__ == "__main__":
    main()
