import streamlit as st
import pandas as pd
from PIL import Image
import requests
from io import BytesIO
from datetime import datetime
from fpdf import FPDF

# -----------------------------
# Your existing data loading/caching functions
# -----------------------------
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

def normalize_name(name: str) -> str:
    """
    Helper function to normalize doctor names
    so they match between excel_df and payment_data.
    """
    return (
        str(name)
        .replace("Dr. ", "")
        .replace("Dra. ", "")
        .replace("Dra.","")
        .strip()
        .upper()
    )

# -----------------------------
# Load and display logo
# -----------------------------
logo_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
logo = load_image(logo_url)
st.sidebar.image(logo, use_container_width=True)

st.title('Medical Production Report')

# -----------------------------
# Load data
# -----------------------------
xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
csv_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/multipliers.csv'

excel_df = load_excel_data(xlsx_url)
csv_df = load_csv_data(csv_url)
csv_df.columns = csv_df.columns.str.strip()
excel_df = merge_hospital_names(excel_df, "UNIDADE")

payment_file_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/pagamento.xlsx'
payment_excel = pd.ExcelFile(payment_file_url)
available_sheets = payment_excel.sheet_names

# Convert to uppercase **once** so that merges are consistent
excel_df['DESCRICAO_PROCEDIMENTO'] = excel_df['DESCRICAO_PROCEDIMENTO'].astype(str).str.upper()
csv_df['DESCRICAO_PROCEDIMENTO'] = csv_df['DESCRICAO_PROCEDIMENTO'].astype(str).str.upper()

try:
    # -----------------------------
    # Pre-process excel_df
    # -----------------------------
    excel_df['STATUS_APROVADO'] = pd.to_datetime(excel_df['STATUS_APROVADO'], format='%d-%m-%Y %H:%M', errors='coerce')
    excel_df['STATUS_PRELIMINAR'] = pd.to_datetime(excel_df['STATUS_PRELIMINAR'], format='%d-%m-%Y %H:%M', errors='coerce')

    # Extract month and year
    excel_df['MONTH'] = excel_df['STATUS_APROVADO'].dt.month
    excel_df['YEAR'] = excel_df['STATUS_APROVADO'].dt.year

    # Define month names in uppercase
    month_names = [
        "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
        "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
    ]
    
    # Unique years
    unique_years = sorted(excel_df['YEAR'].dropna().unique())
    
    st.sidebar.header('Filter Options')
    # Sidebar selects MONTH/YEAR
    selected_month_name = st.sidebar.selectbox(
        'Select Month/Year',
        [f"{month}/{year}" for year in unique_years for month in month_names]
    )
    # Parse selected month/year
    selected_month_str, selected_year_str = selected_month_name.split('/')
    selected_month = month_names.index(selected_month_str) + 1
    selected_year_str = selected_year_str.split('.')[0]  # remove decimals, e.g. "2024.0"
    selected_year = int(selected_year_str)

    # Filter excel_df by month/year
    filtered_df = excel_df[
        (excel_df['MONTH'] == selected_month) &
        (excel_df['YEAR'] == selected_year)
    ]

    # -------------
    # Attempt to match sheet name in pagamento.xlsx
    # -------------
    formatted_sheet_name = f"{month_names[selected_month - 1].capitalize()} {selected_year}"
    matched_sheet_name = next(
        (sheet for sheet in available_sheets if formatted_sheet_name.lower() in sheet.lower()), 
        None
    )
    if not matched_sheet_name:
        raise ValueError(f"Sheet matching '{formatted_sheet_name}' not found in {payment_file_url}")
    
    # Load payment_data for selected month
    payment_data = pd.read_excel(payment_excel, sheet_name=matched_sheet_name)
    payment_data['DATE'] = pd.to_datetime(payment_data['DATE'], errors='coerce')
    payment_data = payment_data[payment_data['DATE'].dt.month == selected_month]

except Exception as e:
    st.error(f"An error occurred during data preparation: {e}")

# -----------------------------
# Create TABS for the two pages
# -----------------------------
tab1, tab2 = st.tabs(["Individual Doctor View", "Worst/Best Doctors"])

