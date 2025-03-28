import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd

# File uploader to select the dataset
st.set_page_config(layout="wide", page_title="Breast Cancer Prevention Dashboard")

# Sidebar menu
with st.sidebar:
    st.title('Navigation')
    menu_options = [
        'Upload File',
        'Total Number of Exams',
        'Number of Studies per Day',
        'SLA Compliance',
        'SLA Compliance Over Time',
        'Number of Exams per Unidade',
        'Count by Medico Laudo Definitivo',
        'Exams Without Report'
    ]
    selection = st.radio('Go to', menu_options)

file = st.sidebar.file_uploader('Upload Excel File', type=['xlsx'])

if file is not None:
    # Load the dataset
    df = pd.read_excel(file, 'Sheet1')

    # Filter relevant rows and columns
    mamografia_df = df[df['DESCRICAO_PROCEDIMENTO'].str.contains('MAMOGRAFIA', case=False, na=False)]
    mamografia_df = mamografia_df[mamografia_df['MEDICO_SOLICITANTE'].isin(['MARCELO JACOBINA DE ABREU', 'HENRIQUE ARUME GUENKA'])]
    
    # Convert date columns to datetime with dayfirst=True
    mamografia_df['DATA_HORA_PRESCRICAO'] = pd.to_datetime(mamografia_df['DATA_HORA_PRESCRICAO'], dayfirst=True, errors='coerce')
    mamografia_df['STATUS_APROVADO'] = pd.to_datetime(mamografia_df['STATUS_APROVADO'], dayfirst=True, errors='coerce')
    mamografia_df['STATUS_ALAUDAR'] = pd.to_datetime(mamografia_df['STATUS_APROVADO'], dayfirst=True, errors='coerce')
    
    # Filter out invalid dates
    mamografia_df = mamografia_df.dropna(subset=['DATA_HORA_PRESCRICAO'])

    # Calculate SLA timing (5 days)
    mamografia_df['SLA_MET'] = (mamografia_df['STATUS_APROVADO'] - mamografia_df['STATUS_ALAUDAR']).dt.days <= 10

    # Drop-down selection for "UNIDADE" and specific date/period selection
    if not mamografia_df.empty:
        unidade_selected = st.sidebar.selectbox('Select Unidade', mamografia_df['UNIDADE'].unique())
        date_selection = st.sidebar.date_input('Select a specific day or period of time', value=(mamografia_df['DATA_HORA_PRESCRICAO'].min(), mamografia_df['DATA_HORA_PRESCRICAO'].max()), key='date_selection', help='Select a date or a range of dates')

        filtered_df = mamografia_df[mamografia_df['UNIDADE'] == unidade_selected]

        if isinstance(date_selection, tuple) and len(date_selection) == 2:
            start_date, end_date = date_selection
            filtered_df = filtered_df[(filtered_df['DATA_HORA_PRESCRICAO'].dt.date >= start_date) & 
                                      (filtered_df['DATA_HORA_PRESCRICAO'].dt.date <= end_date)]
        elif isinstance(date_selection, pd.Timestamp):
            filtered_df = filtered_df[filtered_df['DATA_HORA_PRESCRICAO'].dt.date == date_selection]

        if selection == 'Total Number of Exams':
            # Total number of exams
            total_exams = filtered_df.shape[0]
            st.write(f'Total number of mammogram exams: {total_exams}')

        elif selection == 'Number of Studies per Day':
            # Line graph of studies (number x day in full date format including day of week)
            line_data = filtered_df['DATA_HORA_PRESCRICAO'].dt.date.value_counts().sort_index()
            if not line_data.empty:
                fig1, ax1 = plt.subplots()
                ax1.plot(line_data.index, line_data.values)
                ax1.set_title('Number of Studies per Day')
                ax1.set_xlabel('Date')
                ax1.set_ylabel('Number of Studies')
                ax1.grid(True)
                st.pyplot(fig1)
            else:
                st.write("No data available for the selected filters.")

        elif selection == 'SLA Compliance':
            # Pie chart of SLA (inside SLA time or outside)
            sla_counts = filtered_df['SLA_MET'].value_counts()
            if not sla_counts.empty:
                fig2, ax2 = plt.subplots()
                ax2.pie(sla_counts, labels=['Within SLA', 'Outside SLA'], autopct='%1.1f%%', startangle=90)
                ax2.set_title('SLA Compliance')
                st.pyplot(fig2)
            else:
                st.write("No data available for the selected filters.")

        elif selection == 'SLA Compliance Over Time':
            # SLA compliance over time
            sla_over_time = filtered_df.groupby(filtered_df['DATA_HORA_PRESCRICAO'].dt.date)['SLA_MET'].mean()
            if not sla_over_time.empty:
                fig3, ax3 = plt.subplots()
                ax3.plot(sla_over_time.index, sla_over_time.values, marker='o')
                ax3.set_title('SLA Compliance Over Time')
                ax3.set_xlabel('Date')
                ax3.set_ylabel('SLA Compliance Rate')
                ax3.grid(True)
                st.pyplot(fig3)
            else:
                st.write("No data available for the selected filters.")

        elif selection == 'Number of Exams per Unidade':
            # Number of exams per Unidade
            exams_per_unidade = mamografia_df['UNIDADE'].value_counts()
            if not exams_per_unidade.empty:
                fig4, ax4 = plt.subplots()
                ax4.bar(exams_per_unidade.index, exams_per_unidade.values)
                ax4.set_title('Number of Exams per Unidade')
                ax4.set_xlabel('Unidade')
                ax4.set_ylabel('Number of Exams')
                ax4.tick_params(axis='x', rotation=45)
                st.pyplot(fig4)
            else:
                st.write("No data available for the selected filters.")

        elif selection == 'Count by Medico Laudo Definitivo':
            # Drop-down to select "MEDICO_LAUDO_DEFINITIVO" and count events based on filtered data
            medico_selected = st.sidebar.selectbox('Select Medico Laudo Definitivo', filtered_df['MEDICO_LAUDO_DEFINITIVO'].dropna().unique())
            medico_filtered_df = filtered_df[filtered_df['MEDICO_LAUDO_DEFINITIVO'] == medico_selected]
            total_by_medico = medico_filtered_df.shape[0]
            st.write(f'Total number of exams by {medico_selected}: {total_by_medico}')

        elif selection == 'Exams Without Report':
            # Total number of mammogram exams without a report (STATUS_APROVADO is empty)
            missing_report_df = mamografia_df[mamografia_df['STATUS_APROVADO'].isna()]
            total_missing_report = missing_report_df.shape[0]
            st.write(f'Total number of mammogram exams without a report: {total_missing_report}')

            # Display the dataframe of exams without a report
            st.write("Dataframe of mammogram exams without a report:")
            st.dataframe(missing_report_df)

        # Display the filtered dataframe
        st.write("Filtered Data:")
        st.dataframe(filtered_df)
    else:
        st.write("No mammography data found in the uploaded file.")
