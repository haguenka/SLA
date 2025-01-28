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

# Load and process payment data
@st.cache_data
def load_payment_data(payment_url):
    # Load the Excel file
    response = requests.get(payment_url)
    xlsx_data = BytesIO(response.content)
    excel_file = pd.ExcelFile(xlsx_data)

    # Initialize an empty DataFrame to combine all sheets
    all_payments = pd.DataFrame()

    for sheet_name in excel_file.sheet_names:
        # Load each sheet and extract the relevant columns
        sheet_df = pd.read_excel(excel_file, sheet_name=sheet_name)
        if 'medico' in sheet_df.columns and 'total' in sheet_df.columns:
            # Add a column for month/year based on sheet name
            sheet_df['MONTH_YEAR'] = pd.Period(sheet_name, freq='M')
            all_payments = pd.concat([all_payments, sheet_df], ignore_index=True)
    
    # Standardize column names
    all_payments.rename(columns={'medico': 'DOCTOR', 'total': 'PAYMENT'}, inplace=True)
    
    return all_payments

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
st.sidebar.image(logo, use_column_width=True)

st.title('Medical Production Report')

# Load data
xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
csv_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/multipliers.csv'
payment_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/pagamento.xlsx'

excel_df = load_excel_data(xlsx_url)
csv_df = load_csv_data(csv_url)
payment_df = load_payment_data(payment_url)  # Load the payment data

csv_df.columns = csv_df.columns.str.strip()
excel_df = merge_hospital_names(excel_df, "UNIDADE")

# Sidebar filters
st.sidebar.header('Filter Options')

