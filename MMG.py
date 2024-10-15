import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd

# File uploader to select the dataset
st.title('Breast Cancer Prevention Mammogram Program Dashboard')
file = st.file_uploader('Upload Excel File', type=['xlsx'])

if file is not None:
    # Load the dataset
    df = pd.read_excel(file, 'Sheet1')

    # Filter relevant rows and columns
    mamografia_df = df[df['DESCRICAO_PROCEDIMENTO'].str.contains('MAMOGRAFIA', na=False)]
    mamografia_df = mamografia_df[mamografia_df['MEDICO_SOLICITANTE'].isin(['MARCELO JACOBINA DE ABREU', 'HENRIQUE ARUME GUENKA'])]

    # Convert date columns to datetime
    mamografia_df['DATA_HORA_PRESCRICAO'] = pd.to_datetime(mamografia_df['DATA_HORA_PRESCRICAO'], errors='coerce')
    mamografia_df['STATUS_APROVADO'] = pd.to_datetime(mamografia_df['STATUS_APROVADO'], errors='coerce')

    # Filter out invalid dates
    mamografia_df = mamografia_df.dropna(subset=['DATA_HORA_PRESCRICAO', 'STATUS_APROVADO'])

    # Calculate SLA timing (5 days)
    mamografia_df['SLA_MET'] = (mamografia_df['STATUS_APROVADO'] - mamografia_df['DATA_HORA_PRESCRICAO']).dt.days <= 5

    # Drop-down selection for "UNIDADE" and specific date/period selection
    unidade_selected = st.selectbox('Select Unidade', mamografia_df['UNIDADE'].unique())
    date_selection = st.date_input('Select a specific day or period of time', [])

    filtered_df = mamografia_df[mamografia_df['UNIDADE'] == unidade_selected]

    if date_selection:
        if isinstance(date_selection, list) and len(date_selection) == 2:
            filtered_df = filtered_df[(filtered_df['DATA_HORA_PRESCRICAO'].dt.date >= date_selection[0]) & 
                                      (filtered_df['DATA_HORA_PRESCRICAO'].dt.date <= date_selection[1])]
        else:
            filtered_df = filtered_df[filtered_df['DATA_HORA_PRESCRICAO'].dt.date == date_selection]

    # Total number of exams
    total_exams = filtered_df.shape[0]
    st.write(f'Total number of mammogram exams: {total_exams}')

    # Line graph of studies (number x day in full date format including day of week)
    line_data = filtered_df['DATA_HORA_PRESCRICAO'].dt.date.value_counts().sort_index()
    fig1, ax1 = plt.subplots()
    ax1.plot(line_data.index, line_data.values)
    ax1.set_title('Number of Studies per Day')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Number of Studies')
    ax1.grid(True)
    st.pyplot(fig1)

    # Pie chart of SLA (inside SLA time or outside)
    sla_counts = filtered_df['SLA_MET'].value_counts()
    fig2, ax2 = plt.subplots()
    ax2.pie(sla_counts, labels=['Within SLA', 'Outside SLA'], autopct='%1.1f%%', startangle=90)
    ax2.set_title('SLA Compliance')
    st.pyplot(fig2)

    # Drop-down to select "MEDICO_LAUDO_DEFINITIVO" and correlate with number of exams on selected date
    doctor_selected = st.selectbox('Select Doctor', filtered_df['MEDICO_LAUDO_DEFINITIVO'].dropna().unique())
    doctor_filtered_df = filtered_df[filtered_df['MEDICO_LAUDO_DEFINITIVO'] == doctor_selected]

    st.write(f'Number of exams by Dr. {doctor_selected}: {doctor_filtered_df.shape[0]}')

    # Additional feature: SLA compliance over time
    st.subheader('SLA Compliance Over Time')
    sla_over_time = filtered_df.groupby(filtered_df['DATA_HORA_PRESCRICAO'].dt.date)['SLA_MET'].mean()
    fig3, ax3 = plt.subplots()
    ax3.plot(sla_over_time.index, sla_over_time.values, marker='o')
    ax3.set_title('SLA Compliance Over Time')
    ax3.set_xlabel('Date')
    ax3.set_ylabel('SLA Compliance Rate')
    ax3.grid(True)
    st.pyplot(fig3)

    # Additional feature: Number of exams per Unidade
    st.subheader('Number of Exams per Unidade')
    exams_per_unidade = mamografia_df['UNIDADE'].value_counts()
    fig4, ax4 = plt.subplots()
    ax4.bar(exams_per_unidade.index, exams_per_unidade.values)
    ax4.set_title('Number of Exams per Unidade')
    ax4.set_xlabel('Unidade')
    ax4.set_ylabel('Number of Exams')
    ax4.tick_params(axis='x', rotation=45)
    st.pyplot(fig4)
