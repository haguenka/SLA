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

# Define periods with more explicit hour ranges
def assign_period(hour):
    if 0 <= hour < 6:
        return 'Madrugada'
    elif 6 <= hour < 12:
        return 'Manhã'
    elif 12 <= hour < 18:
        return 'Tarde'
    else:
        return 'Noite'

# Color mapping for periods
period_colors = {
    'Madrugada': '#555555',
    'Manhã': '#4682b4',
    'Tarde': '#f0ad4e',
    'Noite': '#c0392b'
}

# Day translations
day_translations = {
    'Monday': 'Segunda-feira', 
    'Tuesday': 'Terça-feira', 
    'Wednesday': 'Quarta-feira',
    'Thursday': 'Quinta-feira', 
    'Friday': 'Sexta-feira', 
    'Saturday': 'Sábado', 
    'Sunday': 'Domingo'
}

# Load and display logo from GitHub
logo_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
logo = load_image(logo_url)
st.sidebar.image(logo, use_column_width=True)

# Streamlit app
st.title('Medical Production Report')

# Load Excel and CSV files from GitHub
xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
csv_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/multipliers.csv'

excel_df = load_excel_data(xlsx_url)
csv_df = load_csv_data(csv_url)

# Strip any leading/trailing whitespace from CSV column names
csv_df.columns = csv_df.columns.str.strip()

# Sidebar filters
st.sidebar.header('Filter Options')

