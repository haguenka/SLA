import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import requests
from io import BytesIO
import numpy as np
import re
from dateutil import parser
from datetime import datetime
import openai
import json

# Adicionamos importações para exportar Excel
import io
import base64

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
    logo_url = 'https://raw.githubusercontent.com/haguenka/SLA/main/logo.jpg'
    logo = load_logo(logo_url)
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
        # if 'MEDICO_SOLICITANTE' not in df.columns:
            # st.error("'MEDICO_SOLICITANTE' column not found in the data.")
            # return
        if 'UNIDADE' not in df.columns or 'TIPO_ATENDIMENTO' not in df.columns:
            st.error("'UNIDADE' ou 'TIPO_ATENDIMENTO' column not found.")
            return

        # Padroniza 'MEDICO_SOLICITANTE'
        # df['MEDICO_SOLICITANTE'] = df['MEDICO_SOLICITANTE'].astype(str).str.strip().str.lower()

        # Filtra os grupos permitidos
        allowed_groups = [
            'GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA',
            'GRUPO RAIO-X', 'GRUPO MAMOGRAFIA',
            'GRUPO MEDICINA NUCLEAR', 'GRUPO ULTRASSOM'
        ]
        df = df[df['GRUPO'].isin(allowed_groups)]

        # Substitui células vazias ou contendo somente espaços por np.nan
        if 'STATUS_APROVADO' in df.columns:
            df['STATUS_APROVADO'] = df['STATUS_APROVADO'].replace(r'^\s*$', np.nan, regex=True)
        else:
            st.error("'STATUS_APROVADO' column not found in the data.")
            return

        # Conversão das colunas de data/hora
        df['STATUS_ALAUDAR'] = pd.to_datetime(df['STATUS_ALAUDAR'], dayfirst=True, errors='coerce')
        df['STATUS_PRELIMINAR'] = pd.to_datetime(df['STATUS_PRELIMINAR'], dayfirst=True, errors='coerce')
        df['STATUS_APROVADO'] = pd.to_datetime(df['STATUS_APROVADO'], dayfirst=True, errors='coerce')

        # Conversão da coluna DATA_HORA_PRESCRICAO
        if 'DATA_HORA_PRESCRICAO' in df.columns:
            df['DATA_HORA_PRESCRICAO'] = pd.to_datetime(df['DATA_HORA_PRESCRICAO'], dayfirst=True, errors='coerce')
        else:
            st.error("'DATA_HORA_PRESCRICAO' column not found in the data.")
            return

        # Cálculo do END_DATE (para Hospital Santa Catarina, ignora STATUS_PRELIMINAR)
        df['END_DATE'] = df.apply(
            lambda row: row['STATUS_APROVADO'] if row['UNIDADE'] == 'Hospital Santa Catarina'
            else (row['STATUS_PRELIMINAR'] if pd.notna(row['STATUS_PRELIMINAR']) else row['STATUS_APROVADO']),
            axis=1
        )

        # Função para calcular horas úteis excluindo fins de semana
        def calculate_business_hours(start_date, end_date):
            if pd.isna(start_date) or pd.isna(end_date):
                return np.nan
            
            # Se as datas são iguais, verifica se é fim de semana
            if start_date.date() == end_date.date():
                if start_date.weekday() < 5:  # Segunda a sexta (0-4)
                    return (end_date - start_date).total_seconds() / 3600
                else:
                    return 0  # Fim de semana
            
            total_hours = 0
            current_date = start_date
            
            while current_date.date() < end_date.date():
                next_day = current_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                # Se o dia atual não é fim de semana (segunda a sexta)
                if current_date.weekday() < 5:
                    hours_in_day = (next_day - current_date).total_seconds() / 3600
                    total_hours += hours_in_day
                
                # Move para o início do próximo dia
                current_date = current_date.replace(hour=0, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
            
            # Adiciona as horas do último dia (se não for fim de semana)
            if current_date.weekday() < 5:
                final_hours = (end_date - current_date).total_seconds() / 3600
                total_hours += final_hours
            
            return total_hours

        # Cálculo do DELTA_TIME excluindo fins de semana
        df['DELTA_TIME'] = df.apply(
            lambda row: calculate_business_hours(row['STATUS_ALAUDAR'], row['END_DATE']),
            axis=1
        )

        # Define condições para SLA fora do período
        # doctors_of_interest = ['henrique arume guenka', 'marcelo jacobina de abreu']
        # condition_1 = (df['GRUPO'] == 'GRUPO MAMOGRAFIA') & (df['MEDICO_SOLICITANTE'].isin(doctors_of_interest)) & (df['DELTA_TIME'] > 120)
        condition_2 = (df['GRUPO'] == 'GRUPO MAMOGRAFIA') & (df['DELTA_TIME'] > 96)
        condition_3 = (df['GRUPO'] == 'GRUPO RAIO-X') & (df['DELTA_TIME'] > 96)
        condition_4 = (df['GRUPO'] == 'GRUPO MEDICINA NUCLEAR') & (df['DELTA_TIME'] > 96)
        condition_5 = (df['TIPO_ATENDIMENTO'] == 'Pronto Atendimento') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 1.2)
        condition_6 = (df['TIPO_ATENDIMENTO'] == 'Internado') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 24)
        condition_7 = (df['TIPO_ATENDIMENTO'] == 'Externo') & (df['GRUPO'].isin(['GRUPO TOMOGRAFIA', 'GRUPO RESSONÂNCIA MAGNÉTICA', 'GRUPO ULTRASSOM'])) & (df['DELTA_TIME'] > 96)

        df['SLA_STATUS'] = 'SLA DENTRO DO PERÍODO'
        df.loc[condition_2 | condition_3 | condition_4 | condition_5 | condition_6 | condition_7,
               'SLA_STATUS'] = 'SLA FORA DO PERÍODO'

        # Cria a coluna OBSERVACAO se não existir
        if 'OBSERVACAO' not in df.columns:
            df['OBSERVACAO'] = ''

        # Criação da coluna PERIODO_DIA com base em STATUS_ALAUDAR
        def calcular_periodo_dia(dt):
            if pd.isna(dt):
                return None
            hora = dt.hour
            if 0 <= hora < 7:
                return "Madrugada"
            elif 7 <= hora < 13:
                return "Manhã"
            elif 13 <= hora < 19:
                return "Tarde"
            else:
                return "Noite"
        df['PERIODO_DIA'] = df['STATUS_ALAUDAR'].apply(calcular_periodo_dia)

        # Colunas selecionadas
        selected_columns = [
            'SAME', 'NOME_PACIENTE', 'GRUPO', 'DESCRICAO_PROCEDIMENTO',
            'MEDICO_LAUDO_DEFINITIVO', 'UNIDADE', 'TIPO_ATENDIMENTO',
            'DATA_HORA_PRESCRICAO', 'STATUS_ALAUDAR', 'STATUS_PRELIMINAR',
            'STATUS_APROVADO', 'DELTA_TIME', 'SLA_STATUS',
            'OBSERVACAO', 'PERIODO_DIA', 'STATUS_ATUAL'
        ]
        df_selected = df[selected_columns]

        # Filtros na barra lateral
        unidade_options = df['UNIDADE'].unique()
        selected_unidade = st.sidebar.selectbox("Selecione a UNIDADE", sorted(unidade_options))

        grupo_options = df['GRUPO'].unique()
        selected_grupo = st.sidebar.selectbox("Selecione o GRUPO", sorted(grupo_options))

        tipo_atendimento_options = df['TIPO_ATENDIMENTO'].unique()
        selected_tipo_atendimento = st.sidebar.selectbox("Selecione o Tipo de Atendimento", sorted(tipo_atendimento_options))

        # Filtro pelo período utilizando DATA_HORA_PRESCRICAO
        min_date = df['DATA_HORA_PRESCRICAO'].min()
        max_date = df['DATA_HORA_PRESCRICAO'].max()
        start_date, end_date = st.sidebar.date_input("Selecione o período", [min_date, max_date])

        # DataFrame filtrado (para abas 1 e 2, se quiser)
        df_filtered = df_selected[
            (df_selected['UNIDADE'] == selected_unidade) &
            (df_selected['GRUPO'] == selected_grupo) &
            (df_selected['TIPO_ATENDIMENTO'] == selected_tipo_atendimento) &
            (df_selected['DATA_HORA_PRESCRICAO'] >= pd.Timestamp(start_date)) &
            (df_selected['DATA_HORA_PRESCRICAO'] <= pd.Timestamp(end_date))
        ]

        df_filtered_2 = df_selected[
            (df_selected['UNIDADE'] == selected_unidade) &
            (df_selected['GRUPO'] == selected_grupo) &
            (df_selected['DATA_HORA_PRESCRICAO'] >= pd.Timestamp(start_date)) &
            (df_selected['DATA_HORA_PRESCRICAO'] <= pd.Timestamp(end_date))
        ]

        # Criação das abas
        tab1, tab2, tab3 = st.tabs(["Exames com Laudo", "Exames sem Laudo", "Agente de IA"])

        # --- Aba 1: Exames com Laudo ---
        with tab1:
            st.subheader("Dados dos Exames (com laudo)")
            df_com_laudo = df_filtered[
                (df_filtered['STATUS_PRELIMINAR'].notna()) | (df_filtered['STATUS_APROVADO'].notna())
            ]
            st.dataframe(df_com_laudo)
            total_exams = len(df_com_laudo)
            st.write(f"Total de exames com laudo: {total_exams}")

            df_fora = df_com_laudo[df_com_laudo['SLA_STATUS'] == 'SLA FORA DO PERÍODO'].copy()
            periodo_order = {"Madrugada": 1, "Manhã": 2, "Tarde": 3, "Noite": 4}
            df_fora['PERIODO_ORDER'] = df_fora['PERIODO_DIA'].map(periodo_order)
            df_fora = df_fora.sort_values(by='PERIODO_ORDER', ascending=True)
            st.subheader("Exames SLA FORA DO PRAZO (ordenados por período do dia)")
            st.dataframe(df_fora.drop(columns=['PERIODO_ORDER']))

            # Contagens
            contagem_periodo = df_fora['PERIODO_DIA'].value_counts()
            contagem_periodo_df = pd.DataFrame({
                'PERIODO_DIA': contagem_periodo.index,
                'Contagem': contagem_periodo.values
            })
            st.subheader("Contagem por período (exames SLA FORA DO PRAZO)")
            st.dataframe(contagem_periodo_df)

            contagem_periodo_total = df_com_laudo['PERIODO_DIA'].value_counts()
            contagem_periodo_total_df = pd.DataFrame({
                'PERIODO_DIA': contagem_periodo_total.index,
                'Contagem': contagem_periodo_total.values
            })
            st.subheader("Contagem total por período (exames com laudo)")
            st.dataframe(contagem_periodo_total_df)

            if not df_com_laudo.empty:
                sla_status_counts = df_com_laudo['SLA_STATUS'].value_counts()
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

                logo_img = Image.open(BytesIO(requests.get(logo_url).content))
                logo_img.thumbnail((400, 400))
                fig.figimage(logo_img, 10, 10, zorder=1, alpha=0.7)
                st.pyplot(fig)
            else:
                st.warning("Nenhum registro encontrado para este filtro.")

        # --- Aba 2: Exames sem Laudo ---
        with tab2:
            st.subheader("Exames sem Laudo")
            df_sem_laudo = df_filtered_2[df_filtered_2['STATUS_ATUAL'].isin(['A laudar', 'Sem Laudo'])]
            st.dataframe(df_sem_laudo)
            st.write(f"Total de exames sem laudo: {len(df_sem_laudo)}")

        # Configura a chave da OpenAI
        openai.api_key = st.secrets["openai"]["api_key"]

        # -------------------------------------------------------------
        # Função para exportar o último resultado em Excel
        # -------------------------------------------------------------
        def export_last_query_to_excel_bytes() -> bytes:
            """
            Gera o arquivo Excel em memória a partir do último resultado armazenado
            e retorna o conteúdo em bytes.
            """
            if "last_query_result" not in st.session_state:
                return None

            df_to_export = st.session_state["last_query_result"].copy()
            if df_to_export.empty:
                return None

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_to_export.to_excel(writer, index=False, sheet_name="Resultado")
            output.seek(0)
            return output.getvalue()

        # -------------------------------------------------------------
        # Função principal de consulta ao DataFrame
        # -------------------------------------------------------------
        def query_dataframe(question: str, df: pd.DataFrame) -> str:
            """
            Filtra o DataFrame conforme a pergunta (modalidade, datas, UNIDADE, TIPO_ATENDIMENTO, etc.)
            e retorna uma string com o resultado.
            Armazena o DataFrame resultante em st.session_state["last_query_result"] para exportação.
            """
            q_lower = question.lower()

            # 1) Detectar a modalidade
            modalidade_map = {
                "tomografia": "GRUPO TOMOGRAFIA",
                "ressonância": "GRUPO RESSONÂNCIA MAGNÉTICA",
                "ressonancia": "GRUPO RESSONÂNCIA MAGNÉTICA",
                "raio-x": "GRUPO RAIO-X",
                "raio x": "GRUPO RAIO-X",
                "mamografia": "GRUPO MAMOGRAFIA",
                "medicina nuclear": "GRUPO MEDICINA NUCLEAR",
                "ultrassom": "GRUPO ULTRASSOM",
            }
            modalidade_detectada = None
            for chave, grupo in modalidade_map.items():
                if chave in q_lower:
                    modalidade_detectada = grupo
                    break

            # 2) Detectar datas
            datas_encontradas = re.findall(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", q_lower)
            datas_convertidas = []
            for d in datas_encontradas:
                try:
                    dt = parser.parse(d, dayfirst=True)
                    datas_convertidas.append(dt.date())
                except:
                    pass

            mes_ano_match = re.findall(r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})", q_lower)
            meses_map = {
                "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, 
                "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
                "outubro": 10, "novembro": 11, "dezembro": 12
            }
            datas_inferidas = []
            for (mes_str, ano_str) in mes_ano_match:
                mes_num = meses_map.get(mes_str, None)
                ano_num = int(ano_str)
                if mes_num:
                    dt_inicio = datetime(ano_num, mes_num, 1).date()
                    if mes_num == 12:
                        dt_fim = datetime(ano_num + 1, 1, 1).date()
                    else:
                        dt_fim = datetime(ano_num, mes_num + 1, 1).date()
                    datas_inferidas.append((dt_inicio, dt_fim))

            # 3) Inicia o DataFrame temporário
            df_temp = df.copy()

            # Modalidade
            if modalidade_detectada:
                df_temp = df_temp[df_temp['GRUPO'] == modalidade_detectada]

            # Datas exatas
            if len(datas_convertidas) == 1:
                dia = datas_convertidas[0]
                df_temp = df_temp[df_temp['DATA_HORA_PRESCRICAO'].dt.date == dia]
            elif len(datas_convertidas) >= 2:
                inicio = min(datas_convertidas)
                fim = max(datas_convertidas)
                df_temp = df_temp[(df_temp['DATA_HORA_PRESCRICAO'].dt.date >= inicio) &
                                  (df_temp['DATA_HORA_PRESCRICAO'].dt.date <= fim)]

            # Intervalo mes_ano
            if datas_inferidas:
                (dt_inicio, dt_fim) = datas_inferidas[0]
                df_temp = df_temp[(df_temp['DATA_HORA_PRESCRICAO'].dt.date >= dt_inicio) &
                                  (df_temp['DATA_HORA_PRESCRICAO'].dt.date < dt_fim)]

            # 4) UNIDADE
            unidades = df['UNIDADE'].unique()
            for unidade in unidades:
                if unidade.lower() in q_lower:
                    df_temp = df_temp[df_temp['UNIDADE'] == unidade]
                    break

            # 5) TIPO_ATENDIMENTO
            tipos = df['TIPO_ATENDIMENTO'].unique()
            for tipo in tipos:
                if tipo.lower() in q_lower:
                    df_temp = df_temp[df_temp['TIPO_ATENDIMENTO'] == tipo]
                    break

            # 6) STATUS_ATUAL (sem laudo)
            if "sem laudo" in q_lower or "a laudar" in q_lower:
                df_temp = df_temp[df_temp['STATUS_ATUAL'].str.lower().isin(["a laudar", "sem laudo"])]

            # Armazena o resultado para exportação
            st.session_state["last_query_result"] = df_temp.copy()

            # 7) Monta resposta
            count = len(df_temp)
            if any(x in q_lower for x in ["quantas", "quantos", "número", "numero"]):
                mod_str = modalidade_detectada.replace("GRUPO ", "").lower() if modalidade_detectada else "exames (todas as modalidades)"
                if datas_inferidas:
                    mi, mf = datas_inferidas[0]
                    return f"Foram {count} {mod_str} realizados entre {mi.strftime('%d/%m/%Y')} e {mf.strftime('%d/%m/%Y')}."
                elif len(datas_convertidas) == 1:
                    return f"Foram {count} {mod_str} realizados em {datas_convertidas[0].strftime('%d/%m/%Y')}."
                elif len(datas_convertidas) >= 2:
                    i2 = min(datas_convertidas)
                    f2 = max(datas_convertidas)
                    return f"Foram {count} {mod_str} realizados no período de {i2.strftime('%d/%m/%Y')} até {f2.strftime('%d/%m/%Y')}."
                else:
                    return f"Foram {count} {mod_str} encontrados no DataFrame."
            
            return f"Após os filtros aplicados, encontrei {count} registros."

        # 2) Defina o schema das funções
        functions = [
            {
                "name": "query_dataframe",
                "description": "Consulta o DataFrame carregado no Python para obter informações.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "A pergunta que o usuário fez sobre o DataFrame."
                        }
                    },
                    "required": ["question"]
                },
            },
            {
                "name": "export_last_query_to_excel",
                "description": (
                    "Gera um arquivo Excel a partir do último resultado de consulta e retorna um link de download."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]

        # 3) Inicializa o histórico da conversa, se ainda não existir
        with tab3:
            if "chat_history" not in st.session_state:
                data_context = (
                    "Você tem acesso a duas funções:\n\n"
                    "1) 'query_dataframe(question)': filtra o DataFrame para responder perguntas.\n"
                    "2) 'export_last_query_to_excel()': gera um arquivo Excel do último resultado filtrado.\n\n"
                    f"Atualmente, há {len(df_filtered)} linhas no df_filtered para visualização nas abas.\n"
                    "Mas a função 'query_dataframe' opera sobre df_selected (todas as linhas/colunas)."
                )
                st.session_state.chat_history = [
                    {
                        "role": "system",
                        "content": (
                            "Você é um assistente de análise de dados. "
                            "Sempre que precisar consultar dados concretos, chame a função 'query_dataframe'. "
                            "Se o usuário quiser um arquivo Excel do resultado, chame 'export_last_query_to_excel'. "
                            "Responda de forma intuitiva e explique seu raciocínio."
                        )
                    },
                    {
                        "role": "system",
                        "content": data_context
                    }
                ]

            user_input = st.text_area("Digite sua pergunta ou comentário:", height=150)
            if st.button("Enviar Consulta"):
                if not user_input.strip():
                    st.info("Por favor, digite uma pergunta para continuar.")
                else:
                    st.session_state.chat_history.append({"role": "user", "content": user_input})
                    try:
                        response = openai.ChatCompletion.create(
                            model="gpt-4o",
                            messages=st.session_state.chat_history,
                            functions=functions,
                            function_call="auto",
                            temperature=0.7
                        )
                        msg_content = response["choices"][0]["message"]

                        if msg_content.get("function_call"):
                            function_name = msg_content["function_call"]["name"]
                            arguments_json = msg_content["function_call"]["arguments"]
                            arguments = json.loads(arguments_json)

                            if function_name == "query_dataframe":
                                answer = query_dataframe(arguments["question"], df_selected)
                                st.session_state.chat_history.append({
                                    "role": "function",
                                    "name": function_name,
                                    "content": answer
                                })
                                # Segunda chamada
                                second_response = openai.ChatCompletion.create(
                                    model="gpt-4",
                                    messages=st.session_state.chat_history,
                                    temperature=0.7
                                )
                                final_reply = second_response["choices"][0]["message"]["content"]
                                st.session_state.chat_history.append({
                                    "role": "assistant",
                                    "content": final_reply
                                })
                                st.write("**Resposta:**")
                                st.write(final_reply)

                            elif function_name == "export_last_query_to_excel":
                                link = export_last_query_to_excel()
                                st.session_state.chat_history.append({
                                    "role": "function",
                                    "name": function_name,
                                    "content": link
                                })
                                second_response = openai.ChatCompletion.create(
                                    model="gpt-4",
                                    messages=st.session_state.chat_history,
                                    temperature=0.7
                                )
                                final_reply = second_response["choices"][0]["message"]["content"]
                                st.session_state.chat_history.append({
                                    "role": "assistant",
                                    "content": final_reply
                                })
                                st.write("**Resposta:**")
                                # Exibimos o link como HTML
                                st.markdown(final_reply, unsafe_allow_html=True)

                            else:
                                st.error("Função desconhecida chamada pelo modelo.")
                        else:
                            final_reply = msg_content["content"]
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": final_reply
                            })
                            st.write("**Resposta:**")
                            st.write(final_reply)

                    except Exception as e:
                        st.error(f"Erro ao executar a consulta: {e}")

            # Em algum lugar da sua interface (por exemplo, logo abaixo da área de chat):
            data = export_last_query_to_excel_bytes()
            if data:
                st.download_button(
                    label="Baixar Excel",
                    data=data,
                    file_name="resultado.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("Não há resultado para exportar no momento.")


    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

if __name__ == "__main__":
    main()
