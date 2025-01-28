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

    # Get unique months and years from the data
    excel_df['MONTH'] = excel_df['STATUS_APROVADO'].dt.month
    excel_df['YEAR'] = excel_df['STATUS_APROVADO'].dt.year

    unique_months = excel_df['MONTH'].unique()
    unique_years = excel_df['YEAR'].unique()

    # Dropdown for month and year selection
    selected_month = st.sidebar.selectbox('Select Month', unique_months)
    selected_year = st.sidebar.selectbox('Select Year', unique_years)

    # Filter data based on selected month and year
    filtered_df = excel_df[
        (excel_df['MONTH'] == selected_month) & 
        (excel_df['YEAR'] == selected_year)
    ]

    hospital_list = filtered_df['UNIDADE'].unique()
    selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list)
    filtered_df = filtered_df[filtered_df['UNIDADE'] == selected_hospital]

    doctor_list = filtered_df['MEDICO_LAUDO_DEFINITIVO'].unique()
    selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list)
    payment = st.sidebar.number_input('Payment Received (BRL)', min_value=0.0, format='%.2f')

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
    # Points calculation
    csv_df['DESCRICAO_PROCEDIMENTO'] = csv_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    aprovado_df['DESCRICAO_PROCEDIMENTO'] = aprovado_df['DESCRICAO_PROCEDIMENTO'].str.upper()
    merged_df = pd.merge(aprovado_df, csv_df, on='DESCRICAO_PROCEDIMENTO', how='left')
    merged_df['MULTIPLIER'] = pd.to_numeric(merged_df['MULTIPLIER'], errors='coerce').fillna(0)
    merged_df['POINTS'] = (merged_df['STATUS_APROVADO'].notna().astype(int) * merged_df['MULTIPLIER']).round(1)

    # Group and calculate point values
    doctor_grouped = merged_df.groupby(['UNIDADE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO']).agg({
        'MULTIPLIER': 'first',
        'STATUS_APROVADO': 'count'
    }).rename(columns={'STATUS_APROVADO': 'COUNT'}).reset_index()

    doctor_grouped['POINTS'] = doctor_grouped['COUNT'] * doctor_grouped['MULTIPLIER']
    total_points_sum = doctor_grouped['POINTS'].sum()
    unitary_point_value = payment / total_points_sum if total_points_sum > 0 else 0.0
    doctor_grouped['POINT_VALUE'] = doctor_grouped['POINTS'] * unitary_point_value

    # Display results
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
    st.markdown(f"<h2 style='color:green;'>Point Value: R$ {unitary_point_value:.2f}/point</h2>", unsafe_allow_html=True)


    # ------------------------------------------------------------------------------------
    # SHOWING LAUDO PRELIMINAR AND LAUDO APROVADO COUNTS FOR TOMOGRAFIA E RESSONANCIA
    # ------------------------------------------------------------------------------------
    valid_groups = ['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA']

    preliminar_filtered = preliminar_df[preliminar_df['GRUPO'].isin(valid_groups)]
    aprovado_filtered = aprovado_df[aprovado_df['GRUPO'].isin(valid_groups)]

    # For PRELIMINAR
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

    # For APROVADO
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
    days_merged = pd.merge(
        preliminar_days_grouped, 
        aprovado_days_grouped,
        on=['MEDICO', 'DATE', 'DAY_OF_WEEK', 'PERIOD'], 
        how='outer'
    ).fillna(0)

    # Convert to integers to avoid decimals
    days_merged['PRELIMINAR_COUNT'] = days_merged['PRELIMINAR_COUNT'].astype(int)
    days_merged['APROVADO_COUNT'] = days_merged['APROVADO_COUNT'].astype(int)

    # Enforce the desired order of periods
    period_order = ['Manhã', 'Tarde', 'Noite', 'Madrugada']
    days_merged['PERIOD'] = pd.Categorical(days_merged['PERIOD'], categories=period_order, ordered=True)
    days_merged = days_merged.sort_values('PERIOD')

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

    # PDF Generation
    if st.button('Generate PDF Report'):
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(10, 10, 10)

        # Cover Page
        pdf.add_page()
        pdf.image(logo_url, x=80, y=30, w=120)
        pdf.set_font('Arial', 'B', 24)
        pdf.ln(100)
        pdf.cell(0, 10, 'Medical Production Report', 0, 1, 'C')
        pdf.set_font('Arial', '', 18)
        pdf.cell(0, 10, f'Period: {selected_month}/{selected_year}', 0, 1, 'C')
        pdf.ln(20)
        pdf.set_font('Arial', 'B', 24)
        pdf.set_text_color(0, 0, 255)
        pdf.cell(0, 10, selected_doctor.upper(), 0, 1, 'C')
        pdf.set_text_color(0, 0, 0)

        # Summary Page
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Financial Summary', 0, 1)
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f'Total Payment: R$ {payment:,.2f}', 0, 1)
        pdf.cell(0, 10, f'Total Points: {total_points_sum:.1f}', 0, 1)
        pdf.cell(0, 10, f'Point Value: R$ {unitary_point_value:.2f}/point', 0, 1)
        pdf.cell(0, 10, f'Total Calculated Value: R$ {total_point_value_sum:.2f}', 0, 1)

        # Detailed Report
        for hospital in doctor_grouped['UNIDADE'].unique():
            pdf.add_page()
            pdf.set_font('Arial', 'B', 20)
            pdf.cell(0, 10, hospital, 0, 1)
            hospital_df = doctor_grouped[doctor_grouped['UNIDADE'] == hospital]

            for grupo in hospital_df['GRUPO'].unique():
                pdf.set_font('Arial', 'B', 14)
                pdf.cell(0, 10, f'Modality: {grupo}', 0, 1)
                grupo_df = hospital_df[hospital_df['GRUPO'] == grupo]

                # Table Header
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(80, 10, 'Procedure', 1, 0)
                pdf.cell(20, 10, 'Count', 1, 0, 'C')
                pdf.cell(20, 10, 'Multiplier', 1, 0, 'C')
                pdf.cell(20, 10, 'Points', 1, 0, 'C')
                pdf.cell(30, 10, 'Value', 1, 1, 'C')

                # Table Rows
                pdf.set_font('Arial', '', 8)
                for _, row in grupo_df.iterrows():
                    procedure = row['DESCRICAO_PROCEDIMENTO'][:50] + '...' if len(row['DESCRICAO_PROCEDIMENTO']) > 50 else row['DESCRICAO_PROCEDIMENTO']
                    pdf.cell(80, 10, procedure, 1, 0)
                    pdf.cell(20, 10, str(row['COUNT']), 1, 0, 'C')
                    pdf.cell(20, 10, f"{row['MULTIPLIER']:.1f}", 1, 0, 'C')
                    pdf.cell(20, 10, f"{row['POINTS']:.1f}", 1, 0, 'C')
                    pdf.cell(30, 10, f"R$ {row['POINT_VALUE']:.2f}", 1, 1, 'R')

                # Group Summary
                pdf.set_font('Arial', 'B', 10)
                pdf.cell(140, 10, f'Total {grupo}', 1, 0, 'R')
                pdf.cell(20, 10, f"{grupo_df['POINTS'].sum():.1f}", 1, 0, 'C')
                pdf.cell(30, 10, f"R$ {grupo_df['POINT_VALUE'].sum():.2f}", 1, 1, 'R')

        # Save and offer download
        pdf_file = "medical_report.pdf"
        pdf.output(pdf_file)

        with open(pdf_file, "rb") as f:
            st.download_button(
                label="Download Full Report",
                data=f,
                file_name=pdf_file,
                mime="application/pdf"
            )

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
