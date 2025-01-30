import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import requests
from io import BytesIO
import numpy as np
import os
import re

# Bibliotecas adicionais para PDF e fuzzy matching
import pdfplumber
from thefuzz import process, fuzz

# =====================================
# FUNÇÕES PARA CARREGAR DADOS
# =====================================

@st.cache_data
def load_logo(url):
    """Baixa uma imagem (logo) a partir de uma URL e a carrega como objeto PIL."""
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

@st.cache_data
def load_excel(file):
    """Carrega um arquivo Excel em um DataFrame."""
    return pd.read_excel(file)

@st.cache_data
def load_excel_from_github():
    """
    Tenta carregar a planilha Excel diretamente do GitHub.
    Se não der certo, retorna None.
    """
    try:
        url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_excel(BytesIO(response.content))
    except requests.exceptions.RequestException:
        return None

@st.cache_data
def load_pdf_from_github():
    """
    Tenta carregar o PDF (lista.pdf) diretamente do GitHub.
    Ajuste a URL conforme necessário.
    Retorna um DataFrame com colunas 'Data' e 'Paciente'.
    """
    url_pdf = "https://raw.githubusercontent.com/haguenka/SLA/main/lista.pdf"  # Ajuste a URL
    try:
        response = requests.get(url_pdf)
        response.raise_for_status()
        pdf_bytes = BytesIO(response.content)

        rows = []
        with pdfplumber.open(pdf_bytes) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    headers = table[0]  # Exemplo: ['Data', 'Paciente', ...]
                    data_rows = table[1:]
                    for row in data_rows:
                        # Ajuste o índice conforme a estrutura do seu PDF
                        data_atendimento = row[0]
                        paciente_nome = row[1]
                        rows.append({
                            'Data': data_atendimento,
                            'Paciente': paciente_nome
                        })
        df_pdf = pd.DataFrame(rows)
        return df_pdf
    except requests.exceptions.RequestException:
        return None

def match_patient_names(pdf_df, excel_df, col_paciente_excel='PACIENTE', col_convenio='CONVENIO', threshold=80):
    """
    Faz a correspondência aproximada entre o nome do paciente (no PDF) e o nome do paciente (no Excel).
    Se a similaridade for >= threshold, copia as informações de 'CONVENIO' e 'MEDICO_SOLICITANTE' do Excel.
    """
    # Normaliza as strings para minúsculas (e, se quiser, remover acentos).
    pdf_df['Paciente_norm'] = pdf_df['Paciente'].astype(str).str.lower().fillna('')
    excel_df['Paciente_norm'] = excel_df[col_paciente_excel].astype(str).str.lower().fillna('')

    # Cria colunas vazias no PDF para popular
    pdf_df['CONVENIO'] = None
    pdf_df['MEDICO_SOLICITANTE'] = None

    # Lista de nomes únicos no Excel (normalizados)
    excel_names = excel_df['Paciente_norm'].unique().tolist()

    # Para cada paciente do PDF, busca o melhor match no Excel
    for i, row in pdf_df.iterrows():
        nome_pdf = row['Paciente_norm']
        best_match, score = process.extractOne(nome_pdf, excel_names, scorer=fuzz.ratio)
        if best_match and score >= threshold:
            # Filtra a(s) linha(s) correspondente(s) no Excel
            matched_excel_rows = excel_df[excel_df['Paciente_norm'] == best_match]
            if not matched_excel_rows.empty:
                matched_row = matched_excel_rows.iloc[0]
                pdf_df.at[i, 'CONVENIO'] = matched_row[col_convenio]
                pdf_df.at[i, 'MEDICO_SOLICITANTE'] = matched_row['MEDICO_SOLICITANTE']

    # Remove colunas auxiliares usadas para normalização
    pdf_df.drop(columns=['Paciente_norm'], inplace=True, errors='ignore')
    excel_df.drop(columns=['Paciente_norm'], inplace=True, errors='ignore')

    return pdf_df

