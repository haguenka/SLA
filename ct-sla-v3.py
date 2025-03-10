import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image
import requests
from io import BytesIO

@st.cache_data
def load_logo(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

@st.cache_data
def load_excel_from_github():
    try:
        url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_excel(BytesIO(response.content))
    except requests.exceptions.RequestException:
        return None

# Streamlit file uploader
st.title("SLA Dashboard for CT Exams")

# Load and display logo from GitHub
url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
response = requests.get(url)
logo = Image.open(BytesIO(response.content))
st.sidebar.image(logo, use_container_width=True)

df = load_excel_from_github()

if df is not None:
    # Filter the data for 'CT' modality and 'Pronto Atendimento'
    filtered_df = df[(df['MODALIDADE'] == 'CT') & (df['TIPO_ATENDIMENTO'] == 'Pronto Atendimento')]

    # Convert the relevant time columns to datetime, using dayfirst=True to handle DD-MM-YYYY format
    filtered_df['DATA_HORA_PRESCRICAO'] = pd.to_datetime(filtered_df['DATA_HORA_PRESCRICAO'], dayfirst=True, errors='coerce')
    filtered_df['STATUS_ALAUDAR'] = pd.to_datetime(filtered_df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')

    # Create the "EM ESPERA" flag for rows where STATUS_ALAUDAR is empty
    filtered_df['EM_ESPERA'] = filtered_df['STATUS_ALAUDAR'].isna()

    # Drop rows where the prescription date is invalid
    filtered_df = filtered_df.dropna(subset=['DATA_HORA_PRESCRICAO'])

    # Sidebar for selecting UNIDADE and Date
    st.sidebar.header("Filter Options")

    # UNIDADE selection
    unidade_options = filtered_df['UNIDADE'].dropna().unique()
    selected_unidade = st.sidebar.selectbox('Select UNIDADE', options=unidade_options)

    # Apply UNIDADE filter before further processing
    filtered_df = filtered_df[filtered_df['UNIDADE'] == selected_unidade]

    # Date selection (specific day or range)
    date_option = st.sidebar.radio("Select Date Option", ['Specific Day', 'Date Range'])

    if date_option == 'Specific Day':
        selected_date = st.sidebar.date_input("Choose a day", value=pd.to_datetime('today'))
        # Filter for the specific day (start from 7 AM and end at 6:59 AM next day)
        start_date = pd.to_datetime(selected_date) + pd.DateOffset(hours=7)
        end_date = start_date + pd.Timedelta(hours=23, minutes=59)  # Include until 6:59 AM next day
        filtered_df = filtered_df[(filtered_df['DATA_HORA_PRESCRICAO'] >= start_date) & 
                                  (filtered_df['DATA_HORA_PRESCRICAO'] < end_date)]
    else:
        start_date, end_date = st.sidebar.date_input("Select date range", value=(pd.to_datetime('today') - pd.DateOffset(days=7), pd.to_datetime('today')))
        # Adjust date range to start at 7:00 AM of the first day and end at 6:59 AM of the day after the last day
        start_date = pd.to_datetime(start_date) + pd.DateOffset(hours=7)
        end_date = pd.to_datetime(end_date) + pd.Timedelta(hours=6, minutes=59)  # Include until 6:59 AM of the next day
        filtered_df = filtered_df[(filtered_df['DATA_HORA_PRESCRICAO'] >= start_date) & 
                                  (filtered_df['DATA_HORA_PRESCRICAO'] < end_date)]

    # Check if there is data to display after filtering
    if filtered_df.empty:
        st.write("No data available for the selected UNIDADE and date range.")
    else:
        # Display the filtered dataframe
        st.markdown(f"### Filtered Data for {selected_unidade}")
        st.dataframe(filtered_df)

        # Calculate the time difference (in hours) for rows where STATUS_ALAUDAR is not NaT
        filtered_df['PROCESS_TIME_HOURS'] = (filtered_df['STATUS_ALAUDAR'] - filtered_df['DATA_HORA_PRESCRICAO']).dt.total_seconds() / 3600

        # Classify into time intervals
        def classify_sla(hours):
            if pd.isnull(hours):
                return 'No Data'
            if hours <= 1:
                return 'Within SLA'
            elif hours <= 2:
                return '1 to 2 hours'
            elif hours <= 3:
                return '2 to 3 hours'
            else:
                return 'Over 3 hours'

        # Apply the classification
        filtered_df['SLA_STATUS'] = filtered_df['PROCESS_TIME_HOURS'].apply(classify_sla)

        # Flagging cases that exceed the 1-hour limit as 'FORA DO PRAZO'
        filtered_df['FORA_DO_PRAZO'] = filtered_df['PROCESS_TIME_HOURS'] > 1

        # Function to get the adjusted day of the week (7 AM to 7 AM next day)
        def get_adjusted_day_of_week(datetime_val):
            if datetime_val.hour < 7:
                adjusted_datetime = datetime_val - pd.Timedelta(days=1)  # Move to the previous day
            else:
                adjusted_datetime = datetime_val
            return adjusted_datetime.day_name()

        # Apply the adjusted day of the week logic
        filtered_df['DAY_OF_WEEK'] = filtered_df['DATA_HORA_PRESCRICAO'].apply(get_adjusted_day_of_week)

        # Create time periods (morning, afternoon, night)
        def get_period(hour):
            if 7 <= hour < 13:
                return 'Morning'
            elif 13 <= hour < 19:
                return 'Afternoon'
            else:
                return 'Night'

        filtered_df['HOUR'] = filtered_df['DATA_HORA_PRESCRICAO'].dt.hour
        filtered_df['TIME_PERIOD'] = filtered_df['HOUR'].apply(get_period)

        # Ensure DATE column exists
        filtered_df['DATE'] = filtered_df['DATA_HORA_PRESCRICAO'].dt.date

        # Display the dataframe with the analysis columns (SLA status, process time, etc.)
        st.write(f"### Processed Data with SLA Status for {selected_unidade}")
        st.dataframe(filtered_df[['DATA_HORA_PRESCRICAO', 'STATUS_ALAUDAR', 'PROCESS_TIME_HOURS', 'SLA_STATUS', 'FORA_DO_PRAZO']])

        # Display the dataframe with only "EM ESPERA" flagged cases
        st.markdown("### Data with 'EM ESPERA' Flag")
        espera_df = filtered_df[filtered_df['EM_ESPERA'] == True]
        st.dataframe(espera_df[['EM_ESPERA', 'NOME_PACIENTE', 'DESCRICAO_PROCEDIMENTO', 'DATA_HORA_PRESCRICAO', 'STATUS_ALAUDAR', 'SLA_STATUS']])


        # Calculate totals and averages
        total_patients = filtered_df.shape[0] - espera_df.shape[0]
        avg_process_time = filtered_df['PROCESS_TIME_HOURS'].mean()

        # --- Layout starts here ---
        st.markdown("## Overview")
        st.markdown(f"**Total Patients Processed**: {total_patients}")
        st.markdown(f"**Average Process Time (in hours)**: {avg_process_time:.2f}")

        # Group graphs in two columns for cleaner layout
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### SLA Violations Pie Chart")
            fig2, ax2 = plt.subplots()
            violation_data = [filtered_df[filtered_df['FORA_DO_PRAZO']].shape[0], filtered_df[~filtered_df['FORA_DO_PRAZO']].shape[0]]
            labels = ['FORA DO PRAZO', 'Within SLA']
            ax2.pie(violation_data, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#ff9999', '#99ff99'])
            ax2.set_title('SLA Violations')
            st.pyplot(fig2)

        with col2:
            st.markdown("### Average Process Time by SLA Category")
            avg_process_by_sla = filtered_df.groupby('SLA_STATUS')['PROCESS_TIME_HOURS'].mean()
            fig3, ax3 = plt.subplots()
            avg_process_by_sla.plot(kind='bar', ax=ax3, color='#66b3ff')
            ax3.set_ylabel('Average Time (hours)')
            ax3.set_title('Average Process Time by SLA Category')
            st.pyplot(fig3)

        st.markdown("---")
        st.markdown("## Heatmaps")

        # Group heatmaps into another two-column layout
        col3, col4 = st.columns(2)

        with col3:
            st.markdown("### Heatmap of Exams by Day and Time Period")
            heatmap_data = filtered_df.groupby(['DAY_OF_WEEK', 'TIME_PERIOD']).size().unstack(fill_value=0)
            fig4, ax4 = plt.subplots(figsize=(10, 6))
            sns.heatmap(heatmap_data, annot=True, fmt='d', cmap='coolwarm', ax=ax4)
            ax4.set_title('Number of Exams by Day and Time Period')
            st.pyplot(fig4)

        with col4:
            st.markdown("### Heatmap of Exams within SLA by Day and Time Period")
            sla_heatmap_data = filtered_df[filtered_df['SLA_STATUS'] == 'Within SLA'].groupby(['DAY_OF_WEEK', 'TIME_PERIOD']).size().unstack(fill_value=0)
            fig5, ax5 = plt.subplots(figsize=(10, 6))
            sns.heatmap(sla_heatmap_data, annot=True, fmt='d', cmap='Blues', ax=ax5)
            ax5.set_title('Exams Within SLA by Day and Time Period')
            st.pyplot(fig5)

        # Worst day analysis
        st.markdown("---")
        st.markdown("## Top 10 Worst Days by FORA DO PRAZO Count")

        # Group by Date, Day of Week, and Time Period for the worst days analysis
        worst_days = filtered_df[filtered_df['FORA_DO_PRAZO']].groupby(['DATE', 'DAY_OF_WEEK', 'TIME_PERIOD']).size().reset_index(name='FORA_DO_PRAZO_COUNT')
        worst_days = worst_days.sort_values(by='FORA_DO_PRAZO_COUNT', ascending=False).head(10)

        if worst_days.shape[0] > 0:
            st.dataframe(worst_days)

            st.markdown("### Heatmap of FORA DO PRAZO on Top 10 Worst Days")
            worst_day_labels = worst_days['DATE'].astype(str).tolist()

            # Filter only FORA DO PRAZO exams for the worst days
            filtered_df['DAY'] = filtered_df['DATA_HORA_PRESCRICAO'].dt.date.astype(str)
            filtered_df['WORST_DAY_FLAG'] = filtered_df['DAY'].apply(lambda x: 1 if x in worst_day_labels else 0)

            # Group for heatmap display: show count of FORA DO PRAZO by day of the week and time period for the worst days
            worst_day_heatmap_data = filtered_df[(filtered_df['WORST_DAY_FLAG'] == 1) & (filtered_df['FORA_DO_PRAZO'])].groupby(['DAY_OF_WEEK', 'TIME_PERIOD']).size().unstack(fill_value=0)

            # Create annotation text for the heatmap with both "FORA DO PRAZO" counts and dates
            def create_annotation_text(row, col, data, worst_days):
                if data.at[row, col] > 0:
                    matched_rows = worst_days[(worst_days['DAY_OF_WEEK'] == row) & (worst_days['TIME_PERIOD'] == col)]
                    if not matched_rows.empty:
                        dates = ', '.join(matched_rows['DATE'].astype(str).values)
                        return f"{data.at[row, col]} ({dates})"
                return ""

            # Apply the annotation function
            annotations = [[create_annotation_text(row, col, worst_day_heatmap_data, worst_days)
                            for col in worst_day_heatmap_data.columns] for row in worst_day_heatmap_data.index]

            # Display the heatmap for the top 10 worst days
            fig6, ax6 = plt.subplots(figsize=(10, 6))
            sns.heatmap(worst_day_heatmap_data, annot=annotations, fmt='', cmap='Reds', ax=ax6, cbar=False)
            ax6.set_title('Number of FORA DO PRAZO Exams on Top 10 Worst Days (with Dates)')
            st.pyplot(fig6)

else:
    st.write("Please upload an Excel file to continue.")
