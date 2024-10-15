import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar

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

    # Create a classic calendar view to display doctor names on respective days
    st.write("### Classic Calendar View")
    month = st.selectbox("Select Month", range(1, 13))
    year = st.selectbox("Select Year", range(date.today().year, date.today().year + 5))
    df['Start Date'] = pd.to_datetime(df['Start Date'])
    df['End Date'] = pd.to_datetime(df['End Date'])

    # Initialize calendar grid
    cal = calendar.monthcalendar(year, month)
    calendar_display = [['' for _ in range(7)] for _ in range(len(cal))]

    # Populate calendar with doctor names
    for _, row in df.iterrows():
        start_date = row['Start Date']
        end_date = row['End Date']
        current_date = start_date
        while current_date <= end_date:
            if current_date.year == year and current_date.month == month:
                week_idx = (current_date.day - 1) // 7
                day_idx = (current_date.weekday() + 1) % 7
                if calendar_display[week_idx][day_idx] == '':
                    calendar_display[week_idx][day_idx] = row['Doctor']
                else:
                    calendar_display[week_idx][day_idx] += f", {row['Doctor']}"
            current_date += timedelta(days=1)

    # Display the calendar
    st.write(f"### {calendar.month_name[month]} {year}")
    st.markdown("| Sun | Mon | Tue | Wed | Thu | Fri | Sat |")
    st.markdown("| --- | --- | --- | --- | --- | --- | --- |")
    for week in cal:
        week_str = "| "
        for day in week:
            if day == 0:
                week_str += "     | "
            else:
                week_idx = (day - 1) // 7
                day_idx = (calendar.weekday(year, month, day) + 1) % 7
                doctor_str = calendar_display[week_idx][day_idx]
                week_str += f"{day} {doctor_str if doctor_str else ''} | "
        st.markdown(week_str)
else:
    st.write("No vacancy periods added yet.")
