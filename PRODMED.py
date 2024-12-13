import streamlit as st
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import matplotlib.pyplot as plt
from datetime import datetime

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

# Define periods with explicit hour ranges
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

# Mapping of abbreviations to full hospital names
hospital_name_mapping = {
    "HSC": "Hospital Santa Catarina",
    "CSSJ": "Casa de Saúde São José",
    "HNSC": "Hospital Nossa Senhora da Conceição"
}

# Function to replace hospital names
def merge_hospital_names(df, column_name):
    return df.replace({column_name: hospital_name_mapping})

# Load and display logo
logo_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
logo = load_image(logo_url)
st.sidebar.image(logo, use_container_width=True)

# Streamlit app
st.title('Medical Production Report')

# Load Excel and CSV files
xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
csv_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/multipliers.csv'

excel_df = load_excel_data(xlsx_url)
csv_df = load_csv_data(csv_url)

# Strip whitespace from CSV column names
csv_df.columns = csv_df.columns.str.strip()

# Replace abbreviations in 'UNIDADE' with full hospital names
excel_df = merge_hospital_names(excel_df, "UNIDADE")

# Sidebar filters
st.sidebar.header('Filter Options')

try:
    # Convert 'STATUS_APROVADO' and 'STATUS_PRELIMINAR' to datetime
    excel_df['STATUS_APROVADO'] = pd.to_datetime(excel_df['STATUS_APROVADO'], format='%d-%m-%Y %H:%M', errors='coerce')
    excel_df['STATUS_PRELIMINAR'] = pd.to_datetime(excel_df['STATUS_PRELIMINAR'], format='%d-%m-%Y %H:%M', errors='coerce')

    # Calculate min and max date from 'STATUS_APROVADO' column
    min_date = excel_df['STATUS_APROVADO'].min()
    max_date = excel_df['STATUS_APROVADO'].max()

    # Sidebar date input
    start_date, end_date = st.sidebar.date_input(
        'Select Date Range',
        value=[min_date.date(), max_date.date()],
        min_value=min_date.date(),
        max_value=max_date.date()
    )

    # Convert start_date and end_date to datetime64[ns] for comparison
    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)

    # Filter data based on date range
    filtered_df = excel_df[
        (excel_df['STATUS_APROVADO'] >= start_date) & (excel_df['STATUS_APROVADO'] <= end_date)
    ]

    # Hospital selection
    hospital_list = filtered_df['UNIDADE'].unique()
    selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list, key='hospital_selectbox')
    filtered_df = filtered_df[filtered_df['UNIDADE'] == selected_hospital]

    # Doctor selection from final laudos
    doctor_list = filtered_df['MEDICO_LAUDO_DEFINITIVO'].unique()
    selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list, key='doctor_selectbox')

    # Show the selected doctor's name on top in red and big letters
    st.markdown(f"<h1 style='color:red;'>{selected_doctor}</h1>", unsafe_allow_html=True)

    # Filter dataframes by selected doctor
    preliminar_df = filtered_df[
        (filtered_df['STATUS_PRELIMINAR'].notna()) &
        (filtered_df['MEDICO_LAUDOO_PRELIMINAR'] == selected_doctor)
    ]
    aprovado_df = filtered_df[
        (filtered_df['STATUS_APROVADO'].notna()) &
        (filtered_df['MEDICO_LAUDO_DEFINITIVO'] == selected_doctor)
    ]

    # Display total event counts for the selected doctor
    total_preliminar_events = len(preliminar_df)
    total_aprovado_events = len(aprovado_df)
    st.markdown(f"<h3 style='color:#f0ad4e;'>Total Events for LAUDO PRELIMINAR: {total_preliminar_events}</h3>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='color:#4682b4;'>Total Events for LAUDO APROVADO: {total_aprovado_events}</h3>", unsafe_allow_html=True)

    # Display filtered data for selected doctor (both preliminar and aprovado)
    doctor_all_events = pd.concat([preliminar_df, aprovado_df], ignore_index=True)
    filtered_columns = [
        'SAME', 'NOME_PACIENTE', 'TIPO_ATENDIMENTO', 'GRUPO', 'DESCRICAO_PROCEDIMENTO',
        'ESPECIALIDADE', 'STATUS_PRELIMINAR', 'MEDICO_LAUDOO_PRELIMINAR',
        'STATUS_APROVADO', 'MEDICO_LAUDO_DEFINITIVO', 'UNIDADE'
    ]
    st.dataframe(doctor_all_events[filtered_columns], width=1200, height=400)

    # Merge with CSV for points calculation - only for aprovado events of selected doctor
    csv_df['DESCRICAO_PROCEDIMENTO'] = csv_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    aprovado_df['DESCRICAO_PROCEDIMENTO'] = aprovado_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    merged_df = pd.merge(aprovado_df, csv_df, on='DESCRICAO_PROCEDIMENTO', how='left')
    merged_df['MULTIPLIER'] = pd.to_numeric(merged_df['MULTIPLIER'], errors='coerce').fillna(0)
    merged_df['POINTS'] = (merged_df['STATUS_APROVADO'].notna().astype(int) * merged_df['MULTIPLIER']).round(1)

    # Group by UNIDADE, GRUPO, DESCRICAO_PROCEDIMENTO for the selected doctor
    doctor_grouped = merged_df.groupby(['UNIDADE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO']).agg({
        'MULTIPLIER': 'first',
        'STATUS_APROVADO': 'count'
    }).rename(columns={'STATUS_APROVADO': 'COUNT'}).reset_index()

    # Display grouped results
    total_points_sum = 0
    total_count_sum = 0  # total count for all modalities

    for hospital in doctor_grouped['UNIDADE'].unique():
        hospital_df = doctor_grouped[doctor_grouped['UNIDADE'] == hospital]
        st.markdown(f"<h2 style='color:yellow;'>{hospital}</h2>", unsafe_allow_html=True)
        for grupo in hospital_df['GRUPO'].unique():
            grupo_df = hospital_df[hospital_df['GRUPO'] == grupo].copy()
            grupo_df['POINTS'] = grupo_df['COUNT'] * grupo_df['MULTIPLIER']
            total_points = grupo_df['POINTS'].sum()
            total_count = grupo_df['COUNT'].sum()
            total_points_sum += total_points
            total_count_sum += total_count
            st.dataframe(grupo_df[['DESCRICAO_PROCEDIMENTO', 'COUNT', 'MULTIPLIER', 'POINTS']])
            st.write(f"**Total Points for {grupo}: {total_points:.1f}**")
            st.write(f"**Total Count for {grupo}: {total_count}**")

    st.markdown(f"### Total Points for All Modalities: {total_points_sum:.1f}")
    st.markdown(f"### Total Count for All Modalities: {total_count_sum}")

    # ---------------------------------------------
    # ADDING THE REQUESTED FUNCTION BLOCK HERE
    # ---------------------------------------------
    # We now want to show LAUDO APROVADO and LAUDO PRELIMINAR counts for each period
    # We'll compute a merged DataFrame that contains both PRELIMINAR_COUNT and APROVADO_COUNT.

    # Filter preliminar_df and aprovado_df for only the "TOMOGRAFIA" and "RESSONANCIA" modalities
    valid_groups = ['GRUPO TOMOGRAFIA', 'GRUPO RESSONÄNCIA MAGNÉTICA']
    
    preliminar_filtered = preliminar_df[preliminar_df['GRUPO'].isin(valid_groups)]
    aprovado_filtered = aprovado_df[aprovado_df['GRUPO'].isin(valid_groups)]
    
    # For preliminar_df
    if not preliminar_filtered.empty:
        preliminar_filtered['DAY_OF_WEEK'] = preliminar_filtered['STATUS_PRELIMINAR'].dt.day_name().map(day_translations)
        preliminar_filtered['DATE'] = preliminar_filtered['STATUS_PRELIMINAR'].dt.date.astype(str)
        preliminar_filtered['PERIOD'] = preliminar_filtered['STATUS_PRELIMINAR'].dt.hour.apply(assign_period)
        preliminar_days_grouped = preliminar_filtered.groupby(
            ['MEDICO_LAUDOO_PRELIMINAR', 'DATE', 'DAY_OF_WEEK', 'PERIOD'],
            dropna=False
        ).size().reset_index(name='PRELIMINAR_COUNT')
        preliminar_days_grouped = preliminar_days_grouped.rename(columns={'MEDICO_LAUDOO_PRELIMINAR': 'MEDICO'})
    else:
        preliminar_days_grouped = pd.DataFrame(columns=['MEDICO', 'DATE', 'DAY_OF_WEEK', 'PERIOD', 'PRELIMINAR_COUNT'])
    
    # For aprovado_df
    if not aprovado_filtered.empty:
        aprovado_filtered['DAY_OF_WEEK'] = aprovado_filtered['STATUS_APROVADO'].dt.day_name().map(day_translations)
        aprovado_filtered['DATE'] = aprovado_filtered['STATUS_APROVADO'].dt.date.astype(str)
        aprovado_filtered['PERIOD'] = aprovado_filtered['STATUS_APROVADO'].dt.hour.apply(assign_period)
        aprovado_days_grouped = aprovado_filtered.groupby(
            ['MEDICO_LAUDO_DEFINITIVO', 'DATE', 'DAY_OF_WEEK', 'PERIOD'],
            dropna=False
        ).size().reset_index(name='APROVADO_COUNT')
        aprovado_days_grouped = aprovado_days_grouped.rename(columns={'MEDICO_LAUDO_DEFINITIVO': 'MEDICO'})
    else:
        aprovado_days_grouped = pd.DataFrame(columns=['MEDICO', 'DATE', 'DAY_OF_WEEK', 'PERIOD', 'APROVADO_COUNT'])
    
    # Merge both
    days_merged = pd.merge(preliminar_days_grouped, aprovado_days_grouped,
                           on=['MEDICO', 'DATE', 'DAY_OF_WEEK', 'PERIOD'], how='outer')
    days_merged = days_merged.fillna(0)
    
    # Convert to integers to avoid decimals
    days_merged['PRELIMINAR_COUNT'] = days_merged['PRELIMINAR_COUNT'].astype(int)
    days_merged['APROVADO_COUNT'] = days_merged['APROVADO_COUNT'].astype(int)
    
    # Styling for the DataFrame
    def color_rows(row):
        return [
            f'background-color: {period_colors.get(row["PERIOD"], "white")}; color: white'
            for _ in row.index
        ]
    
    styled_df = days_merged.style.apply(color_rows, axis=1)
    
    st.markdown("### LAUDO PRELIMINAR and LAUDO APROVADO Counts by Period (Tomografia and Ressonancia)")
    st.dataframe(styled_df, width=1200, height=400)


except Exception as e:
    st.error(f"An error occurred: {e}")



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
