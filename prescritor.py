import streamlit as st
import pandas as pd
import requests
from PIL import Image
from io import BytesIO

# Função para carregar o logo via URL com cache
@st.cache_data(show_spinner=False)
def load_logo(url):
    response = requests.get(url)
    if response.status_code == 200:
        return Image.open(BytesIO(response.content))
    else:
        return None

# Função para carregar o arquivo Excel via URL com cache
@st.cache_data(show_spinner=False)
def load_excel_data(xlsx_url):
    response = requests.get(xlsx_url)
    if response.status_code == 200:
        return pd.read_excel(BytesIO(response.content))
    else:
        st.error("Não foi possível carregar o arquivo Excel da URL fornecida.")
        return None

# URL do logo
url_logo = 'https://raw.githubusercontent.com/haguenka/SLA/main/sj.png'
logo = load_logo(url_logo)

# -------------------------------
# CONFIGURAÇÃO DE CSS (DARK MODE)
# -------------------------------
st.markdown("""
    <style>
    /* Estilo para o corpo (modo escuro) */
    body {
        background-color: #121212;
        color: #ffffff;
    }
    /* Estilo para a sidebar */
    .css-1d391kg, .css-1d391kg div {
        background-color: #1e1e1e;
    }
    /* Ajuste de fonte e espaçamento para um visual clean/fancy */
    .reportview-container .main .block-container{
        padding-top: 2rem;
        padding-right: 2rem;
        padding-left: 2rem;
        padding-bottom: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

# -------------------------------
# TÍTULO E LOGO NA SIDEBAR
# -------------------------------
st.title("Análise CDI - Médico Prescritor")
if logo is not None:
    st.sidebar.image(logo, use_container_width=True)
st.sidebar.header("Selecione os filtros")

# Função para carregar os dados do repositório Git
def load_data():
    xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
    df = load_excel_data(xlsx_url)
    if df is not None:
        # Converter as datas com dayfirst=True para interpretar corretamente o formato (dia/mês/ano)
        df["DATA_HORA_PRESCRICAO"] = pd.to_datetime(df["DATA_HORA_PRESCRICAO"], errors='coerce', dayfirst=True)
        if "STATUS_ALAUDAR" in df.columns:
            df["STATUS_ALAUDAR"] = pd.to_datetime(df["STATUS_ALAUDAR"], errors='coerce', dayfirst=True)
    return df

df = load_data()

# Filtrar somente os exames externos
df = df[df["TIPO_ATENDIMENTO"] == "Externo"]

# Sidebar - Filtros

# Filtro de unidade
unidades = df["UNIDADE"].dropna().unique()
unidade_selecionada = st.sidebar.selectbox("Selecione a unidade:", unidades)

# Filtrar por unidade
df = df[df["UNIDADE"] == unidade_selecionada]

# Filtro de período específico utilizando STATUS_ALAUDAR
if df["STATUS_ALAUDAR"].notnull().any():
    min_date = df["STATUS_ALAUDAR"].min().date()
    max_date = df["STATUS_ALAUDAR"].max().date()
    periodo = st.sidebar.date_input("Selecione o período:", [min_date, max_date])
    # Verifica se o usuário selecionou duas datas
    if isinstance(periodo, list) and len(periodo) == 2:
        start_date, end_date = periodo
        df = df[(df["STATUS_ALAUDAR"].dt.date >= start_date) & (df["STATUS_ALAUDAR"].dt.date <= end_date)]
else:
    st.sidebar.warning("A coluna STATUS_ALAUDAR não possui datas válidas.")

# Filtro de médico (após filtrar por período)
medicos = df["MEDICO_SOLICITANTE"].dropna().unique()
medico_selecionado = st.sidebar.selectbox("Selecione o médico:", medicos)

# Dados filtrados
df_medico = df[df["MEDICO_SOLICITANTE"] == medico_selecionado]

# Exibição de dados em abas
tab1, tab2 = st.tabs(["Análise por Médico", "Top 10 Médicos Prescritores de RM"])

with tab1:
    st.header(f"Exames de {medico_selecionado}")
    # Criar uma cópia para formatar as datas
    df_display = df_medico.copy()
    # Formatar as datas para o formato dd/mm/yyyy
    df_display["DATA_HORA_PRESCRICAO"] = df_display["DATA_HORA_PRESCRICAO"].dt.strftime("%d/%m/%Y")
    df_display["STATUS_ALAUDAR"] = df_display["STATUS_ALAUDAR"].dt.strftime("%d/%m/%Y")
    st.dataframe(df_display[["NOME_PACIENTE", "DATA_HORA_PRESCRICAO", "STATUS_ALAUDAR", "DESCRICAO_PROCEDIMENTO"]])
    
    # Exibição dos exames por modalidade com DataFrame para cada modalidade
    st.subheader("Exames por Modalidade")
    modalidades = df_medico["MODALIDADE"].dropna().unique()
    
    for mod in modalidades:
        st.markdown(f"### Modalidade: {mod}")
        df_mod = df_medico[df_medico["MODALIDADE"] == mod]
        # Contagem dos procedimentos para a modalidade atual
        procedimento_counts = df_mod["DESCRICAO_PROCEDIMENTO"].value_counts().reset_index()
        procedimento_counts.columns = ["DESCRICAO_PROCEDIMENTO", "QUANTITATIVO"]
        st.dataframe(procedimento_counts)

with tab2:
    st.header("Top 10 Médicos Prescritores")
    top_medicos = df["MEDICO_SOLICITANTE"].value_counts().head(10)
    st.bar_chart(top_medicos)

    st.header("Top 10 Médicos Prescritores de RM")
    # Filtrar registros cuja coluna MODALIDADE contenha "RM"
    df_rm = df[df["MODALIDADE"].str.contains("RM", case=False, na=False)]
    top_medicos_rm = df_rm["MEDICO_SOLICITANTE"].value_counts().head(10)
    st.bar_chart(top_medicos_rm)
