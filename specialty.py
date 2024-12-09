import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from PIL import Image

# Load the data
@st.cache_data
def load_logo(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

@st.cache_data
def load_excel_from_github():
    try:
        url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_excel(BytesIO(response.content))
    except requests.exceptions.RequestException:
        return None

# Load and display logo from GitHub
url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
response = requests.get(url)
logo = Image.open(BytesIO(response.content))
st.sidebar.image(logo, use_column_width=True)

df = load_excel_from_github()

# Streamlit app
def main():
    if df is not None:
        st.title("Exams by Specialty")

        # Sidebar for specialty selection
        st.sidebar.header("Filter by Specialty")
        specialties = df['ESPECIALIDADE'].dropna().unique()
        selected_specialty = st.sidebar.selectbox("Select a Specialty", specialties)

        # Filter data based on selected specialty
        filtered_data = df[df['ESPECIALIDADE'] == selected_specialty]

        # Display filtered exams
        st.header(f"Exams for Specialty: {selected_specialty}")
        if not filtered_data.empty:
            st.write(filtered_data[['DESCRICAO_PROCEDIMENTO']])
        else:
            st.write("No exams found for the selected specialty.")
    else:
        st.error("Data could not be loaded. Please check the source.")

if __name__ == "__main__":
    main()
