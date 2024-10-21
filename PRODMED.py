import streamlit as st
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import matplotlib.pyplot as plt

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

    # Strip any leading/trailing whitespace from CSV column names
    csv_df.columns = csv_df.columns.str.strip()

    # Sidebar filters
    st.sidebar.header('Filter Options')

    # Date range filter
    date_column = 'STATUS_APROVADO'
    excel_df[date_column] = pd.to_datetime(excel_df[date_column], errors='coerce')
    min_date, max_date = excel_df[date_column].min(), excel_df[date_column].max()
    start_date, end_date = st.sidebar.date_input('Select Date Range', [min_date, max_date])

    # Unidade filter
    hospital_list = excel_df['UNIDADE'].unique()
    selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list)

    # Filter doctor names based on selected hospital
    doctor_list = excel_df[excel_df['UNIDADE'] == selected_hospital]['MEDICO_LAUDO_DEFINITIVO'].unique()
    selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list)

    # Apply filters to the dataframe
    filtered_df = excel_df[
        (excel_df[date_column] >= pd.to_datetime(start_date)) &
        (excel_df[date_column] <= pd.to_datetime(end_date)) &
        (excel_df['UNIDADE'] == selected_hospital) &
        (excel_df['MEDICO_LAUDO_DEFINITIVO'] == selected_doctor)
    ]

    # Merge filtered data with CSV to calculate points
    csv_df['DESCRICAO_PROCEDIMENTO'] = csv_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    filtered_df['DESCRICAO_PROCEDIMENTO'] = filtered_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    merged_df = pd.merge(filtered_df, csv_df, on='DESCRICAO_PROCEDIMENTO', how='left')

    # Fill NaN values in MULTIPLIER with 0 for procedures not listed in the CSV
    merged_df['MULTIPLIER'] = pd.to_numeric(merged_df['MULTIPLIER'], errors='coerce').fillna(0)

    # Group by UNIDADE, MEDICO_LAUDO_DEFINITIVO, and GRUPO to create dataframes for each doctor and modality
    doctors_grouped = merged_df.groupby(['UNIDADE', 'MEDICO_LAUDO_DEFINITIVO', 'GRUPO'])
    total_points_sum = 0

    # Loop through each group (hospital, doctor, modality) and display data
    for (hospital, doctor, grupo), group_df in doctors_grouped:
        if len(group_df) > 0:  # Only display if the doctor approved exams in that modality
            st.write(f"Hospital: {hospital} | Doctor: {doctor} | Modality: {grupo}")
            grouped_summary = group_df.groupby('DESCRICAO_PROCEDIMENTO').agg({'MULTIPLIER': 'first', 'STATUS_APROVADO': 'count'}).rename(columns={'STATUS_APROVADO': 'COUNT'}).reset_index()
            grouped_summary['POINTS'] = grouped_summary['COUNT'] * grouped_summary['MULTIPLIER']
            total_points = grouped_summary['POINTS'].sum()
            total_points_sum += total_points

            # Display the grouped dataframe and total points for this modality
            st.dataframe(grouped_summary[['DESCRICAO_PROCEDIMENTO', 'COUNT', 'MULTIPLIER', 'POINTS']])
            st.write(f'Total Points for {grupo}: {total_points}')

    # Display total points across all groups
    st.write(f'Total Points for All Modalities: {total_points_sum}')

else:
    st.sidebar.write('Please upload both an Excel and a CSV file to continue.')













