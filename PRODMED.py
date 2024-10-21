import streamlit as st
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import matplotlib.pyplot as plt
import streamlit.components.v1 as components

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
csv_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/multipliers.csv'
csv_df = pd.read_csv(csv_url)

# Initialize dataframes
excel_df = None
csv_df = pd.read_csv(csv_url)

if xlsx_file:
    # Load the files into dataframes
    excel_df = pd.read_excel(xlsx_file)
    

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

    # Apply filters to the dataframe for date and doctor
    filtered_df = excel_df[
        (excel_df[date_column] >= pd.to_datetime(start_date)) &
        (excel_df[date_column] <= pd.to_datetime(end_date)) &
        (excel_df['MEDICO_LAUDO_DEFINITIVO'] == selected_doctor)
    ]

    # Display full filtered dataframe for the selected doctor
    st.write('Full Filtered Dataframe for Selected Doctor:')
    filtered_columns = ['SAME', 'NOME_PACIENTE', 'TIPO_ATENDIMENTO', 'GRUPO', 'DESCRICAO_PROCEDIMENTO', 'ESPECIALIDADE', 'STATUS_APROVADO', 'MEDICO_LAUDO_DEFINITIVO', 'UNIDADE']
    st.dataframe(filtered_df[filtered_columns], width=1200, height=400)

    # Merge filtered data with CSV to calculate points
    csv_df['DESCRICAO_PROCEDIMENTO'] = csv_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    filtered_df['DESCRICAO_PROCEDIMENTO'] = filtered_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    merged_df = pd.merge(filtered_df, csv_df, on='DESCRICAO_PROCEDIMENTO', how='left')

    # Fill NaN values in MULTIPLIER with 0 for procedures not listed in the CSV
    merged_df['MULTIPLIER'] = pd.to_numeric(merged_df['MULTIPLIER'], errors='coerce').fillna(0)

    # Calculate points for each procedure
    merged_df['POINTS'] = merged_df['MULTIPLIER']

    # Group by UNIDADE, GRUPO, and DESCRICAO_PROCEDIMENTO to create dataframes for each doctor
    doctor_grouped = merged_df.groupby(['UNIDADE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO']).agg({'MULTIPLIER': 'first', 'STATUS_APROVADO': 'count'}).rename(columns={'STATUS_APROVADO': 'COUNT'}).reset_index()
    total_points_sum = 0

    # Loop through each hospital and modality for the selected doctor
    for hospital in doctor_grouped['UNIDADE'].unique():
        hospital_df = doctor_grouped[doctor_grouped['UNIDADE'] == hospital]
        st.markdown(f"<h2 style='color:yellow;'>{hospital}</h2>", unsafe_allow_html=True)
        for grupo in hospital_df['GRUPO'].unique():
            grupo_df = hospital_df[hospital_df['GRUPO'] == grupo]
            grupo_df['POINTS'] = grupo_df['COUNT'] * grupo_df['MULTIPLIER']
            total_points = grupo_df['POINTS'].sum()
            total_points_sum += total_points
            total_exams = grupo_df['COUNT'].sum()

            # Display the grouped dataframe, total points, and total number of exams for this modality
            st.markdown(f"<h3 style='color:#0a84ff;'>Modality: {grupo}</h3>", unsafe_allow_html=True)
            st.dataframe(grupo_df[['DESCRICAO_PROCEDIMENTO', 'COUNT', 'MULTIPLIER', 'POINTS']], width=1000, height=300)
            st.write(f'Total Points for {grupo}: {total_points}')
            st.write(f'Total Number of Exams for {grupo}: {total_exams}')

    # Display total points across all hospitals and modalities
    st.markdown(f"<h2 style='color:#10fa07;'>Total Points for All Modalities: {total_points_sum}</h2>", unsafe_allow_html=True)

    # Export all results to Excel file
    if st.button('Export Results to Excel'):
        try:
            with pd.ExcelWriter('Medical_Analysis_Results.xlsx', engine='openpyxl') as writer:
                # Write filtered data
                filtered_df.to_excel(writer, sheet_name='Filtered Data', index=False)
                
                # Write grouped data
                for hospital in doctor_grouped['UNIDADE'].unique():
                    hospital_df = doctor_grouped[doctor_grouped['UNIDADE'] == hospital]
                    for grupo in hospital_df['GRUPO'].unique():
                        grupo_df = hospital_df[hospital_df['GRUPO'] == grupo]
                        grupo_df.to_excel(writer, sheet_name=f'{hospital}_{grupo}', index=False)
                
                # Write summary sheet
                summary_df = pd.DataFrame({'Total Points for All Modalities': [total_points_sum]})
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            st.success('Results exported successfully! You can download the file from the link below:')
            with open('Medical_Analysis_Results.xlsx', 'rb') as file:
                btn = st.download_button(
                    label='Download Results',
                    data=file,
                    file_name='Medical_Analysis_Results.xlsx'
                )
        except Exception as e:
            st.error(f'An error occurred while exporting: {e}')
else:
    st.sidebar.write('Please upload an Excel file to continue.')













