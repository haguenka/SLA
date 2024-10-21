import streamlit as st
import pandas as pd
from PIL import Image
import requests
from io import BytesIO

# Load and display logo from GitHub
url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
response = requests.get(url)
logo = Image.open(BytesIO(response.content))
st.sidebar.image(logo, use_column_width=True)

# Streamlit app
st.title('Medical Analysis Dashboard')

# Upload Excel and CSV files
st.sidebar.header('Upload Files')
xlsx_file = st.sidebar.file_uploader('Upload Excel File', type=['xlsx'])
csv_file = st.sidebar.file_uploader('Upload CSV File', type=['csv'])

# Initialize dataframes
excel_df = None
csv_df = None

if xlsx_file and csv_file:
    # Load the files into dataframes
    excel_df = pd.read_excel(xlsx_file)
    csv_df = pd.read_csv(csv_file)

    # Sidebar filters
    st.sidebar.header('Filter Options')

    # Date range filter
    date_column = 'DATA_LAUDO'
    excel_df[date_column] = pd.to_datetime(excel_df[date_column], errors='coerce')
    min_date, max_date = excel_df[date_column].min(), excel_df[date_column].max()
    start_date, end_date = st.sidebar.date_input('Select Date Range', [min_date, max_date])

    # Unidade filter
    hospital_list = excel_df['UNIDADE'].unique()
    selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list)

    # Grupo filter
    grupo_list = excel_df['GRUPO'].unique()
    selected_grupo = st.sidebar.selectbox('Select Exam Modality', grupo_list)

    # Medico_Laudo_Definitivo filter
    doctor_list = excel_df['MEDICO_LAUDO_DEFINITIVO'].unique()
    selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list)

    # Apply filters to the dataframe
    filtered_df = excel_df[
        (excel_df[date_column] >= pd.to_datetime(start_date)) &
        (excel_df[date_column] <= pd.to_datetime(end_date)) &
        (excel_df['UNIDADE'] == selected_hospital) &
        (excel_df['GRUPO'] == selected_grupo) &
        (excel_df['MEDICO_LAUDO_DEFINITIVO'] == selected_doctor)
    ]

    # Merge filtered data with CSV to calculate points
    csv_df['DESCRICAO_PROCEDIMENTO'] = csv_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    filtered_df['DESCRICAO_PROCEDIMENTO'] = filtered_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    merged_df = pd.merge(filtered_df, csv_df, on='DESCRICAO_PROCEDIMENTO', how='inner')

    # Calculate points as count * multiplier
    if 'MULTIPLIER' in merged_df.columns:
        merged_df['MULTIPLIER'] = pd.to_numeric(merged_df['MULTIPLIER'], errors='coerce')
        procedure_counts = merged_df['DESCRICAO_PROCEDIMENTO'].value_counts().reset_index()
        procedure_counts.columns = ['DESCRICAO_PROCEDIMENTO', 'COUNT']
        merged_df = pd.merge(procedure_counts, csv_df, on='DESCRICAO_PROCEDIMENTO', how='inner')
        merged_df['POINTS'] = merged_df['COUNT'] * merged_df['MULTIPLIER']

        # Display filtered dataframe and count of exams
        st.write('Filtered Dataframe:')
        st.dataframe(merged_df[['DESCRICAO_PROCEDIMENTO', 'COUNT', 'MULTIPLIER', 'POINTS']])
        st.write(f'Total Number of Exams: {len(filtered_df)}')
        st.write(f'Total Points: {merged_df["POINTS"].sum()}')
    else:
        st.write('The CSV file must contain a "MULTIPLIER" column.')
else:
    st.sidebar.write('Please upload both an Excel and a CSV file to continue.')










