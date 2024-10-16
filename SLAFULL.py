import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Streamlit app
def main():
    st.title("SLA Analysis Dashboard")

    # File upload
    uploaded_file = st.file_uploader("Upload an Excel file for SLA Analysis", type=['xlsx'])
    if uploaded_file is not None:
        try:
            # Load the Excel file
            df = pd.read_excel(uploaded_file)

            # Filter by GRUPO to include only 'GRUPO TOMOGRAFIA' and 'GRUPO RESSONANCIA MAGNETICA'
            allowed_groups = ['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA']
            df = df[df['GRUPO'].isin(allowed_groups)]

            # Parse the relevant datetime columns explicitly with dayfirst=True
            df['STATUS_ALAUDAR'] = pd.to_datetime(df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')
            df['STATUS_PRELIMINAR'] = pd.to_datetime(df['STATUS_PRELIMINAR'], dayfirst=True, errors='coerce')
            df['STATUS_APROVADO'] = pd.to_datetime(df['STATUS_APROVADO'], dayfirst=True, errors='coerce')

            # Eliminate rows where both STATUS_PRELIMINAR and STATUS_APROVADO are null
            df = df.dropna(subset=['STATUS_PRELIMINAR', 'STATUS_APROVADO'], how='all')

            # Check if 'UNIDADE' and 'TIPO_ATENDIMENTO' exist
            if 'UNIDADE' not in df.columns or 'TIPO_ATENDIMENTO' not in df.columns:
                st.error("'UNIDADE' or 'TIPO_ATENDIMENTO' column not found.")
                return

            # Calculate DELTA_TIME using STATUS_PRELIMINAR if it exists, otherwise use STATUS_APROVADO
            df['DELTA_TIME'] = (df['STATUS_PRELIMINAR'].fillna(df['STATUS_APROVADO']) - df['STATUS_ALAUDAR']).dt.total_seconds() / 3600  # in hours

            # Define the conditions for SLA violations
            conditions = [
                (df['TIPO_ATENDIMENTO'] == 'Pronto Atendimento') & (df['DELTA_TIME'] > 1),
                (df['TIPO_ATENDIMENTO'] == 'Internado') & (df['DELTA_TIME'] > 24),
                (df['TIPO_ATENDIMENTO'] == 'Externo') & (df['DELTA_TIME'] > 72)
            ]

            # Set the default SLA status and apply conditions
            df['SLA_STATUS'] = 'SLA DENTRO DO PERÍODO'
            df.loc[conditions[0], 'SLA_STATUS'] = 'SLA FORA DO PERÍODO'
            df.loc[conditions[1], 'SLA_STATUS'] = 'SLA FORA DO PERÍODO'
            df.loc[conditions[2], 'SLA_STATUS'] = 'SLA FORA DO PERÍODO'

            # Select only relevant columns
            selected_columns = [
                'SAME', 'NOME_PACIENTE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO', 'MEDICO_LAUDO_DEFINITIVO',
                'UNIDADE', 'TIPO_ATENDIMENTO', 'STATUS_ALAUDAR', 'STATUS_PRELIMINAR', 'STATUS_APROVADO', 'DELTA_TIME', 'SLA_STATUS'
            ]

            df_selected = df[selected_columns]

            # Sidebar dropdown for selecting UNIDADE
            unidade_options = df['UNIDADE'].unique()
            selected_unidade = st.sidebar.selectbox("Select UNIDADE", unidade_options)

            # Filter dataframe based on selected UNIDADE
            df_filtered = df_selected[df_selected['UNIDADE'] == selected_unidade]

            # Display the filtered dataframe
            st.dataframe(df_filtered)

            # Generate SLA_STATUS pie chart
            sla_status_counts = df_filtered['SLA_STATUS'].value_counts()
            fig, ax = plt.subplots()
            ax.pie(sla_status_counts, labels=sla_status_counts.index, autopct='%1.1f%%', colors=['lightgreen', 'lightcoral'])
            ax.set_title(f'SLA Status Distribution for {selected_unidade}')

            # Display the pie chart
            st.pyplot(fig)

        except Exception as e:
            st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
