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
        # Converter as datas utilizando o formato "dd-mm-yyyy hh:mm"
        df["DATA_HORA_PRESCRICAO"] = pd.to_datetime(
            df["DATA_HORA_PRESCRICAO"], format="%d-%m-%Y %H:%M", errors='coerce'
        )
        if "STATUS_ALAUDAR" in df.columns:
            df["STATUS_ALAUDAR"] = pd.to_datetime(
                df["STATUS_ALAUDAR"], format="%d-%m-%Y %H:%M", errors='coerce'
            )
    return df

df = load_data()

# Filtrar somente os exames externos
df = df[df["TIPO_ATENDIMENTO"] == "Externo"]

# Sidebar - Filtros

# Filtro de unidade
unidades = df["UNIDADE"].dropna().unique()
unidade_selecionada = st.sidebar.selectbox("Selecione a unidade:", unidades)
df = df[df["UNIDADE"] == unidade_selecionada]

# Converter STATUS_ALAUDAR para período mensal (mês/ano)
df["MES"] = df["STATUS_ALAUDAR"].dt.to_period("M")

# Dicionário para mapear o número do mês para o nome em português
meses_portugues = {
    1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
    5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
    9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
}

# Cria a lista de períodos disponíveis e ordena
meses_disponiveis = sorted(df["MES"].dropna().unique())

# Selectbox para selecionar o mês/ano com o formato "NOME_DO_MÊS/AA"
mes_selecionado = st.sidebar.selectbox(
    "Selecione o mês/ano:",
    meses_disponiveis,
    format_func=lambda p: f"{meses_portugues[p.month]}/{str(p.year)[-2:]}"
)

# Filtrar os dados pelo mês/ano selecionado
df = df[df["MES"] == mes_selecionado]

# Filtro de médico (após filtrar por mês/ano)
medicos = df["MEDICO_SOLICITANTE"].dropna().unique()
medico_selecionado = st.sidebar.selectbox("Selecione o médico:", medicos)

# Dados filtrados
df_medico = df[df["MEDICO_SOLICITANTE"] == medico_selecionado]

# Exibição de dados em abas
tab1, tab2 = st.tabs(["Análise por Médico", "Top 10 Médicos Prescritores de RM"])

with tab1:
    st.header(f"Exames de {medico_selecionado}")
    # Preparar o DataFrame para exibição formatando as datas para dd/mm/yyyy
    df_display = df_medico.copy()
    df_display["DATA_HORA_PRESCRICAO"] = df_display["DATA_HORA_PRESCRICAO"].dt.strftime("%d/%m/%Y")
    df_display["STATUS_ALAUDAR"] = df_display["STATUS_ALAUDAR"].dt.strftime("%d/%m/%Y")
    st.dataframe(df_display[["NOME_PACIENTE", "DATA_HORA_PRESCRICAO", "STATUS_ALAUDAR", "DESCRICAO_PROCEDIMENTO"]])
    
    st.subheader("Exames por Modalidade")
    modalidades = df_medico["MODALIDADE"].dropna().unique()
    
    for mod in modalidades:
        st.markdown(f"### Modalidade: {mod}")
        df_mod = df_medico[df_medico["MODALIDADE"] == mod]
        procedimento_counts = df_mod["DESCRICAO_PROCEDIMENTO"].value_counts().reset_index()
        procedimento_counts.columns = ["DESCRICAO_PROCEDIMENTO", "QUANTITATIVO"]
        st.dataframe(procedimento_counts)

with tab2:
    st.header("Top 10 Médicos Prescritores")
    top_medicos = df["MEDICO_SOLICITANTE"].value_counts().head(10)
    st.bar_chart(top_medicos)

    st.header("Top 10 Médicos Prescritores de RM")
    df_rm = df[df["MODALIDADE"].str.contains("MR", case=False, na=False)]
    top_medicos_rm = df_rm["MEDICO_SOLICITANTE"].value_counts().head(10)
    st.bar_chart(top_medicos_rm)
