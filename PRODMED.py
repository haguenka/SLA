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
st.title('Report de Produção Médica')

# Load Excel and CSV files from GitHub
xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/basesla5.xlsx'
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

# Ensure start_date and end_date are within the valid range
if start_date < min_date:
    start_date = min_date
if end_date > max_date:
    end_date = max_date

# Unidade filter
hospital_list = excel_df['UNIDADE'].unique()
selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list)

# Filter doctor names based on selected hospital
doctor_list = excel_df[excel_df['UNIDADE'] == selected_hospital]['MEDICO_LAUDO_DEFINITIVO'].unique()
selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list)
st.markdown(f"<h3 style='color:red;'>{selected_doctor}</h3>", unsafe_allow_html=True)

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
st.markdown(f"<h2 style='color:#10fa07;'>Total Points for All Modalities: {total_points_sum:.1f}</h2>", unsafe_allow_html=True)

# Get the days and periods each doctor has events
days_df = filtered_df[['MEDICO_LAUDO_DEFINITIVO', 'STATUS_APROVADO']].dropna()
days_df['DAY_OF_WEEK'] = days_df['STATUS_APROVADO'].dt.strftime('%A').replace({'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 'Wednesday': 'Quarta-feira', 'Thursday': 'Quinta-feira', 'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'})
days_df['DATE'] = days_df['STATUS_APROVADO'].dt.strftime('%Y-%m-%d')

# Define time periods
days_df['PERIOD'] = pd.cut(days_df['STATUS_APROVADO'].dt.hour, bins=[-1, 7, 13, 19, 24], labels=['Madrugada', 'Manhã', 'Tarde', 'Noite'], ordered=False)

days_grouped = days_df.groupby(['MEDICO_LAUDO_DEFINITIVO', 'DATE', 'DAY_OF_WEEK', 'PERIOD']).size().reset_index(name='EVENT_COUNT')
days_grouped = days_grouped[days_grouped['EVENT_COUNT'] > 0]  # Only show days with events

st.write('Dias com eventos de Laudo:')
st.dataframe(days_grouped.style.apply(lambda x: ['background-color: #555555; color: #ffffff' if x['PERIOD'] == 'Madrugada' else 'background-color: #4682b4; color: #ffffff' if x['PERIOD'] == 'Manhã' else 'background-color: #f0ad4e; color: #ffffff' if x['PERIOD'] == 'Tarde' else 'background-color: #c0392b; color: #ffffff' for _ in x], axis=1), width=1200, height=400)
days_df = filtered_df[['MEDICO_LAUDO_DEFINITIVO', 'STATUS_APROVADO']].dropna()
days_df['DAY_OF_WEEK'] = days_df['STATUS_APROVADO'].dt.strftime('%A').replace({'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 'Wednesday': 'Quarta-feira', 'Thursday': 'Quinta-feira', 'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'})
days_df['DATE'] = days_df['STATUS_APROVADO'].dt.strftime('%Y-%m-%d')

# Define time periods
days_df['PERIOD'] = pd.cut(days_df['STATUS_APROVADO'].dt.hour, bins=[-1, 7, 13, 19, 24], labels=['Madrugada', 'Manhã', 'Tarde', 'Noite'], ordered=False)

# Define medical shifts
def medical_shift(hour):
    if 7 <= hour < 19:
        return 'Day Shift'
    else:
        return 'Night Shift'

days_df['SHIFT'] = days_df['STATUS_APROVADO'].dt.hour.apply(medical_shift)

days_grouped = days_df.groupby(['MEDICO_LAUDO_DEFINITIVO', 'DATE', 'DAY_OF_WEEK', 'PERIOD']).size().reset_index(name='EVENT_COUNT')
days_grouped = days_grouped[days_grouped['EVENT_COUNT'] > 0]  # Only show days with events

# Plot events per hour for each day
for day in days_df['DATE'].unique():
    st.write(f'Events Timeline for {day}:')
    day_df = days_df[days_df['DATE'] == day]
    if not day_df.empty:
        fig, ax = plt.subplots(figsize=(10, 6))

        # Extract hour from STATUS_APROVADO for plotting
        day_df['HOUR'] = day_df['STATUS_APROVADO'].dt.hour

        # Group by hour to get event counts
        hourly_events = day_df.groupby('HOUR').size().reset_index(name='EVENT_COUNT')

        # Plot events per hour for each day
        plt.style.use('dark_background')

        # Plot event counts against hours
        ax.plot(hourly_events['HOUR'], hourly_events['EVENT_COUNT'], marker='o', linestyle='-', color='#1f77b4', label=str(day))
        ax.set_facecolor('#2e2e2e')
        ax.set_xlabel('Hour of the Day', color='white')
        ax.set_ylabel('Events Count', color='white')
        ax.set_title(f'Events Timeline for {day}', color='white')
        ax.tick_params(colors='white')
        ax.legend(title='Date', facecolor='#3a3a3a', edgecolor='white')
        ax.grid(True, which='both', linestyle='--', linewidth=0.5, color='gray')
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
        
        # Add days each doctor has events in table format
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Days Each Doctor Has Events', ln=True, align='C')
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(50, 10, 'Doctor', 1, 0, 'C')
        pdf.cell(30, 10, 'Date', 1, 0, 'C')
        pdf.cell(30, 10, 'Day of Week', 1, 0, 'C')
        pdf.cell(30, 10, 'Period', 1, 0, 'C')
        pdf.cell(30, 10, 'Event Count', 1, 1, 'C')
        pdf.set_font('Arial', '', 10)
        for _, row in days_grouped.iterrows():
            pdf.cell(50, 10, row['MEDICO_LAUDO_DEFINITIVO'], 1, 0, 'L')
            pdf.cell(30, 10, row['DATE'], 1, 0, 'C')
            pdf.cell(30, 10, row['DAY_OF_WEEK'], 1, 0, 'C')
            pdf.cell(30, 10, row['PERIOD'], 1, 0, 'C')
            pdf.cell(30, 10, str(row['EVENT_COUNT']), 1, 1, 'C')
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