try:
    # Date processing
    excel_df['STATUS_APROVADO'] = pd.to_datetime(excel_df['STATUS_APROVADO'], format='%d-%m-%Y %H:%M', errors='coerce')
    excel_df['STATUS_PRELIMINAR'] = pd.to_datetime(excel_df['STATUS_PRELIMINAR'], format='%d-%m-%Y %H:%M', errors='coerce')

    # Month/Year selection
    excel_df['MONTH_YEAR'] = excel_df['STATUS_APROVADO'].dt.to_period('M')
    available_months = sorted(excel_df['MONTH_YEAR'].dropna().unique())
    
    if len(available_months) > 0:
        default_month = available_months[-1]
        month_options = [period.strftime("%B %Y") for period in available_months]
    else:
        default_month = pd.Period(datetime.now(), freq='M')
        month_options = [default_month.strftime("%B %Y")]

    selected_month_str = st.sidebar.selectbox(
        'Select Month/Year', 
        options=month_options, 
        index=len(month_options)-1
    )
    
    selected_month = pd.Period(selected_month_str, freq='M')
    start_date = selected_month.start_time
    end_date = selected_month.end_time

    filtered_df = excel_df[
        (excel_df['STATUS_APROVADO'] >= start_date) & 
        (excel_df['STATUS_APROVADO'] <= end_date)
    ]

    hospital_list = filtered_df['UNIDADE'].unique()
    selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list)
    filtered_df = filtered_df[filtered_df['UNIDADE'] == selected_hospital]

    doctor_list = filtered_df['MEDICO_LAUDO_DEFINITIVO'].unique()
    selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list)

    # Automatically fill payment based on the selected month/year and doctor
    doctor_payment = payment_df[
        (payment_df['MONTH_YEAR'] == selected_month) &
        (payment_df['DOCTOR'] == selected_doctor)
    ]['PAYMENT'].sum()

    payment = st.sidebar.number_input(
        'Payment Received (BRL)', 
        min_value=0.0, 
        value=float(doctor_payment), 
        format='%.2f'
    )

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
        unitary_value = payment / total_aprovado_events
    else:
        unitary_value = 0.0
    st.markdown(f"<h3 style='color:green;'>Payment: R$ {payment:,.2f}</h3>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='color:green;'>Unitary Event Value: R$ {unitary_value:,.2f}</h3>", unsafe_allow_html=True)
    
    doctor_all_events = pd.concat([preliminar_df, aprovado_df], ignore_index=True)
    if not doctor_all_events.empty:
        doctor_all_events['STATUS_APROVADO'] = doctor_all_events['STATUS_APROVADO'].dt.strftime('%Y-%m-%d %H:%M')

    filtered_columns = [
        'SAME', 'NOME_PACIENTE', 'TIPO_ATENDIMENTO', 'GRUPO', 'DESCRICAO_PROCEDIMENTO',
        'ESPECIALIDADE', 'STATUS_PRELIMINAR', 'MEDICO_LAUDOO_PRELIMINAR',
        'STATUS_APROVADO', 'MEDICO_LAUDO_DEFINITIVO', 'UNIDADE'
    ]
    st.dataframe(doctor_all_events[filtered_columns], width=1200, height=400)

    # Points calculation
    csv_df['DESCRICAO_PROCEDIMENTO'] = csv_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    aprovado_df['DESCRICAO_PROCEDIMENTO'] = aprovado_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    merged_df = pd.merge(aprovado_df, csv_df, on='DESCRICAO_PROCEDIMENTO', how='left')
    merged_df['MULTIPLIER'] = pd.to_numeric(merged_df['MULTIPLIER'], errors='coerce').fillna(0)
    merged_df['POINTS'] = (merged_df['STATUS_APROVADO'].notna().astype(int) * merged_df['MULTIPLIER']).round(1)

    doctor_grouped = merged_df.groupby(['UNIDADE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO']).agg({
        'MULTIPLIER': 'first',
        'STATUS_APROVADO': 'count'
    }).rename(columns={'STATUS_APROVADO': 'COUNT'}).reset_index()
    
    doctor_grouped['POINTS'] = doctor_grouped['COUNT'] * doctor_grouped['MULTIPLIER']
    total_points_sum = doctor_grouped['POINTS'].sum()
    unitary_point_value = payment / total_points_sum if total_points_sum > 0 else 0.0
    doctor_grouped['POINT_VALUE'] = doctor_grouped['POINTS'] * unitary_point_value

    total_count_sum = doctor_grouped['COUNT'].sum()
    total_point_value_sum = doctor_grouped['POINT_VALUE'].sum()

    for hospital in doctor_grouped['UNIDADE'].unique():
        hospital_df = doctor_grouped[doctor_grouped['UNIDADE'] == hospital]
        st.markdown(f"<h2 style='color:yellow;'>{hospital}</h2>", unsafe_allow_html=True)
        for grupo in hospital_df['GRUPO'].unique():
            grupo_df = hospital_df[hospital_df['GRUPO'] == grupo].copy()
            total_points = grupo_df['POINTS'].sum()
            total_point_value = grupo_df['POINT_VALUE'].sum()
            total_count = grupo_df['COUNT'].sum()
            
            st.markdown(f"<h3 style='color:#0a84ff;'>{grupo}</h3>", unsafe_allow_html=True)
            st.dataframe(grupo_df[[
                'DESCRICAO_PROCEDIMENTO', 
                'COUNT', 
                'MULTIPLIER', 
                'POINTS', 
                'POINT_VALUE'
            ]].style.format({'POINT_VALUE': "R$ {:.2f}"}))
            
            st.write(f"**Total Points: {total_points:.1f}**")
            st.write(f"**Total Value: R$ {total_point_value:.2f}**")
            st.write(f"**Total Exams: {total_count}**")

    st.markdown(f"<h2 style='color:red;'>Total Points: {total_points_sum:.1f}</h2>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:red;'>Total Value: R$ {total_point_value_sum:.2f}</h2>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:red;'>Total Exams: {total_count_sum}</h2>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='color:green;'>Point Value: R$ {unitary_point_value:.4f}/point</h2>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"An error occurred: {e}")


# -----------------------------------------------------------------------------
# EXPORT SUMMARY AND DOCTORS DATAFRAMES AS A COMBINED PDF REPORT
# -----------------------------------------------------------------------------
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
        pdf.cell(0, 10, f'Mês de {selected_month.strftime("%B de %Y").capitalize()}', ln=True, align='C')
        pdf.ln(20)
        # Add doctor's name in uppercase, big and blue
        pdf.set_font('Arial', 'B', 24)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 10, selected_doctor.upper(), ln=True, align='C')
        pdf.set_text_color(0, 0, 0)
        pdf.ln(20)
        
        # Add summary sheet
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'RELATÓRIO DE PRODUÇÃO MÉDICA', ln=True, align='C')
        pdf.ln(10)
        pdf.set_font('Arial', '', 16)
        pdf.cell(0, 10, f'Total de Pontos por Exames Aprovados: {total_points_sum:.1f}', ln=True)
        pdf.cell(0, 10, f'Total de Exames Aprovados: {total_aprovado_events}', ln=True)
        pdf.cell(0, 10, f'Pagamento Recebido: R$ {payment:,.2f}', ln=True)
        if total_aprovado_events > 0:
            unitary_value_pdf = payment / total_aprovado_events
        else:
            unitary_value_pdf = 0.0
        pdf.cell(0, 10, f'Valor Unitário por Evento: R$ {unitary_value_pdf:,.2f}', ln=True)
        pdf.ln(10)
        
        # -----------------------------------------------------------------------------
        # Add "Days Each Doctor Has Events" in table format (using days_merged)
        # -----------------------------------------------------------------------------
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'PERÍODOS/PLANTÃO COM EVENTOS REALIZADOS', ln=True, align='C')
        pdf.ln(10)

        if not days_merged.empty:
            # Table header
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(80, 10, 'MÉDICO', 1, 0, 'C')
            pdf.cell(30, 10, 'DATA', 1, 0, 'C')
            pdf.cell(30, 10, 'DIA DA SEMANA', 1, 0, 'C')
            pdf.cell(30, 10, 'PERÍODO', 1, 0, 'C')
            pdf.cell(30, 10, 'PRELIMINAR', 1, 0, 'C')
            pdf.cell(30, 10, 'APROVADO', 1, 1, 'C')

            pdf.set_font('Arial', '', 10)
            for _, row in days_merged.iterrows():
                pdf.cell(80, 10, str(row['MEDICO']), 1, 0, 'L')
                pdf.cell(30, 10, str(row['DATE']), 1, 0, 'C')
                pdf.cell(30, 10, str(row['DAY_OF_WEEK']), 1, 0, 'C')
                pdf.cell(30, 10, str(row['PERIOD']), 1, 0, 'C')
                pdf.cell(30, 10, str(row['PRELIMINAR_COUNT']), 1, 0, 'C')
                pdf.cell(30, 10, str(row['APROVADO_COUNT']), 1, 1, 'C')

                # Page break if we exceed the height
                if pdf.get_y() > 180:
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 10)
                    pdf.cell(80, 10, 'MÉDICO', 1, 0, 'C')
                    pdf.cell(30, 10, 'DATA', 1, 0, 'C')
                    pdf.cell(30, 10, 'DIA DA SEMANA', 1, 0, 'C')
                    pdf.cell(30, 10, 'PERÍODO', 1, 0, 'C')
                    pdf.cell(30, 10, 'PRELIMINAR', 1, 0, 'C')
                    pdf.cell(30, 10, 'APROVADO', 1, 1, 'C')
        else:
            pdf.set_font('Arial', 'I', 12)
            pdf.cell(0, 10, 'No events found in the selected date range/modality.', ln=True, align='C')

        pdf.ln(10)
        
        # -----------------------------------------------------------------------------
        # Add hospital and modality dataframes to subsequent pages in table format
        # -----------------------------------------------------------------------------
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
                grupo_df = hospital_df[hospital_df['GRUPO'] == grupo].copy()
                grupo_df['POINTS'] = grupo_df['COUNT'] * grupo_df['MULTIPLIER']

                # Create table header
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(80, 10, 'Procedure', 1, 0, 'C')
                pdf.cell(30, 10, 'Count', 1, 0, 'C')
                pdf.cell(30, 10, 'Multiplier', 1, 0, 'C')
                pdf.cell(30, 10, 'Points', 1, 1, 'C')

                # Add rows to the table
                pdf.set_font('Arial', 'B', 10)
                for _, row in grupo_df.iterrows():
                    procedure_text = row['DESCRICAO_PROCEDIMENTO']
                    # Truncate if too long
                    if len(procedure_text) > 30:
                        procedure_text = procedure_text[:30] + '...'
                    pdf.cell(80, 10, procedure_text, 1, 0, 'L')
                    pdf.cell(30, 10, str(row['COUNT']), 1, 0, 'C')
                    pdf.cell(30, 10, f"{row['MULTIPLIER']:.1f}", 1, 0, 'C')
                    pdf.cell(30, 10, f"{row['POINTS']:.1f}", 1, 1, 'C')

                    # Check if we need a page break
                    if pdf.get_y() > 180:  
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
            st.download_button(
                label='Download Combined PDF',
                data=file,
                file_name='Medical_Analysis_Combined_Report.pdf'
            )
    except Exception as e:
        st.error(f'An error occurred while exporting the PDF: {e}')


