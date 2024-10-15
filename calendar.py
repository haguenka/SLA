import streamlit as st
import pandas as pd
from datetime import date
import calendar
import datetime
import plotly.graph_objects as go

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

    # Create a modern calendar visualization
    st.write("### Vacancy Calendar View")
    calendar_data = []
    for _, row in df.iterrows():
        start_date = row['Start Date']
        end_date = row['End Date']
        current_date = start_date
        while current_date <= end_date:
            calendar_data.append({
                'Doctor': row['Doctor'],
                'Date': current_date
            })
            current_date += datetime.timedelta(days=1)

    calendar_df = pd.DataFrame(calendar_data)
    calendar_df['Date'] = pd.to_datetime(calendar_df['Date'])
    calendar_df['Day'] = calendar_df['Date'].dt.day
    calendar_df['Month'] = calendar_df['Date'].dt.month_name()

    # Create a calendar-like heatmap
    fig = go.Figure()
    for doctor in calendar_df['Doctor'].unique():
        doctor_data = calendar_df[calendar_df['Doctor'] == doctor]
        fig.add_trace(go.Scatter(
            x=doctor_data['Date'],
            y=[doctor] * len(doctor_data),
            mode='markers',
            marker=dict(size=10),
            name=doctor
        ))

    fig.update_layout(
        title='Doctor Vacancy Calendar',
        xaxis_title='Date',
        yaxis_title='Doctor',
        xaxis=dict(showgrid=True),
        yaxis=dict(categoryorder='total descending')
    )

    st.plotly_chart(fig)
else:
    st.write("No vacancy periods added yet.")
