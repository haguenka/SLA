import logging
import os
import re
import sqlite3
import fitz  # PyMuPDF for PDF manipulation
import pandas as pd
import base64
from io import BytesIO
import streamlit as st

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def sanitize_column_name(column_name):
    sanitized_name = re.sub(r'\W+', '_', column_name)
    return sanitized_name.strip('_')

def initialize_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns = [
        "Nome do Paciente", "Idade", "Sexo", "Contato Telefônico", "SAME", 
        "PDF File", "Data_Exame", "Resposta- Tabagista", "Observação- Tabagista", 
        "Resposta- Enfisema", "Observação- Enfisema", "Resposta- Fibrose", 
        "Observação- Fibrose", "Resposta- Imunossuprimido", "Observação- Imunossuprimido",
        "Resposta- Histórico familiar de câncer", "Observação- Histórico familiar de câncer", 
        "Tamanho:", "Densidade:", "Contorno espiculado/irregular:", "Número de nódulos:", 
        "Localização Lobo superior:"
    ]
    
    create_table_query = f'''
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {', '.join(f'"{col}" TEXT' for col in columns)}
    )
    '''
    cursor.execute(create_table_query)
    conn.commit()
    conn.close()

def extract_patient_info(text):
    output_dict = {}
    patterns = {
        'Nome do Paciente': r'Paciente\s*:\s*(.+)',
        'Data de Nascimento': r'Data\s+de\s+Nascimento\s*:\s*([\d\/]+)',
        'Data_Exame': r'Data\s+do\s+Exame\s*:\s*([\d\/]+)',
        'SAME': r'SAME\s*:\s*(.+)',
        'Idade': r'Idade\s*:\s*(\d+)',
        'Sexo': r'Sexo\s*:\s*(\w+)',
        'Contato Telefônico': r'Contato\s*:\s*(.+)'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            output_dict[key] = match.group(1).strip()
        else:
            logging.warning(f"Pattern for '{key}' not found in text")

    return output_dict

def save_to_database(db_path, data):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    initialize_database(db_path)

    if 'id' in data and data['id']:
        # Update an existing patient
        set_clause = ', '.join(f'"{key}" = ?' for key in data.keys() if key != 'id')
        sql = f'UPDATE patients SET {set_clause} WHERE id = ?'
        values = [str(data[key]) if data[key] is not None else '' for key in data.keys() if key != 'id']
        values.append(data['id'])
    else:
        # Insert new patient
        columns = ', '.join(f'"{key}"' for key in data.keys() if key != 'id')
        placeholders = ', '.join(['?' for _ in data if _ != 'id'])
        sql = f'INSERT INTO patients ({columns}) VALUES ({placeholders})'
        values = [str(data[key]) if data[key] is not None else '' for key in data.keys() if key != 'id']

    cursor.execute(sql, values)
    conn.commit()
    conn.close()

def highlight_phrases_with_conditions(input_folder, output_folder):
    pdf_data = []
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]

    for filename in pdf_files:
        file_path = os.path.join(input_folder, filename)
        try:
            doc = fitz.open(file_path)
            full_text = ""

            for page in doc:
                text = page.get_text("text")
                full_text += text

            patient_info = extract_patient_info(full_text)
            patient_info['PDF File'] = filename
            pdf_data.append(patient_info)

            output_pdf_path = os.path.join(output_folder, filename)
            doc.save(output_pdf_path)

            doc.close()
        except Exception as e:
            logging.error(f"Error processing file {filename}: {str(e)}")

    return pdf_data

# Streamlit Application Interface
st.title("Pulmonary Nodule Program")

# Folder selection for input and output
input_folder = st.text_input("Select the input folder for PDFs")
output_folder = st.text_input("Select the output folder for processed files")

# Process PDFs Button
if st.button("Process PDFs"):
    if input_folder and output_folder:
        pdf_data = highlight_phrases_with_conditions(input_folder, output_folder)
        db_path = os.path.join(output_folder, 'patient_database.sqlite')

        for patient in pdf_data:
            save_to_database(db_path, patient)

        st.success(f"Processed {len(pdf_data)} PDF files.")
        st.write("Processed PDF Data:")
        st.dataframe(pd.DataFrame(pdf_data))

        # Display a download button for the database
        with open(db_path, "rb") as file:
            btn = st.download_button(
                label="Download Patient Database (SQLite)",
                data=file,
                file_name="patient_database.sqlite",
                mime="application/x-sqlite3"
            )
    else:
        st.error("Please specify both input and output folders.")

# View Database Content
if st.button("View Database"):
    if output_folder:
        db_path = os.path.join(output_folder, 'patient_database.sqlite')
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query("SELECT * FROM patients", conn)
            conn.close()

            st.write("Database Contents:")
            st.dataframe(df)
        else:
            st.error("Database not found. Please process PDFs first.")
    else:
        st.error("Please specify the output folder.")

# Remove Duplicates Button
if st.button("Remove Duplicate Patients"):
    if output_folder:
        db_path = os.path.join(output_folder, 'patient_database.sqlite')
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM patients
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM patients
                    GROUP BY SAME
                )
            ''')
            conn.commit()
            conn.close()
            st.success("Duplicate entries removed.")
        else:
            st.error("Database not found. Please process PDFs first.")
    else:
        st.error("Please specify the output folder.")