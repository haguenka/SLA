import streamlit as st
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
from datetime import datetime
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

def assign_period(hour):
    if 0 <= hour < 7:
        return 'Madrugada'
    elif 7 <= hour < 13:
        return 'Manhã'
    elif 13 <= hour < 19:
        return 'Tarde'
    else:
        return 'Noite'

period_colors = {
    'Madrugada': '#555555',
    'Manhã': '#4682b4',
    'Tarde': '#f0ad4e',
    'Noite': '#c0392b'
}

day_translations = {
    'Monday': 'Segunda-feira',
    'Tuesday': 'Terça-feira',
    'Wednesday': 'Quarta-feira',
    'Thursday': 'Quinta-feira',
    'Friday': 'Sexta-feira',
    'Saturday': 'Sábado',
    'Sunday': 'Domingo'
}

hospital_name_mapping = {
    "HSC": "Hospital Santa Catarina",
    "CSSJ": "Casa de Saúde São José",
    "HNSC": "Hospital Nossa Senhora da Conceição"
}

def merge_hospital_names(df, column_name):
    return df.replace({column_name: hospital_name_mapping})

# Load and display logo
logo_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
logo = load_image(logo_url)
st.sidebar.image(logo, use_container_width=True)

st.title('Medical Production Report')

# Load data
xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
csv_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/multipliers.csv'

excel_df = load_excel_data(xlsx_url)
csv_df = load_csv_data(csv_url)
csv_df.columns = csv_df.columns.str.strip()
excel_df = merge_hospital_names(excel_df, "UNIDADE")

# Sidebar filters
st.sidebar.header('Filter Options')

