import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import requests
from io import BytesIO
import numpy as np
import os
import re

# Funções com cache do Streamlit
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

    # Carrega e exibe o logo na barra lateral
    url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
    logo = load_logo(url)
    st.sidebar.image(logo, use_container_width=True)

    # Tenta carregar a planilha do GitHub; se não conseguir, permite upload
    df = load_excel_from_github()
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
            st.error("'UNIDADE' ou 'TIPO_ATENDIMENTO' column not found.")
            return

        # Padroniza 'MEDICO_SOLICITANTE'
        df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].astype(str).str.strip().str.lower()

        # Filtra os grupos permitidos
        allowed_groups = [
            'GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA',
            'GRUPO RAIO-X', 'GRUPO MAMOGRAFIA',
            'GRUPO MEDICINA NUCLEAR', 'GRUPO ULTRASSOM'
        ]
        df = df[df['GRUPO'].isin(allowed_groups)]

        # --------------------------------------------------------------
        # Substitui células vazias ou contendo somente espaços por np.nan
        # e converte STATUS_APROVADO para datetime (valores inválidos viram NaT)
        # --------------------------------------------------------------
        if 'STATUS_APROVADO' in df.columns:
            df['STATUS_APROVADO'] = df['STATUS_APROVADO'].replace(r'^\s*$', np.nan, regex=True)
        else:
            st.error("'STATUS_APROVADO' column not found in the data.")
            return

        # Conversão das colunas de data/hora
        df['STATUS_ALAUDAR'] = pd.to_datetime(df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')
        df['STATUS_PRELIMINAR'] = pd.to_datetime(df['STATUS_PRELIMINAR'], dayfirst=True, errors='coerce')
        df['STATUS_APROVADO'] = pd.to_datetime(df['STATUS_APROVADO'], dayfirst=True, errors='coerce')

        # Conversão da coluna DATA_HORA_PRESCRICAO (usada para o filtro de período)
        if 'DATA_HORA_PRESCRICAO' in df.columns:
            df['DATA_HORA_PRESCRICAO'] = pd.to_datetime(df['DATA_HORA_PRESCRICAO'], dayfirst=True, errors='coerce')
        else:
            st.error("'DATA_HORA_PRESCRICAO' column not found in the data.")
            return

        # Remove as linhas em que ambas STATUS_PRELIMINAR e STATUS_APROVADO estão ausentes
        #df = df.dropna(subset=['STATUS_PRELIMINAR', 'STATUS_APROVADO'], how='all')

        # Cálculo do DELTA_TIME
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

        df['SLA_STATUS'] = 'SLA DENTRO DO PERÍODO'
        df.loc[condition_1 | condition_2 | condition_3 | condition_4 | condition_5 | condition_6 | condition_7,
               'SLA_STATUS'] = 'SLA FORA DO PERÍODO'

        # Cria a coluna OBSERVACAO se não existir
        if 'OBSERVACAO' not in df.columns:
            df['OBSERVACAO'] = ''

        # ----------------------------------------------------------------------
        # 1) Criação da coluna PERIODO_DIA com base em STATUS_ALAUDAR
        # ----------------------------------------------------------------------
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

        # ----------------------------------------------------------------------
        # Colunas selecionadas (incluindo DATA_HORA_PRESCRICAO para filtro)
        # ----------------------------------------------------------------------
        selected_columns = [
            'SAME', 'NOME_PACIENTE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO',
            'MEDICO_LAUDO_DEFINITIVO', 'UNIDADE', 'TIPO_ATENDIMENTO',
            'DATA_HORA_PRESCRICAO',  # Utilizada para o filtro de data
            'STATUS_ALAUDAR', 'STATUS_PRELIMINAR', 'STATUS_APROVADO',
            'MEDICO_SOLICITANTE', 'DELTA_TIME', 'SLA_STATUS', 'OBSERVACAO',
            'PERIODO_DIA', 'STATUS_ATUAL'
        ]
        df_selected = df[selected_columns]

        # ----------------------------------------------------------------------
        # 2) Filtros na barra lateral
        # ----------------------------------------------------------------------
        unidade_options = df['UNIDADE'].unique()
        selected_unidade = st.sidebar.selectbox("Selecione a UNIDADE", sorted(unidade_options))

        grupo_options = df['GRUPO'].unique()
        selected_grupo = st.sidebar.selectbox("Selecione o GRUPO", sorted(grupo_options))

        tipo_atendimento_options = df['TIPO_ATENDIMENTO'].unique()
        selected_tipo_atendimento = st.sidebar.selectbox("Selecione o Tipo de Atendimento", sorted(tipo_atendimento_options))

        # Utiliza DATA_HORA_PRESCRICAO para selecionar o período
        min_date = df['DATA_HORA_PRESCRICAO'].min()
        max_date = df['DATA_HORA_PRESCRICAO'].max()
        start_date, end_date = st.sidebar.date_input("Selecione o período", [min_date, max_date])

        # ----------------------------------------------------------------------
        # 3) Filtro do DataFrame principal
        # ----------------------------------------------------------------------
        df_filtered = df_selected[
            (df_selected['UNIDADE'] == selected_unidade) &
            (df_selected['GRUPO'] == selected_grupo) &
            (df_selected['TIPO_ATENDIMENTO'] == selected_tipo_atendimento) &
            (df_selected['DATA_HORA_PRESCRICAO'] >= pd.Timestamp(start_date)) &
            (df_selected['DATA_HORA_PRESCRICAO'] <= pd.Timestamp(end_date))
        ]

        # ----------------------------------------------------------------------
        # Criação das abas para visualização dos dados
        # ----------------------------------------------------------------------
        tab1, tab2 = st.tabs(["Exames com Laudo", "Exames sem Laudo"])

        # Aba 1: Exames com laudo (todos os registros filtrados)
        with tab1:
            st.subheader("Dados dos Exames (com laudo)")
            st.dataframe(df_filtered)
            total_exams = len(df_filtered)
            st.write(f"Total de exames: {total_exams}")

            # Exibe exames com SLA FORA DO PERÍODO, ordenados por período do dia
            df_fora = df_filtered[df_filtered['SLA_STATUS'] == 'SLA FORA DO PERÍODO'].copy()
            periodo_order = {"Madrugada": 1, "Manhã": 2, "Tarde": 3, "Noite": 4}
            df_fora['PERIODO_ORDER'] = df_fora['PERIODO_DIA'].map(periodo_order)
            df_fora = df_fora.sort_values(by='PERIODO_ORDER', ascending=True)

            st.subheader("Exames SLA FORA DO PRAZO (ordenados por período do dia)")
            st.dataframe(df_fora.drop(columns=['PERIODO_ORDER']))

            # Contagem por período (apenas exames com SLA FORA DO PERÍODO)
            contagem_periodo = df_fora['PERIODO_DIA'].value_counts()
            contagem_periodo_df = pd.DataFrame({
                'PERIODO_DIA': contagem_periodo.index,
                'Contagem': contagem_periodo.values
            })
            st.subheader("Contagem por período (exames SLA FORA DO PRAZO)")
            st.dataframe(contagem_periodo_df)

            # Contagem total por período (todos os exames)
            contagem_periodo_total = df_filtered['PERIODO_DIA'].value_counts()
            contagem_periodo_total_df = pd.DataFrame({
                'PERIODO_DIA': contagem_periodo_total.index,
                'Contagem': contagem_periodo_total.values
            })
            st.subheader("Contagem total por período (todos os exames)")
            st.dataframe(contagem_periodo_total_df)

            # Gráfico de Pizza para o SLA Status
            if not df_filtered.empty:
                sla_status_counts = df_filtered['SLA_STATUS'].value_counts()
                colors = ['lightcoral' if status == 'SLA FORA DO PERÍODO' else 'lightgreen'
                          for status in sla_status_counts.index]
                fig, ax = plt.subplots()
                ax.pie(
                    sla_status_counts,
                    labels=sla_status_counts.index,
                    autopct='%1.1f%%',
                    colors=colors
                )
                ax.set_title(f'SLA Status - {selected_unidade} - {selected_grupo} - {selected_tipo_atendimento}')

                # Adiciona o logo no gráfico
                logo_img = Image.open(BytesIO(requests.get(url).content))
                logo_img.thumbnail((400, 400))
                fig.figimage(logo_img, 10, 10, zorder=1, alpha=0.7)

                st.pyplot(fig)
            else:
                st.warning("Nenhum registro encontrado para este filtro.")

        # Aba 2: Exames sem Laudo (filtrados por status_atual com as entradas desejadas)
        with tab2:
            st.subheader("Exames sem Laudo")
            df_sem_laudo = df_filtered[df_filtered['status_atual'].isin(['A laudar', 'Liberado', 'Sem laudo'])]
            st.dataframe(df_sem_laudo)
            st.write(f"Total de exames sem laudo: {len(df_sem_laudo)}")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

if __name__ == "__main__":
    main()
