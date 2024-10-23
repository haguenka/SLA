import streamlit as st
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import matplotlib.pyplot as plt
import datetime
from fpdf import FPDF

# Caching for performance improvement
@st.cache_data
def load_image(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

@st.cache_data
def load_excel_data(xlsx_url):
    response = requests.get(xlsx_url)
    return pd.read_excel(BytesIO(response.content))

@st.cache_data
def load_csv_data(csv_url):
    response = requests.get(csv_url)
    return pd.read_csv(BytesIO(response.content))

# Load and display logo from GitHub
logo_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
logo = load_image(logo_url)
st.sidebar.image(logo, use_column_width=True)

# Streamlit app
st.title('Medical Analysis Dashboard')

# Load Excel and CSV files from GitHub
xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/VSET.xlsx'
csv_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/multipliers.csv'

excel_df = load_excel_data(xlsx_url)
csv_df = load_csv_data(csv_url)

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
merged_df['POINTS'] = merged_df['STATUS_APROVADO'].notna().astype(int) * merged_df['MULTIPLIER']

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

# Get the days and periods each doctor has events
st.write('Days Each Doctor Has Events:')
days_df = filtered_df[['MEDICO_LAUDO_DEFINITIVO', 'STATUS_APROVADO']].dropna()
days_df['DAY_OF_WEEK'] = days_df['STATUS_APROVADO'].dt.day_name()
days_df['DATE'] = days_df['STATUS_APROVADO'].dt.date

days_grouped = days_df.groupby(['MEDICO_LAUDO_DEFINITIVO', 'DATE', 'DAY_OF_WEEK', 'STATUS_APROVADO']).size().reset_index(name='EVENT_COUNT')
days_grouped = days_grouped[days_grouped['EVENT_COUNT'] > 0]  # Only show days with events
st.dataframe(days_grouped, width=800, height=400)

# Plot events per hour for each day
for day in days_grouped['DATE'].unique():
    st.write(f'Events Timeline for {day}:')
    day_df = days_grouped[days_grouped['DATE'] == day]
    if not day_df.empty:
        fig, ax = plt.subplots(figsize=(10, 6))

        # Extract hour from STATUS_APROVADO for plotting
        day_df['HOUR'] = day_df['STATUS_APROVADO'].dt.hour

        # Group by hour to get event counts
        hourly_events = day_df.groupby('HOUR')['EVENT_COUNT'].sum().reset_index()

        # Plot event counts against hours
        ax.plot(hourly_events['HOUR'], hourly_events['EVENT_COUNT'], marker='o', linestyle='-', label=str(day))
        ax.set_xlabel('Hour of the Day')
        ax.set_ylabel('Events Count')
        ax.set_title(f'Events Timeline for {day}')
        ax.legend(title='Date')
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.xticks(range(0, 24))
        st.pyplot(fig)

# Export summary and doctors' dataframes as a combined PDF report
if st.button('Export Summary and Doctors Dataframes as PDF'):
    try:
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(left=5, top=5, right=5)

        # Create title sheet
        pdf.add_page()
        pdf.image(logo_url, x=80, y=30, w=120)
        pdf.set_font('Arial', 'B', 24)
        pdf.ln(100)
        pdf.cell(0, 10, 'Relatório de produção', ln=True, align='C')
        pdf.ln(10)
        pdf.set_font('Arial', '', 18)
        pdf.cell(0, 10, f'Mês de {start_date.strftime("%B de %Y").capitalize()}', ln=True, align='C')
        pdf.ln(20)
        # Add doctors name in uppercase, big and blue
        pdf.set_font('Arial', 'B', 24)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 10, selected_doctor.upper(), ln=True, align='C')
        pdf.set_text_color(0, 0, 0)
        pdf.ln(20)
        
        # Add summary sheet
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Medical Analysis Summary Report', ln=True, align='C')
        pdf.ln(10)
        pdf.set_font('Arial', '', 16)
        pdf.cell(0, 10, f'Total Points for All Modalities: {total_points_sum}', ln=True)
        pdf.ln(10)
        
        # Add hospital and modality dataframes to subsequent pages in table format
        for hospital in doctor_grouped['UNIDADE'].unique():
            pdf.add_page()
            pdf.set_font('Arial', 'B', 24)
            pdf.set_text_color(0, 0, 255)
            pdf.cell(0, 10, f'Hospital: {hospital}', ln=True, align='C')
            pdf.set_text_color(0, 0, 0)
            pdf.ln(10)
            hospital_df = doctor_grouped[doctor_grouped['UNIDADE'] == hospital]
            for grupo in hospital_df['GRUPO'].unique():
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f'Modality: {grupo}', ln=True)
                pdf.ln(10)
                grupo_df = hospital_df[hospital_df['GRUPO'] == grupo]
                grupo_df['POINTS'] = grupo_df['COUNT'] * grupo_df['MULTIPLIER']

                # Create table header
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(80, 10, 'Procedure', 1, 0, 'C')
                pdf.cell(30, 10, 'Count', 1, 0, 'C')
                pdf.cell(30, 10, 'Multiplier', 1, 0, 'C')
                pdf.cell(30, 10, 'Points', 1, 1, 'C')

                # Add rows to the table
                pdf.set_font('Arial', '', 10)
                for _, row in grupo_df.iterrows():
                    pdf.cell(80, 10, row['DESCRICAO_PROCEDIMENTO'][:30] + '...' if len(row['DESCRICAO_PROCEDIMENTO']) > 30 else row['DESCRICAO_PROCEDIMENTO'], 1, 0, 'L')
                    pdf.cell(30, 10, str(row['COUNT']), 1, 0, 'C')
                    pdf.cell(30, 10, f"{row['MULTIPLIER']:.1f}", 1, 0, 'C')
                    pdf.cell(30, 10, f"{row['POINTS']:.1f}", 1, 1, 'C')
                    if pdf.get_y() > 190:  # Add a new page if the current page is about to overflow
                        pdf.add_page()
                        pdf.set_font('Arial', 'B', 10)
                        pdf.cell(80, 10, 'Procedure', 1, 0, 'C')
                        pdf.cell(30, 10, 'Count', 1, 0, 'C')
                        pdf.cell(30, 10, 'Multiplier', 1, 0, 'C')
                        pdf.cell(30, 10, 'Points', 1, 1, 'C')
                
                # Summary for the modality
                total_points = grupo_df['POINTS'].sum()
                total_exams = grupo_df['COUNT'].sum()
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(0, 10, f'Total Points for {grupo}: {total_points}', ln=True)
                pdf.cell(0, 10, f'Total Number of Exams for {grupo}: {total_exams}', ln=True)
                pdf.ln(10)
        
        pdf_file_path = 'Medical_Analysis_Combined_Report.pdf'
        pdf.output(pdf_file_path)
        st.success('Combined report exported successfully! You can download the file from the link below:')
        with open(pdf_file_path, 'rb') as file:
            btn = st.download_button(
                label='Download Combined PDF',
                data=file,
                file_name='Medical_Analysis_Combined_Report.pdf'
            )
    except Exception as e:
        st.error(f'An error occurred while exporting the PDF: {e}')
