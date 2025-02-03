import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from PIL import ImageEnhance
import requests
from io import BytesIO
import numpy as np
from fuzzywuzzy import fuzz, process

# Streamlit app
@st.cache_data
def load_logo(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

@st.cache_data
def load_excel(file):
    return pd.read_excel(file)

@st.cache_data
def load_excel_from_github(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_excel(BytesIO(response.content))
    except requests.exceptions.RequestException:
        return None

def match_names(patient_name, exam_names):
    match, score = process.extractOne(patient_name, exam_names, scorer=fuzz.token_sort_ratio)
    return match if score >= 70 else None

def highlight_rows(row):
    if pd.notna(row['Destaque']):
        return ['background-color: yellow'] * len(row)
    return [''] * len(row)

def main():
    st.title("Análise IBAM")

    # Criar abas
    tab1, tab2 = st.tabs(["Análise de Exames e Consultas", "Estatísticas Gerais"])

    with tab1:
        # Load and display logo from GitHub
        url_logo = 'https://raw.githubusercontent.com/haguenka/SLA/main/sj.png'
        logo = load_logo(url_logo)
        
        # Convert to RGB and adjust contrast using gamma correction
        enhanced_logo = logo.convert('RGB')
        pixels = np.array(enhanced_logo)  # Convert the image to a numpy array
        
        # Apply gamma correction for enhanced contrast
        gamma = 0.7  # Adjust this value between 0 and 1; lower values increase contrast
        pixels[:, :, 0] = (pixels[:, :, 0] ** gamma) * 80  # Red channel
        pixels[:, :, 1] = (pixels[:, :, 1] ** gamma) * 200  # Green channel
        pixels[:, :, 2] = (pixels[:, :, 2] ** gamma) * 220  # Blue channel
        
        # Optional: Apply color balance enhancement using CLAHE
        enhanced_image = Image.fromarray(pixels)
        enhanced_image = enhanced_image.crop()
        enhanced_image = ImageEnhance.Color(enhanced_image).enhance(0.5)
        final_image = Image.fromarray(np.array(enhanced_image))
        
        st.sidebar.image(final_image, use_container_width=True)
    
        # Load datasets
        url_sla = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
        df = load_excel_from_github(url_sla)
    
        url_lista = 'https://raw.githubusercontent.com/haguenka/SLA/main/lista.xlsx'
        df_consultas = load_excel_from_github(url_lista)
    
        # Verifica se os arquivos foram carregados corretamente
        if df is None or df_consultas is None:
            st.sidebar.header("Carregar arquivo")
            uploaded_file = st.sidebar.file_uploader("Escolher um arquivo Excel", type=['xlsx'])
            if uploaded_file is not None:
                df = load_excel(uploaded_file)
            else:
                st.warning("Nenhum arquivo disponível. Por favor, carregue um arquivo Excel.")
                return
    
        try:
            # Verifica a existência de colunas essenciais
            required_columns = ['MEDICO_SOLICITANTE', 'NOME_PACIENTE', 'SAME', 'STATUS_ALAUDAR', 'UNIDADE', 'TIPO_ATENDIMENTO', 'GRUPO']
            required_columns_consultas = ['Prestador', 'Paciente', 'Data']
    
            if 'Convênio' in df_consultas.columns:
                required_columns_consultas.append('Convênio')
    
            if any(col not in df.columns for col in required_columns):
                st.error(f"Colunas faltando no dataset SLA: {', '.join([col for col in required_columns if col not in df.columns])}")
                return
    
            if any(col not in df_consultas.columns for col in required_columns_consultas):
                st.error(f"Colunas faltando no dataset Consultas: {', '.join([col for col in required_columns_consultas if col not in df_consultas.columns])}")
                return
    
            # Padronizar colunas
            df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].str.strip().str.lower()
            df_consultas['Prestador'] = df_consultas['Prestador'].str.strip().str.lower()
    
            if 'Convênio' in df_consultas.columns:
                df_consultas['Convênio'] = df_consultas['Convênio'].str.strip().str.upper()
    
            # 🔹 **Correção: Converter "STATUS_ALAUDAR" para datetime**
            df['STATUS_ALAUDAR'] = pd.to_datetime(df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['STATUS_ALAUDAR'])  # Remove valores inválidos
            df.rename(columns={'STATUS_ALAUDAR': 'Data'}, inplace=True)
    
            df_consultas['Data'] = pd.to_datetime(df_consultas['Data'], dayfirst=True, errors='coerce')
    
            # Filtragem por período
            unidade = st.sidebar.selectbox("Selecione a Unidade", options=df['UNIDADE'].unique())
            date_range = st.sidebar.date_input("Selecione o Período", [])
    
            filtered_df = df[df['UNIDADE'] == unidade]
    
            if date_range and len(date_range) == 2:
                start_date = pd.to_datetime(date_range[0])  
                end_date = pd.to_datetime(date_range[1])  
                
                # 🔹 **Correção na filtragem de datas**
                filtered_df = filtered_df[(filtered_df['Data'] >= start_date) & (filtered_df['Data'] <= end_date)]
                df_consultas = df_consultas[(df_consultas['Data'] >= start_date) & (df_consultas['Data'] <= end_date)]
    
            if filtered_df.empty:
                st.warning("Nenhum dado disponível para o período selecionado.")
                return
    
            selected_doctor = st.sidebar.selectbox("Selecione o Médico Prescritor", options=filtered_df['MEDICO_SOLICITANTE'].unique())
    
            # 🔹 **Filtrar exames do médico selecionado**
            exames_doctor_df = filtered_df[filtered_df['MEDICO_SOLICITANTE'] == selected_doctor]
    
            # 🔹 **Filtrar consultas do médico selecionado**
            consultas_doctor_df = df_consultas[df_consultas['Prestador'] == selected_doctor] if selected_doctor in df_consultas['Prestador'].values else pd.DataFrame()
    
            # 🔹 **Marcar pacientes encontrados nos exames**
            exam_patients = set(exames_doctor_df['NOME_PACIENTE'].dropna().str.lower())
    
            if not consultas_doctor_df.empty:
                consultas_doctor_df['Destaque'] = consultas_doctor_df['Paciente'].apply(lambda x: match_names(x.lower(), exam_patients))
    
            if not exames_doctor_df.empty:
                exames_doctor_df['Destaque'] = exames_doctor_df['NOME_PACIENTE'].apply(lambda x: match_names(x.lower(), set(consultas_doctor_df['Paciente'].dropna().str.lower())))
    
            # 🔹 **Exibir lista de exames por modalidade separadamente**
            st.subheader(f"Exames por Modalidade - {selected_doctor.capitalize()}")
            if not exames_doctor_df.empty:
                for modalidade in exames_doctor_df['GRUPO'].unique():
                    exames_mod_df = exames_doctor_df[exames_doctor_df['GRUPO'] == modalidade]
                    total_exames = len(exames_mod_df)
                    total_grifados = exames_mod_df['Destaque'].notna().sum()
                    st.subheader(f"{modalidade} - Total: {total_exames} (Grifados: {total_grifados})")
                    st.dataframe(exames_mod_df.style.apply(highlight_rows, axis=1))
            else:
                st.warning("Nenhum exame encontrado para este médico.")
    
            # 🔹 **Exibir lista de consultas destacadas**
            st.subheader(f"Consultas - Total de Pacientes: {len(consultas_doctor_df)}")
            if not consultas_doctor_df.empty:
                st.dataframe(consultas_doctor_df.style.apply(highlight_rows, axis=1))
            else:
                st.warning("Nenhuma consulta encontrada para este médico.")
    
            # 🔹 **Criar lista de convênios atendidos pelo médico**
            if 'Convênio' in df_consultas.columns and not consultas_doctor_df.empty:
                convenio_counts = consultas_doctor_df['Convênio'].value_counts().reset_index()
                convenio_counts.columns = ['Convênio', 'Total de Atendimentos']
                st.subheader(f"Convênios Atendidos - Total: {len(convenio_counts)}")
                st.dataframe(convenio_counts)
            else:
                st.warning("Nenhuma informação de convênio disponível para este médico.")
    
        except Exception as e:
            st.error(f"Ocorreu um erro: {e}")
  
    with tab2:
        st.subheader("Estatísticas Gerais")
        total_consultas = len(df_consultas)
        st.metric("Total de Consultas no Período", total_consultas)
        
        if 'Convênio' in df_consultas.columns:
            st.subheader("Consultas por Convênio")
            convenio_counts = df_consultas['Convênio'].value_counts().reset_index()
            convenio_counts.columns = ['Convênio', 'Quantidade']
            st.dataframe(convenio_counts)
        
        st.subheader("Top 10 Médicos com Mais Consultas")
        doctor_counts = df_consultas['Prestador'].value_counts().head(10)
        fig, ax = plt.subplots()
        doctor_counts.plot(kind='bar', ax=ax)
        ax.set_ylabel("Quantidade de Consultas")
        ax.set_xlabel("Médico")
        st.pyplot(fig)

if __name__ == "__main__":
    main()