# =====================================
# FUNÇÃO PRINCIPAL
# =====================================
def main():
    st.title("Análise IBAM com Correlação de PDF (via GitHub)")

    # Carrega e exibe logo
    url_logo = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
    logo = load_logo(url_logo)
    st.sidebar.image(logo, use_container_width=True)

    # Carrega Excel do GitHub
    df = load_excel_from_github()
    if df is None:
        st.error("Não foi possível carregar o Excel do GitHub. Verifique a URL ou o arquivo.")
        return

    # Verifica colunas mínimas
    required_cols = ['MEDICO_SOLICITANTE', 'UNIDADE', 'TIPO_ATENDIMENTO']
    for col in required_cols:
        if col not in df.columns:
            st.error(f"Coluna obrigatória '{col}' não encontrada no Excel.")
            return

    # Verifica se existem PACIENTE e CONVENIO para correlação
    if 'PACIENTE' not in df.columns or 'CONVENIO' not in df.columns:
        st.warning("O DataFrame Excel não possui colunas 'PACIENTE' ou 'CONVENIO'. "
                   "A correlação com PDF que adiciona convênio pode não funcionar corretamente.")

    # Padroniza
    df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].astype(str).str.strip().str.lower()

    # Remove NaN essenciais
    df = df.dropna(subset=['MEDICO_SOLICITANTE', 'UNIDADE', 'TIPO_ATENDIMENTO'])

    # Filtra grupos
    allowed_groups = [
        'GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA',
        'GRUPO RAIO-X', 'GRUPO MAMOGRAFIA',
        'GRUPO MEDICINA NUCLEAR', 'GRUPO ULTRASSOM'
    ]
    if 'GRUPO' in df.columns:
        df = df[df['GRUPO'].isin(allowed_groups)]

    # Converte colunas para datetime
    for col_dt in ['STATUS_ALAUDAR', 'STATUS_PRELIMINAR', 'STATUS_APROVADO']:
        if col_dt in df.columns:
            df[col_dt] = pd.to_datetime(df[col_dt], dayfirst=True, errors='coerce')

    # Remove linhas sem STATUS_PRELIMINAR e STATUS_APROVADO
    if 'STATUS_PRELIMINAR' in df.columns and 'STATUS_APROVADO' in df.columns:
        df = df.dropna(subset=['STATUS_PRELIMINAR', 'STATUS_APROVADO'], how='all')

    # SIDEBAR - Filtros
    unidade = st.sidebar.selectbox("Selecione a Unidade", options=df['UNIDADE'].dropna().unique())
    date_range = st.sidebar.date_input("Selecione o Período (STATUS_ALAUDAR)", [])
    tipo_atendimento = st.sidebar.selectbox("Selecione o Tipo de Atendimento", options=df['TIPO_ATENDIMENTO'].dropna().unique())

    # Aplica filtros
    filtered_df = df[(df['UNIDADE'] == unidade) & (df['TIPO_ATENDIMENTO'] == tipo_atendimento)]
    if date_range and len(date_range) == 2:
        start_date, end_date = date_range
        if 'STATUS_ALAUDAR' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df['STATUS_ALAUDAR'] >= pd.to_datetime(start_date)) &
                (filtered_df['STATUS_ALAUDAR'] <= pd.to_datetime(end_date))
            ]

    # Mostra dados filtrados do Excel
    st.subheader("Dados Filtrados do Excel")
    st.dataframe(filtered_df)

    # Cálculo dos top 10 médicos
    top_doctors = filtered_df['MEDICO_SOLICITANTE'].value_counts().head(10)

    # Contar exames por médico (para top 10)
    if 'GRUPO' in filtered_df.columns:
        top_doctor_exam_counts = (
            filtered_df[filtered_df['MEDICO_SOLICITANTE'].isin(top_doctors.index)]
            .groupby(['MEDICO_SOLICITANTE', 'GRUPO'])
            .size()
            .unstack(fill_value=0)
        )
        group_totals = top_doctor_exam_counts.sum().rename('Total')
        top_doctor_exam_counts = pd.concat([top_doctor_exam_counts, group_totals.to_frame().T])

        st.subheader("Contagem de Exames por Médico (Top 10)")
        st.dataframe(top_doctor_exam_counts)

    # Gráfico Top 10
    if not top_doctors.empty:
        st.subheader("Top 10 Médicos Solicitantes")
        fig, ax = plt.subplots()
        top_doctors.plot(kind='bar', ax=ax, color='skyblue')
        ax.set_title("Top 10 Médicos Solicitantes")
        ax.set_ylabel("Quantidade de Solicitações")
        ax.set_xlabel("Médicos")
        for i, v in enumerate(top_doctors):
            ax.text(i, v + 0.5, str(v), ha='center', va='bottom', fontsize=10)
        st.pyplot(fig)
    else:
        st.info("Nenhum dado disponível para o filtro selecionado.")

    # =====================================
    # CORRELAÇÃO COM PDF (via GitHub)
    # =====================================
    st.header("Correlação com PDF (Lista de Atendimentos)")

    pdf_df = load_pdf_from_github()
    if pdf_df is None or pdf_df.empty:
        st.error("Não foi possível carregar ou extrair dados do PDF (lista.pdf) do GitHub.")
        return

    # Verifica se a coluna 'Data' e 'Paciente' existem no PDF
    if 'Data' not in pdf_df.columns or 'Paciente' not in pdf_df.columns:
        st.error("O PDF não contém as colunas 'Data' e/ou 'Paciente'. Verifique a extração.")
        st.dataframe(pdf_df.head())
        return

    st.subheader("Dados extraídos do PDF (pré-correlação):")
    st.dataframe(pdf_df.head())

    # Converte e filtra datas no PDF
    pdf_df['Data'] = pd.to_datetime(pdf_df['Data'], dayfirst=True, errors='coerce')
    date_range_pdf = st.date_input("Filtrar Data de Atendimento no PDF", [])
    if len(date_range_pdf) == 2:
        start_pdf, end_pdf = date_range_pdf
        pdf_df = pdf_df[(pdf_df['Data'] >= pd.to_datetime(start_pdf)) & (pdf_df['Data'] <= pd.to_datetime(end_pdf))]

    # Correspondência aproximada de nomes
    st.write("Realizando correspondência de nomes entre PDF e Excel...")
    if 'PACIENTE' in df.columns and 'CONVENIO' in df.columns:
        pdf_df = match_patient_names(pdf_df, df, col_paciente_excel='PACIENTE', col_convenio='CONVENIO', threshold=80)
    else:
        st.warning("Não foi possível correlacionar nomes: Excel não possui 'PACIENTE' e/ou 'CONVENIO'.")

    st.subheader("Dados PDF após correlação (com colunas CONVENIO e MEDICO_SOLICITANTE):")
    st.dataframe(pdf_df)

    # Quantificar por médico, os planos de saúde encontrados
    if 'MEDICO_SOLICITANTE' in pdf_df.columns and 'CONVENIO' in pdf_df.columns:
        summary_df = pdf_df.groupby(['MEDICO_SOLICITANTE', 'CONVENIO']).size().reset_index(name='Quantidade')
        st.subheader("Quantidade de atendimentos por Médico e Convênio (PDF correlacionado)")
        st.dataframe(summary_df)
    else:
        st.warning("As colunas MEDICO_SOLICITANTE e/ou CONVENIO não foram encontradas no DataFrame do PDF.")

if __name__ == "__main__":
    main()
