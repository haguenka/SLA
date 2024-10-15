import streamlit as st
import pandas as pd
from datetime import date

# Data structure to hold doctor's vacancy periods
if 'vacancy_data' not in st.session_state:
    st.session_state['vacancy_data'] = []

st.title("Doctor's Vacancy Period Management")

# Dropdown menu for selecting doctor
doctor_names = ["Dr. Smith", "Dr. Johnson", "Dr. Lee", "Dr. Brown"]
selected_doctor = st.selectbox("Select Doctor", doctor_names)

# Date input for selecting vacancy period
vacancy_start = st.date_input("Select Vacancy Start Date", min_value=date.today())
vacancy_end = st.date_input("Select Vacancy End Date", min_value=vacancy_start)

# Button to confirm selection
if st.button("Add Vacancy Period"):
    st.session_state['vacancy_data'].append({
        'Doctor': selected_doctor,
        'Start Date': vacancy_start,
        'End Date': vacancy_end
    })
    st.success(f"Vacancy period added for {selected_doctor} from {vacancy_start} to {vacancy_end}")

# Display the vacancy periods
if st.session_state['vacancy_data']:
    df = pd.DataFrame(st.session_state['vacancy_data'])
    st.write("### Current Vacancy Periods")
    st.dataframe(df)
else:
    st.write("No vacancy periods added yet.")
