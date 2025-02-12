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
st.title("Rastreador de Cálculo Renal CSSJ")
if logo is not None:
    st.sidebar.image(logo, use_container_width=True)
st.sidebar.header("Selecione os Arquivos")

# Função para carregar os dados do repositório Git
def load_data():
    xlsx_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
    df = load_excel_data(xlsx_url)
    if df is not None:
        df["DATA_HORA_PRESCRICAO"] = pd.to_datetime(df["DATA_HORA_PRESCRICAO"], errors='coerce')
    return df

df = load_data()

# Sidebar - Filtros
st.sidebar.header("Filtros")

# Filtro de unidade
unidades = df["UNIDADE"].dropna().unique()
unidade_selecionada = st.sidebar.selectbox("Selecione a unidade:", unidades)

# Filtro de mês
df = df[df["UNIDADE"] == unidade_selecionada]
df["MES"] = df["DATA_HORA_PRESCRICAO"].dt.to_period("M")
meses_disponiveis = df["MES"].dropna().unique()
mes_selecionado = st.sidebar.selectbox("Selecione o mês:", meses_disponiveis)

# Filtro de médico
df_filtrado = df[df["MES"] == mes_selecionado]
medicos = df_filtrado["MEDICO_LAUDO_DEFINITIVO"].dropna().unique()
medico_selecionado = st.sidebar.selectbox("Selecione o médico:", medicos)

# Dados filtrados
df_medico = df_filtrado[df_filtrado["MEDICO_LAUDO_DEFINITIVO"] == medico_selecionado]

# Exibição de dados
tab1, tab2 = st.tabs(["Análise por Médico", "Top 10 Prescritores"])

with tab1:
    st.header(f"Exames de {medico_selecionado}")
    st.dataframe(df_medico[["NOME_PACIENTE", "DATA_HORA_PRESCRICAO", "DESCRICAO_PROCEDIMENTO"]])
    
    # Contagem por modalidade
    st.subheader("Quantidade de Exames por Modalidade")
    modalidade_counts = df_medico["MODALIDADE"].value_counts()
    st.bar_chart(modalidade_counts)

with tab2:
    st.header("Top 10 Médicos Prescritores")
    top_medicos = df_filtrado["MEDICO_LAUDO_DEFINITIVO"].value_counts().head(10)
    st.bar_chart(top_medicos)
