import streamlit as st
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
import datetime

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

# Assign time periods
def assign_period(hour):
    if 0 <= hour < 6:
        return 'Madrugada'
    elif 6 <= hour < 12:
        return 'Manhã'
    elif 12 <= hour < 18:
        return 'Tarde'
    else:
        return 'Noite'

# Load and display logo
logo_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
logo = load_image(logo_url)
st.sidebar.image(logo, use_column_width=True)

# App title
st.title('Medical Production Report')

# Load data
xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
csv_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/multipliers.csv'

excel_df = load_excel_data(xlsx_url)
csv_df = load_csv_data(csv_url)

# Clean CSV column names
csv_df.columns = csv_df.columns.str.strip()

# Date filter function
def filter_by_date_and_status(df, date_column, start_date, end_date):
    df[date_column] = pd.to_datetime(df[date_column], format='%d-%m-%Y %H:%M', errors='coerce')
    df = df[df[date_column].notna()]
    return df[(df[date_column] >= start_date) & (df[date_column] <= end_date)]

# Sidebar filters
st.sidebar.header('Filter Options')

try:
    # Define columns
    date_column_aprovado = 'STATUS_APROVADO'
    date_column_preliminar = 'STATUS_PRELIMINAR'

    # Convert dates
    excel_df[date_column_aprovado] = pd.to_datetime(excel_df[date_column_aprovado], format='%d-%m-%Y %H:%M', errors='coerce')
    excel_df[date_column_preliminar] = pd.to_datetime(excel_df[date_column_preliminar], format='%d-%m-%Y %H:%M', errors='coerce')

    # Date range
    min_date = min(excel_df[date_column_aprovado].min(), excel_df[date_column_preliminar].min())
    max_date = max(excel_df[date_column_aprovado].max(), excel_df[date_column_preliminar].max())

    start_date, end_date = st.sidebar.date_input(
        'Select Date Range',
        value=[min_date, max_date],
        min_value=min_date.date(),
        max_value=max_date.date()
    )
    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)

    # Filtered data
    filtered_df_definitivo = filter_by_date_and_status(excel_df, date_column_aprovado, start_date, end_date)
    filtered_df_preliminar = filter_by_date_and_status(excel_df, date_column_preliminar, start_date, end_date)

    # Unidade filter
    hospital_list = filtered_df_definitivo['UNIDADE'].unique()
    selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list)

    # Doctor filter
    doctor_list_definitivo = filtered_df_definitivo[filtered_df_definitivo['UNIDADE'] == selected_hospital]['MEDICO_LAUDO_DEFINITIVO'].unique()
    selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list_definitivo)
    st.markdown(f"<h3 style='color:red;'>{selected_doctor}</h3>", unsafe_allow_html=True)

    # Apply doctor filter
    filtered_df_definitivo = filtered_df_definitivo[filtered_df_definitivo['MEDICO_LAUDO_DEFINITIVO'] == selected_doctor]
    filtered_df_preliminar = filtered_df_preliminar[filtered_df_preliminar['MEDICO_LAUDOO_PRELIMINAR'] == selected_doctor]

    # Display reports
    st.markdown("### Definitive Reports")
    st.dataframe(filtered_df_definitivo)

    st.markdown("### Preliminar Reports")
    st.dataframe(filtered_df_preliminar)

    # Merge data with multipliers
    csv_df['DESCRICAO_PROCEDIMENTO'] = csv_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    filtered_df_definitivo['DESCRICAO_PROCEDIMENTO'] = filtered_df_definitivo['DESCRICAO_PROCEDIMENTO'].str.upper()
    filtered_df_preliminar['DESCRICAO_PROCEDIMENTO'] = filtered_df_preliminar['DESCRICAO_PROCEDIMENTO'].str.upper()

    merged_definitivo = pd.merge(filtered_df_definitivo, csv_df, on='DESCRICAO_PROCEDIMENTO', how='left')
    merged_preliminar = pd.merge(filtered_df_preliminar, csv_df, on='DESCRICAO_PROCEDIMENTO', how='left')

    # Calculate points
    merged_definitivo['POINTS'] = (merged_definitivo['STATUS_APROVADO'].notna().astype(int) * merged_definitivo['MULTIPLIER']).round(1)
    merged_preliminar['POINTS'] = (merged_preliminar['STATUS_PRELIMINAR'].notna().astype(int) * merged_preliminar['MULTIPLIER']).round(1)

    # Display points
    st.markdown("### Definitive Report Points")
    st.write(merged_definitivo[['DESCRICAO_PROCEDIMENTO', 'MULTIPLIER', 'POINTS']])

    st.markdown("### Preliminar Report Points")
    st.write(merged_preliminar[['DESCRICAO_PROCEDIMENTO', 'MULTIPLIER', 'POINTS']])

except Exception as e:
    st.error(f"Error: {e}")


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