# Date range filter
date_column = 'STATUS_APROVADO'
try:
    # Convert 'STATUS_APROVADO' to datetime format
    excel_df[date_column] = pd.to_datetime(
        excel_df[date_column], 
        format='%d-%m-%Y %H:%M',
        errors='coerce'
    )
    excel_df = excel_df[excel_df[date_column].notna()]

    # Determine the minimum and maximum dates
    min_date, max_date = excel_df[date_column].min(), excel_df[date_column].max()

    # Sidebar date input
    start_date, end_date = st.sidebar.date_input(
        'Select Date Range',
        value=[min_date, max_date],
        min_value=min_date.date(),
        max_value=max_date.date()
    )
    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)

    # Filter based on date range
    filtered_df = excel_df[
        (excel_df[date_column] >= start_date) & (excel_df[date_column] <= end_date)
    ]

    # Unidade filter
    hospital_list = filtered_df['UNIDADE'].unique()
    selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list)

    # Filter doctor names based on selected hospital
    doctor_list = filtered_df[filtered_df['UNIDADE'] == selected_hospital]['MEDICO_LAUDO_DEFINITIVO'].unique()
    selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list)
    st.markdown(f"<h3 style='color:red;'>{selected_doctor}</h3>", unsafe_allow_html=True)

    # Apply filters to the dataframe for selected doctor
    filtered_df = filtered_df[filtered_df['MEDICO_LAUDO_DEFINITIVO'] == selected_doctor]

    # Format 'STATUS_APROVADO' for display
    filtered_df[date_column] = filtered_df[date_column].dt.strftime('%d-%m-%Y %H:%M')

    # Display filtered data
    filtered_columns = [
        'SAME', 'NOME_PACIENTE', 'TIPO_ATENDIMENTO', 'GRUPO', 
        'DESCRICAO_PROCEDIMENTO', 'ESPECIALIDADE', 'STATUS_APROVADO', 
        'MEDICO_LAUDO_DEFINITIVO', 'UNIDADE'
    ]
    st.dataframe(filtered_df[filtered_columns], width=1200, height=400)

    # Merge filtered data with CSV to calculate points
    csv_df['DESCRICAO_PROCEDIMENTO'] = csv_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    filtered_df['DESCRICAO_PROCEDIMENTO'] = filtered_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    merged_df = pd.merge(filtered_df, csv_df, on='DESCRICAO_PROCEDIMENTO', how='left')
    merged_df['MULTIPLIER'] = pd.to_numeric(merged_df['MULTIPLIER'], errors='coerce').fillna(0)
    merged_df['POINTS'] = (merged_df['STATUS_APROVADO'].notna().astype(int) * merged_df['MULTIPLIER']).round(1)

    # Group by UNIDADE, GRUPO, and DESCRICAO_PROCEDIMENTO
    doctor_grouped = merged_df.groupby(['UNIDADE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO']).agg({
        'MULTIPLIER': 'first', 
        'STATUS_APROVADO': 'count'
    }).rename(columns={'STATUS_APROVADO': 'COUNT'}).reset_index()

    # Display results for each group
    total_points_sum = 0
    for hospital in doctor_grouped['UNIDADE'].unique():
        hospital_df = doctor_grouped[doctor_grouped['UNIDADE'] == hospital]
        st.markdown(f"<h2 style='color:yellow;'>{hospital}</h2>", unsafe_allow_html=True)
        for grupo in hospital_df['GRUPO'].unique():
            grupo_df = hospital_df[hospital_df['GRUPO'] == grupo]
            grupo_df['POINTS'] = grupo_df['COUNT'] * grupo_df['MULTIPLIER']
            total_points = round(grupo_df['POINTS'].sum(), 1)
            total_points_sum += total_points
            total_exams = grupo_df['COUNT'].sum()
            st.markdown(f"<h3 style='color:#0a84ff;'>Modality: {grupo}</h3>", unsafe_allow_html=True)
            st.dataframe(grupo_df[['DESCRICAO_PROCEDIMENTO', 'COUNT', 'MULTIPLIER', 'POINTS']], width=1000, height=300)
            st.write(f'Total Points for {grupo}: {total_points:.1f}')
            st.write(f'Total Number of Exams for {grupo}: {total_exams}')

    st.markdown(f"<h2 style='color:#10fa07;'>Total Points for All Modalities: {total_points_sum:.1f}</h2>", unsafe_allow_html=True)

    # Event timeline
    try:
        days_df = filtered_df.copy()
        days_df['STATUS_APROVADO'] = pd.to_datetime(days_df['STATUS_APROVADO'], format='%d-%m-%Y %H:%M')
        days_df['DAY_OF_WEEK'] = days_df['STATUS_APROVADO'].dt.day_name().map(day_translations)
        days_df['DATE'] = days_df['STATUS_APROVADO'].dt.date.astype(str)
        days_df['PERIOD'] = days_df['STATUS_APROVADO'].dt.hour.apply(assign_period)

        days_grouped = days_df.groupby(['MEDICO_LAUDO_DEFINITIVO', 'DATE', 'DAY_OF_WEEK', 'PERIOD'], dropna=False).size().reset_index(name='EVENT_COUNT')

        # Styling for the DataFrame
        def color_rows(row):
            return [
                f'background-color: {period_colors.get(row["PERIOD"], "white")}; color: white'
                for _ in row.index
            ]

        styled_df = days_grouped.style.apply(color_rows, axis=1)
        st.dataframe(styled_df, width=1200, height=400)

        # Plot events per hour
        for day in days_df['DATE'].unique():
            st.write(f'Events Timeline for {day}:')
            day_df = days_df[days_df['DATE'] == day]
            if not day_df.empty:
                fig, ax = plt.subplots(figsize=(10, 6))
                day_df['HOUR'] = day_df['STATUS_APROVADO'].dt.hour
                hourly_events = day_df.groupby('HOUR').size().reset_index(name='EVENT_COUNT')
                ax.plot(hourly_events['HOUR'], hourly_events['EVENT_COUNT'], marker='o', linestyle='-', label=str(day))
                ax.set_xlabel('Hour of the Day')
                ax.set_ylabel('Events Count')
                ax.set_title(f'Events Timeline for {day}')
                plt.xticks(range(0, 24))
                st.pyplot(fig)

    except Exception as e:
        st.error(f"Error processing event timeline: {e}")

except Exception as e:
    st.error(f"An error occurred while processing the data: {e}")



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
