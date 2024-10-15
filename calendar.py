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
    filtered_calendar_df = df[(df['Start Date'].dt.year == year) & (df['Start Date'].dt.month == month)]

    cal = calendar.TextCalendar(firstweekday=calendar.SUNDAY)
    calendar_output = cal.formatmonth(year, month)

    # Display calendar with doctor names on respective days
    for _, row in filtered_calendar_df.iterrows():
        start_date = row['Start Date']
        end_date = row['End Date']
        current_date = start_date
        while current_date <= end_date:
            if current_date.month == month and current_date.year == year:
                day_str = f"{current_date.day:2}"
                if day_str in calendar_output:
                    calendar_output = calendar_output.replace(day_str, f"{day_str} ({row['Doctor']})")
            current_date += timedelta(days=1)

    st.text(calendar_output)
else:
    st.write("No vacancy periods added yet.")