# ------------------------------------------------------------------------------
# TAB 1: Original Single-Doctor Analysis
# ------------------------------------------------------------------------------
with tab1:
    try:
        # HOSPITAL FILTER
        hospital_list = sorted(filtered_df['UNIDADE'].dropna().unique())
        selected_hospital = st.sidebar.selectbox('Select Hospital', hospital_list)

        # Filter by selected hospital
        hospital_df = filtered_df[filtered_df['UNIDADE'] == selected_hospital]

        # DOCTOR FILTER
        doctor_list = sorted(hospital_df['MEDICO_LAUDO_DEFINITIVO'].dropna().unique())
        selected_doctor = st.sidebar.selectbox('Select Doctor', doctor_list)

        # Match and autofill payment for selected doctor
        payment_data['NORMALIZED_MEDICO'] = payment_data['MEDICO'].apply(normalize_name)
        normalized_doctor_name = normalize_name(selected_doctor)
        doctor_payment = payment_data[payment_data['NORMALIZED_MEDICO'] == normalized_doctor_name]
        if not doctor_payment.empty:
            total_payment = doctor_payment['PAYMENT'].sum()
        else:
            total_payment = 0.0

        st.sidebar.markdown(f"### Payment: R$ {total_payment:,.2f}")
        st.markdown(f"<h1 style='color:red;'>{selected_doctor}</h1>", unsafe_allow_html=True)

        # Filter data for the selected doctor
        preliminar_df = hospital_df[
            (hospital_df['STATUS_PRELIMINAR'].notna()) &
            (hospital_df['MEDICO_LAUDOO_PRELIMINAR'] == selected_doctor)
        ]
        aprovado_df = hospital_df[
            (hospital_df['STATUS_APROVADO'].notna()) &
            (hospital_df['MEDICO_LAUDO_DEFINITIVO'] == selected_doctor)
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

        # Combine data for display
        doctor_all_events = pd.concat([preliminar_df, aprovado_df], ignore_index=True)
        if not doctor_all_events.empty:
            doctor_all_events['STATUS_APROVADO'] = doctor_all_events['STATUS_APROVADO'].dt.strftime('%Y-%m-%d %H:%M')
        filtered_columns = [
            'SAME', 'NOME_PACIENTE', 'TIPO_ATENDIMENTO', 'GRUPO', 'DESCRICAO_PROCEDIMENTO',
            'ESPECIALIDADE', 'STATUS_PRELIMINAR', 'MEDICO_LAUDOO_PRELIMINAR',
            'STATUS_APROVADO', 'MEDICO_LAUDO_DEFINITIVO', 'UNIDADE'
        ]
        st.dataframe(doctor_all_events[filtered_columns], width=1200, height=400)

        # -------------
        # Points calculation for the selected doctor
        # -------------
        # (We already made DESCRICAO_PROCEDIMENTO uppercase above)
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
        unitary_point_value = total_payment / total_points_sum if total_points_sum > 0 else 0.0
        doctor_grouped['POINT_VALUE'] = doctor_grouped['POINTS'] * unitary_point_value

        total_count_sum = doctor_grouped['COUNT'].sum()
        total_point_value_sum = doctor_grouped['POINT_VALUE'].sum()

        for hosp in doctor_grouped['UNIDADE'].unique():
            hos_df = doctor_grouped[doctor_grouped['UNIDADE'] == hosp]
            st.markdown(f"<h2 style='color:yellow;'>{hosp}</h2>", unsafe_allow_html=True)
            for grupo in hos_df['GRUPO'].unique():
                grupo_df = hos_df[hos_df['GRUPO'] == grupo].copy()
                total_points = grupo_df['POINTS'].sum()
                total_pvalue = grupo_df['POINT_VALUE'].sum()
                total_count = grupo_df['COUNT'].sum()

                st.markdown(f"<h3 style='color:#0a84ff;'>{grupo}</h3>", unsafe_allow_html=True)
                st.dataframe(
                    grupo_df[[
                        'DESCRICAO_PROCEDIMENTO',
                        'COUNT',
                        'MULTIPLIER',
                        'POINTS',
                        'POINT_VALUE'
                    ]].style.format({'POINT_VALUE': "R$ {:.2f}"})
                )

        st.markdown(f"<h2 style='color:red;'>Total Points: {total_points_sum:.1f}</h2>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color:red;'>Total Value: R$ {total_point_value_sum:.2f}</h2>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color:red;'>Total Exams: {total_count_sum}</h2>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color:green;'>Point Value: R$ {unitary_point_value:.2f}/point</h2>", unsafe_allow_html=True)

        # --------------------------------------------------------------------
        # LAUDO PRELIMINAR x LAUDO APROVADO (Tomografia & Ressonancia) 
        # --------------------------------------------------------------------
        valid_groups = ['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA']

        preliminar_filtered = preliminar_df[preliminar_df['GRUPO'].isin(valid_groups)]
        aprovado_filtered = aprovado_df[aprovado_df['GRUPO'].isin(valid_groups)]

        # PRELIMINAR
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
            preliminar_days_grouped = pd.DataFrame(columns=['MEDICO','DATE','DAY_OF_WEEK','PERIOD','PRELIMINAR_COUNT'])

        # APROVADO
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
            aprovado_days_grouped = pd.DataFrame(columns=['MEDICO','DATE','DAY_OF_WEEK','PERIOD','APROVADO_COUNT'])

        # Merge both
        days_merged = pd.merge(
            preliminar_days_grouped, 
            aprovado_days_grouped,
            on=['MEDICO','DATE','DAY_OF_WEEK','PERIOD'],
            how='outer'
        ).fillna(0)

        # Convert to integers
        days_merged['PRELIMINAR_COUNT'] = days_merged['PRELIMINAR_COUNT'].astype(int)
        days_merged['APROVADO_COUNT'] = days_merged['APROVADO_COUNT'].astype(int)

        # Enforce order of periods
        period_order = ['Manhã', 'Tarde', 'Noite', 'Madrugada']
        days_merged['PERIOD'] = pd.Categorical(days_merged['PERIOD'], categories=period_order, ordered=True)
        days_merged = days_merged.sort_values('PERIOD')

        # Style for DataFrame
        def color_rows(row):
            return [
                f'background-color: {period_colors.get(row["PERIOD"], "white")}; color: white'
                for _ in row.index
            ]
        styled_df = days_merged.style.apply(color_rows, axis=1)

        st.markdown("### LAUDO PRELIMINAR and LAUDO APROVADO Counts by Period (Tomografia and Ressonancia)")
        st.dataframe(styled_df, width=1200, height=400)

    except Exception as e:
        st.error(f"An error occurred in Tab 1: {e}")


# ------------------------------------------------------------------------------
# TAB 2: Worst 10 & Best 5 Doctors (by VALUE_PER_UNIT) + VALUE_PER_POINT
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("Worst & Best Doctors by Value per Approved Exam (and Value per Point)")

    try:
        # 1) Focus on the entire dataset for the selected month/year 
        #    (only rows that actually have a 'STATUS_APROVADO')
        month_df = excel_df[
            (excel_df['MONTH'] == selected_month) & 
            (excel_df['YEAR'] == selected_year)
        ].dropna(subset=['STATUS_APROVADO']).copy()

        # 2) Merge with csv_df to get MULTIPLIER, compute total points
        #    Because we already did uppercase merges above, 
        #    we can safely join on DESCRICAO_PROCEDIMENTO
        points_merged = pd.merge(month_df, csv_df, on="DESCRICAO_PROCEDIMENTO", how="left")
        points_merged['MULTIPLIER'] = pd.to_numeric(points_merged['MULTIPLIER'], errors='coerce').fillna(0)
        points_merged['POINTS'] = points_merged['MULTIPLIER']  # 1 exam => "MULTIPLIER" points

        # 3) Sum total points by doctor
        points_sum = (
            points_merged
            .groupby("MEDICO_LAUDO_DEFINITIVO")['POINTS']
            .sum()
            .reset_index(name="TOTAL_POINTS")
        )
        points_sum["NORMALIZED_MEDICO"] = points_sum["MEDICO_LAUDO_DEFINITIVO"].apply(normalize_name)

        # 4) Count how many approved exams each doctor has
        approved_counts = (
            month_df
            .groupby("MEDICO_LAUDO_DEFINITIVO")
            .size()
            .reset_index(name="APPROVED_COUNT")
        )
        approved_counts["NORMALIZED_MEDICO"] = approved_counts["MEDICO_LAUDO_DEFINITIVO"].apply(normalize_name)

        # 5) Sum total payments for the same month in 'payment_data'
        pay_month = payment_data.copy()  # already filtered by month
        pay_month["NORMALIZED_MEDICO"] = pay_month["MEDICO"].apply(normalize_name)
        pay_sums = (
            pay_month
            .groupby("NORMALIZED_MEDICO")["PAYMENT"]
            .sum()
            .reset_index(name="TOTAL_PAYMENT")
        )

        # 6) Merge to get: APPROVED_COUNT, TOTAL_POINTS, TOTAL_PAYMENT
        merged_doctors = pd.merge(approved_counts, points_sum, on="NORMALIZED_MEDICO", how="inner")
        merged_doctors = pd.merge(merged_doctors, pay_sums, on="NORMALIZED_MEDICO", how="inner")

        # 7) Filter only doctors with > 0 payment and > 0 approved exams
        merged_doctors = merged_doctors[
            (merged_doctors["TOTAL_PAYMENT"] > 0) & 
            (merged_doctors["APPROVED_COUNT"] > 0)
        ]

        # 8) Compute both metrics
        merged_doctors["VALUE_PER_UNIT"] = merged_doctors["TOTAL_PAYMENT"] / merged_doctors["APPROVED_COUNT"]
        merged_doctors["VALUE_PER_POINT"] = merged_doctors["TOTAL_PAYMENT"] / merged_doctors["TOTAL_POINTS"]

        # 9) Sort for worst 10 (highest VALUE_PER_UNIT) and best 5 (lowest)
        worst_10 = merged_doctors.nlargest(10, "VALUE_PER_UNIT")
        best_10 = merged_doctors.nsmallest(5, "VALUE_PER_UNIT")

        # 10) Display results
        st.markdown("### Worst 10 Doctors by Value per Approved Exam")
        st.dataframe(
            worst_10[[
                "MEDICO_LAUDO_DEFINITIVO",
                "APPROVED_COUNT",
                "TOTAL_POINTS",
                "TOTAL_PAYMENT",
                "VALUE_PER_UNIT",
                "VALUE_PER_POINT",
            ]].style.format({
                "TOTAL_PAYMENT": "R$ {:.2f}",
                "VALUE_PER_UNIT": "R$ {:.2f}",
                "VALUE_PER_POINT": "R$ {:.2f}"
            })
        )

        st.markdown("### Best 10 Doctors by Value per Approved Exam")
        st.dataframe(
            best_10[[
                "MEDICO_LAUDO_DEFINITIVO",
                "APPROVED_COUNT",
                "TOTAL_POINTS",
                "TOTAL_PAYMENT",
                "VALUE_PER_UNIT",
                "VALUE_PER_POINT",
            ]].style.format({
                "TOTAL_PAYMENT": "R$ {:.2f}",
                "VALUE_PER_UNIT": "R$ {:.2f}",
                "VALUE_PER_POINT": "R$ {:.2f}"
            })
        )

    except Exception as e:
        st.error(f"An error occurred while creating the worst/best lists: {e}")

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
        pdf.cell(0, 10, f'Mês de {selected_month_name} {selected_year}', 0, 1, 'C')
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
        pdf.cell(0, 10, f'Pagamento Recebido: R$ {total_payment:,.2f}', ln=True)
        if total_aprovado_events > 0:
            unitary_value_pdf = total_payment / total_aprovado_events
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
                pdf.set_font('Arial', '', 10)
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
