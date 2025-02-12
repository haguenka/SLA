import streamlit as st
import pandas as pd

# Carregar os dados
def load_data():
    file_path = "teste.xlsx"
    df = pd.read_excel(file_path, sheet_name="Sheet1")
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
