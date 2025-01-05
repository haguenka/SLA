import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import requests
from io import BytesIO
import numpy as np
import os
import re

# Streamlit app
@st.cache_data
def load_logo(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

@st.cache_data
def load_excel(file):
    return pd.read_excel(file)

@st.cache_data
def load_excel_from_github():
    try:
        url = 'https://raw.githubusercontent.com/haguenka/SLA/main/baseslaM.xlsx'
        response = requests.get(url)
        response.raise_for_status()
        return pd.read_excel(BytesIO(response.content))
    except requests.exceptions.RequestException:
        return None

def main():
    st.title("Análise de SLA Dashboard")

    # Load and display logo from GitHub
    url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
    logo = load_logo(url)
    st.sidebar.image(logo, use_container_width=True)

    # Load Excel file from GitHub if available
    df = load_excel_from_github()

    # File upload if GitHub file is not available
    if df is None:
        st.sidebar.header("Carregar arquivo")
        uploaded_file = st.sidebar.file_uploader("Escolher um arquivo Excel", type=['xlsx'])
        if uploaded_file is not None:
            df = load_excel(uploaded_file)
        else:
            st.warning("Nenhum arquivo disponível. Por favor, carregue um arquivo Excel.")
            return

    try:
        # Verifica a existência de colunas essenciais
        if 'MEDICO_SOLICITANTE' not in df.columns:
            st.error("'MEDICO_SOLICITANTE' column not found in the data.")
            return

        if 'UNIDADE' not in df.columns or 'TIPO_ATENDIMENTO' not in df.columns:
            st.error("'UNIDADE' or 'TIPO_ATENDIMENTO' column not found.")
            return

        # Padroniza 'MEDICO_SOLICITANTE'
        df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].astype(str).str.strip().str.lower()

        # Filtro de grupos
        allowed_groups = [
            'GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA',
            'GRUPO RAIO-X', 'GRUPO MAMOGRAFIA',
            'GRUPO MEDICINA NUCLEAR', 'GRUPO ULTRASSOM'
        ]
        df = df[df['GRUPO'].isin(allowed_groups)]

        # Conversão de colunas em datetime
        df['STATUS_ALAUDAR'] = pd.to_datetime(df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')
        df['STATUS_PRELIMINAR'] = pd.to_datetime(df['STATUS_PRELIMINAR'], dayfirst=True, errors='coerce')
        df['STATUS_APROVADO'] = pd.to_datetime(df['STATUS_APROVADO'], dayfirst=True, errors='coerce')

        # Remove linhas sem STATUS_PRELIMINAR e STATUS_APROVADO (ambos vazios)
        df = df.dropna(subset=['STATUS_PRELIMINAR', 'STATUS_APROVADO'], how='all')

        # Calcula DELTA_TIME (considerando fins de semana ou não)
        df['END_DATE'] = df['STATUS_PRELIMINAR'].fillna(df['STATUS_APROVADO'])
        df['DELTA_TIME'] = df.apply(
            lambda row: (
                np.busday_count(row['STATUS_ALAUDAR'].date(), row['END_DATE'].date()) * 24
            ) + ((row['END_DATE'] - row['STATUS_ALAUDAR']).seconds // 3600)
            if row['TIPO_ATENDIMENTO'] != 'Pronto Atendimento'
               and not pd.isna(row['STATUS_ALAUDAR'])
               and not pd.isna(row['END_DATE'])
            else (row['END_DATE'] - row['STATUS_ALAUDAR']).total_seconds() / 3600,
            axis=1
        )

        # Define condições para SLA fora do período
        doctors_of_interest = ['henrique arume guenka', 'marcelo jacobina de abreu']
        condition_1 = (df['GRUPO'] == 'GRUPO MAMOGRAFIA') & (df['MEDICO_SOLICITANTE'].isin(doctors_of_interest)) & (df['DELTA_TIME'] > (10 * 24))
        condition_2 = (df['GRUPO'] == 'GRUPO MAMOGRAFIA') & (~df['MEDICO_SOLICITANTE'].isin(doctors_of_interest)) & (df['DELTA_TIME'] > 120)
        condition_3 = (df['GRUPO'] == 'GRUPO RAIO-X') & (df['DELTA_TIME'] > 72)
        condition_4 = (df['GRUPO'] == 'GRUPO MEDICINA NUCLEAR') & (df['DELTA_TIME'] > 120)
        condition_5 = (df['TIPO_ATENDIMENTO'] == 'Pronto Atendimento') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 1)
        condition_6 = (df['TIPO_ATENDIMENTO'] == 'Internado') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 24)
        condition_7 = (df['TIPO_ATENDIMENTO'] == 'Externo') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 96)

        # Assinala SLA DENTRO ou FORA
        df['SLA_STATUS'] = 'SLA DENTRO DO PERÍODO'
        df.loc[condition_1 | condition_2 | condition_3 | condition_4 | condition_5 | condition_6 | condition_7,
               'SLA_STATUS'] = 'SLA FORA DO PERÍODO'

        # Coluna de observação (caso não exista)
        if 'OBSERVACAO' not in df.columns:
            df['OBSERVACAO'] = ''

        # ----------------------------------------------------------- #
        # 1) Criação da coluna PERIODO_DIA com base em STATUS_ALAUDAR #
        # ----------------------------------------------------------- #
        def calcular_periodo_dia(dt):
            """
            Retorna 'Manhã', 'Tarde', 'Noite' ou 'Madrugada'
            de acordo com a hora de STATUS_ALAUDAR.
            """
            if pd.isna(dt):
                return None
            hora = dt.hour
            if 0 <= hora < 7:
                return "Madrugada"
            elif 7 <= hora < 13:
                return "Manhã"
            elif 13 <= hora < 19:
                return "Tarde"
            else:  # 19 <= hora < 24
                return "Noite"

        df['PERIODO_DIA'] = df['STATUS_ALAUDAR'].apply(calcular_periodo_dia)

        # Colunas selecionadas
        selected_columns = [
            'SAME', 'NOME_PACIENTE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO',
            'MEDICO_LAUDO_DEFINITIVO', 'UNIDADE', 'TIPO_ATENDIMENTO',
            'STATUS_ALAUDAR', 'STATUS_PRELIMINAR', 'STATUS_APROVADO',
            'MEDICO_SOLICITANTE', 'DELTA_TIME', 'SLA_STATUS', 'OBSERVACAO',
            'PERIODO_DIA'  
        ]

        df_selected = df[selected_columns]

        # ----------------------------------------------------------- #
        # 2) Filtros na barra lateral                                #
        # ----------------------------------------------------------- #
        unidade_options = df['UNIDADE'].unique()
        selected_unidade = st.sidebar.selectbox("Selecione a UNIDADE", sorted(unidade_options))

        grupo_options = df['GRUPO'].unique()
        selected_grupo = st.sidebar.selectbox("Selecione o GRUPO", sorted(grupo_options))

        tipo_atendimento_options = df['TIPO_ATENDIMENTO'].unique()
        selected_tipo_atendimento = st.sidebar.selectbox("Selecione o Tipo de Atendimento", sorted(tipo_atendimento_options))

        min_date = df['STATUS_ALAUDAR'].min()
        max_date = df['STATUS_ALAUDAR'].max()
        start_date, end_date = st.sidebar.date_input("Selecione o periodo", [min_date, max_date])

        # ----------------------------------------------------------- #
        # 3) Filtro do DataFrame principal                           #
        # ----------------------------------------------------------- #
        df_filtered = df_selected[
            (df_selected['UNIDADE'] == selected_unidade) &
            (df_selected['GRUPO'] == selected_grupo) &
            (df_selected['TIPO_ATENDIMENTO'] == selected_tipo_atendimento) &
            (df_selected['STATUS_ALAUDAR'] >= pd.Timestamp(start_date)) &
            (df_selected['STATUS_ALAUDAR'] <= pd.Timestamp(end_date))
        ]

        # Exibe o 1º DataFrame (todos os registros filtrados)
        st.dataframe(df_filtered)

        # Exibição do total de exames
        total_exams = len(df_filtered)
        st.write(f"Total number of exams: {total_exams}")

        # ----------------------------------------------------------- #
        # 4) Somente SLA FORA e ordenado pelo PERIODO_DIA            #
        # ----------------------------------------------------------- #
        # Filtra os registros FORA DO PERÍODO
        df_fora = df_filtered[df_filtered['SLA_STATUS'] == 'SLA FORA DO PERÍODO'].copy()

        # Dicionário para ordenação personalizada
        periodo_order = {
            "Madrugada": 1,
            "Manhã": 2,
            "Tarde": 3,
            "Noite": 4
        }
        df_fora['PERIODO_ORDER'] = df_fora['PERIODO_DIA'].map(periodo_order)

        # Ordena e exibe
        df_fora = df_fora.sort_values(by='PERIODO_ORDER', ascending=True)

        st.subheader("Exames SLA FORA DO PERÍODO (ordenados por período do dia)")
        st.dataframe(df_fora.drop(columns=['PERIODO_ORDER']))

        # 4.1) Contagem total de cada período
        # value_counts() retorna um Series com PERIODO_DIA -> contagem
        contagem_periodo = df_fora['PERIODO_DIA'].value_counts()
        # Transformar em DataFrame para exibir
        contagem_periodo_df = pd.DataFrame({
            'PERIODO_DIA': contagem_periodo.index,
            'Contagem': contagem_periodo.values
        })

        st.write("Contagem total de cada período (somente exames SLA FORA DO PERÍODO):")
        st.dataframe(contagem_periodo_df)

        # ----------------------------------------------------------- #
        # 5) Gráfico de Pizza (SLA Status)                           #
        # ----------------------------------------------------------- #
        if not df_filtered.empty:
            sla_status_counts = df_filtered['SLA_STATUS'].value_counts()
            colors = [
                'lightcoral' if status == 'SLA FORA DO PERÍODO' else 'lightgreen'
                for status in sla_status_counts.index
            ]
            fig, ax = plt.subplots()
            ax.pie(
                sla_status_counts,
                labels=sla_status_counts.index,
                autopct='%1.1f%%',
                colors=colors
            )
            ax.set_title(f'SLA Status - {selected_unidade} - {selected_grupo} - {selected_tipo_atendimento}')

            # Adiciona o logo no gráfico
            logo = Image.open(BytesIO(requests.get(url).content))
            logo.thumbnail((400, 400))
            fig.figimage(logo, 10, 10, zorder=1, alpha=0.7)

            st.pyplot(fig)
        else:
            st.warning("Nenhum registro encontrado para este filtro.")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

if __name__ == "__main__":
    main()
