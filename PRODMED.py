import streamlit as st
import pandas as pd

# Load data from the Excel file
def load_data(uploaded_file):
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, sheet_name='Sheet1')
        return df
    return None

# Streamlit App
st.title('Event Counter for MEDICO_LAUDO_DEFINITIVO')

# File Upload
uploaded_file = st.sidebar.file_uploader("Choose an Excel file", type=["xlsx"])

# Load data
if uploaded_file is not None:
    data = load_data(uploaded_file)

    # Sidebar Filters
    st.sidebar.header('Filters')

    # Date Range Filter
    data['DATA_LAUDO'] = pd.to_datetime(data['DATA_LAUDO'], errors='coerce')
    start_date = st.sidebar.date_input('Start Date', min_value=data['DATA_LAUDO'].min(), max_value=data['DATA_LAUDO'].max())
    end_date = st.sidebar.date_input('End Date', min_value=data['DATA_LAUDO'].min(), max_value=data['DATA_LAUDO'].max())

    # Filter data by date range
    filtered_data = data[(data['DATA_LAUDO'] >= pd.to_datetime(start_date)) & (data['DATA_LAUDO'] <= pd.to_datetime(end_date))]

    # Get unique doctor names and let the user select
    doctors = filtered_data['MEDICO_LAUDO_DEFINITIVO'].dropna().unique()
    selected_doctor = st.sidebar.selectbox('Select a Doctor', doctors)

    # Filter data by selected doctor
    doctor_data = filtered_data[filtered_data['MEDICO_LAUDO_DEFINITIVO'] == selected_doctor]

    # Create a dataframe with "DESCRICAO_PROCEDIMENTO" and count events
    procedure_counts = doctor_data['DESCRICAO_PROCEDIMENTO'].value_counts().reset_index()
    procedure_counts.columns = ['DESCRICAO_PROCEDIMENTO', 'Count']

    # Display the dataframe
    st.write(f"Procedures for Dr. {selected_doctor}")
    st.dataframe(procedure_counts)
else:
    st.write("Please upload an Excel file to proceed.")