try:
    excel_df['STATUS_APROVADO'] = pd.to_datetime(excel_df['STATUS_APROVADO'], format='%d-%m-%Y %H:%M', errors='coerce')
    excel_df['STATUS_PRELIMINAR'] = pd.to_datetime(excel_df['STATUS_PRELIMINAR'], format='%d-%m-%Y %H:%M', errors='coerce')

    # Extract month and year from the data
    excel_df['MONTH'] = excel_df['STATUS_APROVADO'].dt.month
    excel_df['YEAR'] = excel_df['STATUS_APROVADO'].dt.year

    # Define month names in uppercase
    month_names = [
        "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
        "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
    ]
    
    # Get unique years and months from the data
    unique_years = sorted(excel_df['YEAR'].dropna().unique())
    unique_months = sorted(excel_df['MONTH'].dropna().unique())
    
    # Dropdown for month and year selection in the format "MONTH/YEAR"
    selected_month_name = st.sidebar.selectbox('Select Month/Year', [f"{month}/{year}" for year in unique_years for month in month_names])
    
    # Extract the selected month and year from the selected string
    selected_month, selected_year_str = selected_month_name.split('/')
    selected_month = month_names.index(selected_month) + 1  # Convert month name to number
    
    # Remove decimals from the year string (e.g., "2024.0" -> "2024")
    selected_year_str = selected_year_str.split('.')[0]
    
    # Convert the cleaned year string to an integer
    selected_year = int(selected_year_str)
    
    # Filter data based on selected month and year
    filtered_df = excel_df[
        (excel_df['MONTH'] == selected_month) & 
        (excel_df['YEAR'] == selected_year)
    ]

    # Payment data loading and processing
    payment_file_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/pagamento.xlsx'
    payment_excel = pd.ExcelFile(payment_file_url)
    available_sheets = payment_excel.sheet_names

    # Attempt to match sheet name dynamically
    formatted_sheet_name = f"{month_names[selected_month - 1].capitalize()} {selected_year}"
    matched_sheet_name = next((sheet for sheet in available_sheets if formatted_sheet_name.lower() in sheet.lower()), None)

    if matched_sheet_name:
        # Read the matched sheet
        payment_data = pd.read_excel(payment_excel, sheet_name=matched_sheet_name)
        payment_data['DATE'] = pd.to_datetime(payment_data['DATE'], errors='coerce')
        payment_data = payment_data[payment_data['DATE'].dt.month == selected_month]
    else:
        raise ValueError(f"Sheet matching '{formatted_sheet_name}' not found in {payment_file_url}")

    hospital_list = filtered_df['UNIDADE'].unique()
    selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list)
    filtered_df = filtered_df[filtered_df['UNIDADE'] == selected_hospital]

    doctor_list = filtered_df['MEDICO_LAUDO_DEFINITIVO'].unique()
    selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list)

    # Match and autofill payment for selected doctor
    def normalize_name(name):
        return name.replace("Dr. ", "").replace("Dra. ", "").replace("Dra.","").strip().upper()

    normalized_doctor_name = normalize_name(selected_doctor)
    payment_data['NORMALIZED_MEDICO'] = payment_data['MEDICO'].apply(normalize_name)

    doctor_payment = payment_data[payment_data['NORMALIZED_MEDICO'] == normalized_doctor_name]
    if not doctor_payment.empty:
        total_payment = doctor_payment['PAYMENT'].sum()
    else:
        total_payment = 0.0

    st.sidebar.markdown(f"### Payment: R$ {total_payment:,.2f}")

    st.markdown(f"<h1 style='color:red;'>{selected_doctor}</h1>", unsafe_allow_html=True)

    preliminar_df = filtered_df[
        (filtered_df['STATUS_PRELIMINAR'].notna()) &
        (filtered_df['MEDICO_LAUDOO_PRELIMINAR'] == selected_doctor)
    ]
    aprovado_df = filtered_df[
        (filtered_df['STATUS_APROVADO'].notna()) &
        (filtered_df['MEDICO_LAUDO_DEFINITIVO'] == selected_doctor)
    ]

    total_preliminar_events = len(preliminar_df)
    total_aprovado_events = len(aprovado_df)
    st.markdown(f"<h3 style='color:#f0ad4e;'>Total PRELIMINAR Events: {total_preliminar_events}</h3>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='color:#4682b4;'>Total APROVADO Events: {total_aprovado_events}</h3>", unsafe_allow_html=True)

    if total_aprovado_events > 0:
        unitary_value = total_payment / total_aprovado_events
    else:
        unitary_value = 0.0
    st.markdown(f"<h3 style='color:green;'>Payment: R$ {total_payment:,.2f}</h3>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='color:green;'>Unitary Event Value: R$ {unitary_value:,.2f}</h3>", unsafe_allow_html=True)

    # Combine both preliminar and aprovado data for display (removing seconds from STATUS_APROVADO)
    doctor_all_events = pd.concat([preliminar_df, aprovado_df], ignore_index=True)
    if not doctor_all_events.empty:
        doctor_all_events['STATUS_APROVADO'] = doctor_all_events['STATUS_APROVADO'].dt.strftime('%Y-%m-%d %H:%M')
    filtered_columns = [
        'SAME', 'NOME_PACIENTE', 'TIPO_ATENDIMENTO', 'GRUPO', 'DESCRICAO_PROCEDIMENTO',
        'ESPECIALIDADE', 'STATUS_PRELIMINAR', 'MEDICO_LAUDOO_PRELIMINAR',
        'STATUS_APROVADO', 'MEDICO_LAUDO_DEFINITIVO', 'UNIDADE'
    ]
    st.dataframe(doctor_all_events[filtered_columns], width=1200, height=400)

    # ------------------------------------------------------------------------------------
    # EXPORT SUMMARY AND DOCTORS DATAFRAMES AS A COMBINED PDF REPORT
    # ------------------------------------------------------------------------------------
    if st.button('Export Summary and Doctors Dataframes as PDF'):
        try:
            if doctor_all_events.empty:
                st.error("No data available to export in the PDF report.")
            else:
                pdf = FPDF(orientation='L', unit='mm', format='A4')
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_margins(left=5, top=5, right=5)

                # Title Page
                pdf.add_page()
                pdf.image(logo_url, x=80, y=30, w=120)
                pdf.set_font('Arial', 'B', 24)
                pdf.ln(100)
                pdf.cell(0, 10, 'Relatório de Produção Médica', ln=True, align='C')
                pdf.ln(10)
                pdf.set_font('Arial', '', 18)
                pdf.cell(0, 10, f'Mês de {selected_month_name} {selected_year}', 0, 1, 'C')
                pdf.ln(20)

                # Summary Page
                pdf.add_page()
                pdf.set_font('Arial', 'B', 16)
                pdf.cell(0, 10, 'Resumo da Produção Médica', ln=True, align='C')
                pdf.ln(10)
                pdf.set_font('Arial', '', 12)
                pdf.cell(0, 10, f'Total de Exames Aprovados: {total_aprovado_events}', ln=True)
                pdf.cell(0, 10, f'Total de Pagamento: R$ {total_payment:,.2f}', ln=True)
                pdf.cell(0, 10, f'Valor por Exame: R$ {unitary_value:,.2f}', ln=True)

                # Data Table Page
                pdf.add_page()
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(60, 10, 'Descrição do Procedimento', 1)
                pdf.cell(30, 10, 'Quantidade', 1)
                pdf.cell(30, 10, 'Multiplicador', 1)
                pdf.cell(30, 10, 'Pontos', 1)
                pdf.cell(40, 10, 'Valor', 1, ln=1)

                pdf.set_font('Arial', '', 10)
                for index, row in doctor_all_events.iterrows():
                    pdf.cell(60, 10, str(row['DESCRICAO_PROCEDIMENTO']), 1)
                    pdf.cell(30, 10, str(row.get('COUNT', '')), 1)
                    pdf.cell(30, 10, f"{row.get('MULTIPLIER', 0):.2f}", 1)
                    pdf.cell(30, 10, f"{row.get('POINTS', 0):.2f}", 1)
                    pdf.cell(40, 10, f"R$ {row.get('POINT_VALUE', 0):,.2f}", 1, ln=1)

                pdf_file_path = 'Medical_Production_Report.pdf'
                pdf.output(pdf_file_path)

                # Streamlit download button
                with open(pdf_file_path, 'rb') as file:
                    st.download_button(
                        label='Download PDF Report',
                        data=file,
                        file_name='Medical_Production_Report.pdf',
                        mime='application/pdf'
                    )

        except Exception as e:
            st.error(f"An error occurred during PDF generation: {e}")

except Exception as e:
    st.error(f"An unexpected error occurred: {e}")
