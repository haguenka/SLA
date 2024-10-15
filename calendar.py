import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
import itertools

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

    # Initialize calendar grid for the month
    days_in_month = calendar.monthrange(year, month)[1]
    month_dates = [date(year, month, day) for day in range(1, days_in_month + 1)]

    # Create a dictionary to hold doctor availability per day
    calendar_dict = {day: [] for day in month_dates}

    # Populate the dictionary with doctor names for each day
    for _, row in df.iterrows():
        start_date = row['Start Date']
        end_date = row['End Date']
        current_date = start_date
        while current_date <= end_date:
            if current_date in calendar_dict:
                calendar_dict[current_date].append(row['Doctor'])
            current_date += timedelta(days=1)

    # Display the calendar in a grid format
    st.write(f"### {calendar.month_name[month]} {year}")
    week_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    st.markdown("| " + " | ".join(week_days) + " |")
    st.markdown("|" + " --- |" * 7)

    # Generate calendar weeks
    weeks = calendar.monthcalendar(year, month)
    for week in weeks:
        week_str = "| "
        for day in week:
            if day == 0:
                week_str += "    | "
            else:
                day_date = date(year, month, day)
                doctors = ", ".join(calendar_dict[day_date]) if day_date in calendar_dict else ""
                week_str += f"{day} {doctors} | "
        st.markdown(week_str)
else:
    st.write("No vacancy periods added yet.")
