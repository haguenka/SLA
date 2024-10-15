import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
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

    # Create a full calendar to display doctor names on respective days
    st.write("### Full Vacancy Calendar View")
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
            current_date += timedelta(days=1)

    calendar_df = pd.DataFrame(calendar_data)
    calendar_df['Date'] = pd.to_datetime(calendar_df['Date'])

    # Create a calendar grid
    st.write("### Monthly Calendar View")
    month = st.selectbox("Select Month", list(calendar_df['Date'].dt.month.unique()))
    year = st.selectbox("Select Year", list(calendar_df['Date'].dt.year.unique()))
    filtered_calendar_df = calendar_df[(calendar_df['Date'].dt.month == month) & (calendar_df['Date'].dt.year == year)]

    month_calendar = calendar.monthcalendar(year, month)
    fig = go.Figure()

    for week in month_calendar:
        for day in week:
            if day != 0:
                day_date = date(year, month, day)
                day_data = filtered_calendar_df[filtered_calendar_df['Date'] == day_date]
                doctors = ', '.join(day_data['Doctor'].unique()) if not day_data.empty else ''
                fig.add_trace(go.Scatter(
                    x=[day],
                    y=[week.index(day)],
                    mode='markers+text',
                    text=[doctors],
                    textposition='top center',
                    marker=dict(size=15),
                    name=f"Day {day}"
                ))

    fig.update_layout(
        title='Doctor Vacancy Calendar',
        xaxis_title='Day of Month',
        yaxis_title='Week',
        xaxis=dict(tickmode='array', tickvals=list(range(1, 32))),
        yaxis=dict(tickmode='array', tickvals=list(range(0, len(month_calendar))))
    )

    st.plotly_chart(fig)
else:
    st.write("No vacancy periods added yet.")
