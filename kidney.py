import os
import re
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import calendar
import pandas as pd
import streamlit as st
from io import BytesIO
from fuzzywuzzy import fuzz, process
import zipfile
import requests  # Para carregar a logo a partir de uma URL
import base64  # Já utilizado para download do PDF

# -------------------------------
# FUNÇÃO PARA CARREGAR A LOGO COM CACHE
# -------------------------------
@st.cache_data(show_spinner=False)
def load_logo(url):
    response = requests.get(url)
    if response.status_code == 200:
        return Image.open(BytesIO(response.content))
    else:
        return None

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

# -------------------------------
# EXPRESSÕES REGULARES GLOBAIS
# -------------------------------
regex_calculo = re.compile(r"c\s*[áa]\s*l\s*[cç]\s*[úu]\s*l\s*[oa]s?", re.IGNORECASE)
regex_tamanho = re.compile(r"\b\d+[.,]?\d*\s?(?:mm|cm)\b", re.IGNORECASE)
regex_nome = re.compile(r"(?i)paciente\s*:\s*(.+)")
regex_idade = re.compile(r"(?i)idade\s*:\s*(\d+[Aa]?\s*\d*[Mm]?)")
regex_same = re.compile(r"(?i)same\s*:\s*(\S+)")
regex_data = re.compile(r"(?i)data\s*do\s*exame\s*:\s*([\d/]+)")

# -------------------------------
# FUNÇÃO PARA DESTACAR A PALAVRA-CHAVE "CALCULO" EM AMARELO
# -------------------------------
def highlight_calculo(sentence):
    """
    Recebe uma frase e retorna a mesma frase com todas as ocorrências
    do termo 'calculo' (considerando variações com acentuação e espaçamentos)
    envolvidas em uma tag <span> com fundo amarelo.
    """
    pattern = r"(c\s*[áa]\s*l\s*[cç]\s*[úu]\s*l\s*[oa]s?)"
    highlighted = re.sub(
        pattern,
        r"<span style='background-color: green;'>\1</span>",
        sentence,
        flags=re.IGNORECASE
    )
    return highlighted

# -------------------------------
# FUNÇÕES DE PROCESSAMENTO
# -------------------------------
def extrair_texto(pdf_input):
    """
    Extrai o texto do PDF. Se não houver texto, aplica OCR.
    Aceita tanto um caminho (string) quanto um objeto file-like (BytesIO).
    """
    texto_completo = ""
    if isinstance(pdf_input, str):
        doc = fitz.open(pdf_input)
    elif hasattr(pdf_input, "read"):
        pdf_input.seek(0)
        pdf_bytes = pdf_input.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    else:
        doc = fitz.open(pdf_input)
    for page_num in range(len(doc)):
        texto = doc[page_num].get_text("text")
        if not texto.strip():
            pix = doc[page_num].get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            texto = pytesseract.image_to_string(img, lang="por")
        texto_completo += texto + "\n"
    doc.close()
    return texto_completo

def extrair_informacoes(texto_completo):
    """
    Extrai informações do cabeçalho do laudo a partir do texto completo.
    """
    dados_cabecalho = {}
    dados_cabecalho["Paciente"] = regex_nome.search(texto_completo).group(1).strip() if regex_nome.search(texto_completo) else "N/D"
    dados_cabecalho["Idade"] = regex_idade.search(texto_completo).group(1).strip() if regex_idade.search(texto_completo) else "N/D"
    dados_cabecalho["Same"] = regex_same.search(texto_completo).group(1).strip() if regex_same.search(texto_completo) else "N/D"
    dados_cabecalho["Data do Exame"] = regex_data.search(texto_completo).group(1).strip() if regex_data.search(texto_completo) else "N/D"
    return dados_cabecalho

def processar_pdfs_streamlit(pdf_files):
    """
    Processa os PDFs carregados via file uploader.
    Retorna o relatório mensal, uma lista de registros e um DataFrame com os pacientes minerados.
    Cada registro inclui o nome do arquivo, os bytes do PDF e a sentença destacada com a palavra-chave.
    """
    relatorio_mensal = {}
    lista_calculos = []
    for uploaded_file in pdf_files:
        file_name = uploaded_file.name
        pdf_bytes = uploaded_file.read()
        pdf_stream = BytesIO(pdf_bytes)
        texto_completo = extrair_texto(pdf_stream)
        cabecalho = extrair_informacoes(texto_completo)
        sentencas = re.split(r'(?<=[.!?])\s+', texto_completo)
        ocorrencias_validas = []
        for sentenca in sentencas:
            sentenca = sentenca.replace('\n', ' ').replace('\r', ' ').strip()
            # Verifica se a sentença contém o termo "calculo"
            if regex_calculo.search(sentenca):
                # Exclui se a sentença conter "sem"
                if re.search(r"\bsem\b", sentenca, re.IGNORECASE):
                    continue
                # NOVO: Exclui se a sentença indicar negação (ex.: "não há", "não apresenta", etc.)
                if re.search(r"\b(não\s+há|não\s+apresenta|não\s+possui|nenhum)\b", sentenca, re.IGNORECASE):
                    continue
                # Verifica se a sentença contém alguma das palavras obrigatórias
                if not re.search(r"\b(?:renal(?:es)?|caliciano(?:s)?|calicinal(?:s)?|ureter(?:es)?|ureteral(?:ais))\b", sentenca, re.IGNORECASE):
                    continue
                # Destaca a ocorrência de "calculo" na frase
                sentenca_destacada = highlight_calculo(sentenca)
                tamanho_match = re.search(regex_tamanho, sentenca)
                if tamanho_match:
                    ocorrencias_validas.append((tamanho_match.group(0), sentenca_destacada))
                else:
                    ocorrencias_validas.append(("Não informado", sentenca_destacada))
        
        if ocorrencias_validas:
            data_exame = cabecalho["Data do Exame"]
            partes_data = data_exame.split("/")
            if len(partes_data) == 3:
                try:
                    dia, mes, ano = partes_data
                    mes = int(mes)
                    ano = int(ano)
                except ValueError:
                    mes, ano = 0, 0
            else:
                mes, ano = 0, 0
            key = (ano, mes)
            if key not in relatorio_mensal:
                relatorio_mensal[key] = set()
            relatorio_mensal[key].add(cabecalho["Paciente"])
            for tamanho, sentenca_destacada in ocorrencias_validas:
                record = {**cabecalho,
                          "Tamanho": tamanho,
                          "Sentenca": sentenca_destacada,
                          "Arquivo": file_name,
                          "pdf_bytes": pdf_bytes}
                lista_calculos.append(record)
    for key in relatorio_mensal:
        relatorio_mensal[key] = len(relatorio_mensal[key])
    pacientes_minerados_df = pd.DataFrame(lista_calculos)
    if not pacientes_minerados_df.empty:
        pacientes_minerados_df['has_measure'] = pacientes_minerados_df['Tamanho'].apply(
            lambda x: 0 if x.strip().lower() == "não informado" else 1
        )
        pacientes_minerados_df = pacientes_minerados_df.sort_values('has_measure', ascending=False)
        pacientes_minerados_df = pacientes_minerados_df.drop_duplicates(subset=['Paciente', 'Same'], keep='first')
        pacientes_minerados_df.drop(columns=['has_measure'], inplace=True)
    return relatorio_mensal, lista_calculos, pacientes_minerados_df


def processar_pdfs_from_zip(zip_file):
    """
    Recebe um arquivo ZIP e extrai todos os PDFs contidos nele.
    Processa cada PDF e retorna o relatório mensal, uma lista de registros e um DataFrame.
    Cada registro inclui o nome do arquivo, os bytes do PDF e a sentença destacada com a palavra-chave.
    """
    relatorio_mensal = {}
    lista_calculos = []
    zip_data = BytesIO(zip_file.read())
    with zipfile.ZipFile(zip_data, "r") as z:
        pdf_names = [name for name in z.namelist() if name.lower().endswith(".pdf")]
        for pdf_name in pdf_names:
            with z.open(pdf_name) as pdf_file:
                pdf_bytes = pdf_file.read()
                pdf_stream = BytesIO(pdf_bytes)
                texto_completo = extrair_texto(pdf_stream)
                cabecalho = extrair_informacoes(texto_completo)
                sentencas = re.split(r'(?<=[.!?])\s+', texto_completo)
                ocorrencias_validas = []
                for sentenca in sentencas:
                    if regex_calculo.search(sentenca):
                        if re.search(r"\bsem\b", sentenca, re.IGNORECASE):
                            continue
                        if re.search(r"\b(não\s+há|não\s+apresenta|não\s+possui|nenhum)\b", sentenca, re.IGNORECASE):
                            continue
                        if not re.search(r"\b(?:renal(?:es)?|caliciano(?:s)?|calicinal(?:s)?|ureter(?:es)?|ureteral(?:ais))\b", sentenca, re.IGNORECASE):
                            continue
                        sentenca_destacada = highlight_calculo(sentenca)
                        tamanho_match = re.search(regex_tamanho, sentenca)
                        if tamanho_match:
                            ocorrencias_validas.append((tamanho_match.group(0), sentenca_destacada))
                        else:
                            ocorrencias_validas.append(("Não informado", sentenca_destacada))
                if ocorrencias_validas:
                    data_exame = cabecalho["Data do Exame"]
                    partes_data = data_exame.split("/")
                    if len(partes_data) == 3:
                        try:
                            dia, mes, ano = partes_data
                            mes = int(mes)
                            ano = int(ano)
                        except ValueError:
                            mes, ano = 0, 0
                    else:
                        mes, ano = 0, 0
                    key = (ano, mes)
                    if key not in relatorio_mensal:
                        relatorio_mensal[key] = set()
                    relatorio_mensal[key].add(cabecalho["Paciente"])
                    for tamanho, sentenca_destacada in ocorrencias_validas:
                        record = {**cabecalho,
                                  "Tamanho": tamanho,
                                  "Sentenca": sentenca_destacada,
                                  "Arquivo": pdf_name,
                                  "pdf_bytes": pdf_bytes}
                        lista_calculos.append(record)
    for key in relatorio_mensal:
        relatorio_mensal[key] = len(relatorio_mensal[key])
    pacientes_minerados_df = pd.DataFrame(lista_calculos)
    if not pacientes_minerados_df.empty:
        pacientes_minerados_df['has_measure'] = pacientes_minerados_df['Tamanho'].apply(
            lambda x: 0 if x.strip().lower() == "não informado" else 1
        )
        pacientes_minerados_df = pacientes_minerados_df.sort_values('has_measure', ascending=False)
        pacientes_minerados_df = pacientes_minerados_df.drop_duplicates(subset=['Paciente', 'Same'], keep='first')
        pacientes_minerados_df.drop(columns=['has_measure'], inplace=True)
        pacientes_minerados_df = pacientes_minerados_df.drop(columns=["Arquivo", "pdf_bytes"], errors="ignore")
    return relatorio_mensal, lista_calculos, pacientes_minerados_df

def correlacionar_pacientes_fuzzy(pacientes_df, internados_df, threshold=70):
    """
    Correlaciona os pacientes minerados com os internados usando fuzzy matching.
    Retorna um DataFrame com os pacientes que tiveram correspondência com pontuação >= threshold
    e inclui a coluna 'convenio' extraída do dataframe dos internados.
    """
    pacientes_df['Paciente'] = pacientes_df['Paciente'].fillna("").astype(str)
    internados_df['Paciente'] = internados_df['Paciente'].fillna("").astype(str)
    if 'Convenio' not in internados_df.columns:
        st.warning("A coluna 'convenio' não foi encontrada no dataframe de internados. Será criada com valores vazios.")
        internados_df['Convenio'] = None
    pacientes_df['Paciente_lower'] = pacientes_df['Paciente'].str.lower()
    internados_df['Paciente_lower'] = internados_df['Paciente'].str.lower()
    internados_list = internados_df['Paciente_lower'].tolist()
    matched_indices = []
    convenios = []
    for idx, row in pacientes_df.iterrows():
        nome = row['Paciente_lower']
        if not nome:
            continue
        best_match, score = process.extractOne(nome, internados_list, scorer=fuzz.ratio)
        if score >= threshold:
            matched_indices.append(idx)
            match_idx = internados_df[internados_df['Paciente_lower'] == best_match].index[0]
            convenio_value = internados_df.loc[match_idx, 'Convenio']
            convenios.append(convenio_value)
    correlated_df = pacientes_df.loc[matched_indices].copy()
    correlated_df.drop(columns=['Paciente_lower'], inplace=True)
    correlated_df = correlated_df.drop(columns=["Arquivo", "pdf_bytes"], errors="ignore")
    correlated_df['Convenio'] = convenios
    return correlated_df

# -------------------------------
# ARMAZENAMENTO EM CACHE (st.session_state)
# -------------------------------
if "pacientes_minerados_df" not in st.session_state:
    st.session_state["pacientes_minerados_df"] = pd.DataFrame(columns=["Paciente", "Idade", "Same", "Data do Exame", "Tamanho", "Sentenca", "Arquivo", "pdf_bytes", "Convenio"])
    st.session_state["relatorio_mensal"] = {}
    st.session_state["lista_calculos"] = []

# -------------------------------
# INTERFACE STREAMLIT (SIDEBAR)
# -------------------------------
upload_method = st.sidebar.radio("Selecione o método de upload:", 
                                 ("Upload de PDFs", "Upload de ZIP contendo PDFs"))

if upload_method == "Upload de PDFs":
    pdf_files = st.sidebar.file_uploader("Selecione os arquivos PDF", type="pdf", accept_multiple_files=True)
else:
    zip_file = st.sidebar.file_uploader("Selecione o arquivo ZIP contendo os PDFs", type="zip")

# Upload do arquivo de internados (opcional)
internados_file = st.sidebar.file_uploader("Arquivo internados.xlsx (opcional)", type="xlsx")

# Upload do arquivo de Atendimentos PA (opcional) – movido para a sidebar fora do bloco de processamento
atendimentos_file = st.sidebar.file_uploader("Arquivo Atendimentos PA (xlsx) (opcional)", type="xlsx")


# -------------------------------
# BOTÃO DE PROCESSAMENTO
# -------------------------------
if st.sidebar.button("Processar"):
    if upload_method == "Upload de PDFs" and pdf_files:
        with st.spinner("Processando PDFs..."):
            new_relatorio, new_lista_calculos, new_df = processar_pdfs_streamlit(pdf_files)
        st.success("Processamento concluído!")
    elif upload_method == "Upload de ZIP" and zip_file:
        with st.spinner("Processando arquivo ZIP..."):
            new_relatorio, new_lista_calculos, new_df = processar_pdfs_from_zip(zip_file)
        st.success("Processamento concluído!")
    else:
        st.error("Por favor, selecione os arquivos PDF ou o arquivo ZIP.")
        new_relatorio, new_lista_calculos, new_df = {}, [], pd.DataFrame()

    # Combina os dados novos com os já armazenados em cache
    if not new_df.empty:
        combined_df = pd.concat([st.session_state["pacientes_minerados_df"], new_df], ignore_index=True)
        combined_df['has_measure'] = combined_df['Tamanho'].apply(lambda x: 0 if x.strip().lower() == "não informado" else 1)
        combined_df = combined_df.sort_values('has_measure', ascending=False)
        combined_df = combined_df.drop_duplicates(subset=['Paciente', 'Same'], keep='first')
        combined_df.drop(columns=['has_measure'], inplace=True)
        st.session_state["pacientes_minerados_df"] = combined_df

        # Recalcula o relatório mensal a partir do DataFrame combinado
        combined_relatorio = {}
        for idx, row in combined_df.iterrows():
            data_exame = row["Data do Exame"]
            partes_data = data_exame.split("/")
            if len(partes_data) == 3:
                try:
                    dia, mes, ano = partes_data
                    mes = int(mes)
                    ano = int(ano)
                except ValueError:
                    mes, ano = 0, 0
            else:
                mes, ano = 0, 0
            key = (ano, mes)
            if key not in combined_relatorio:
                combined_relatorio[key] = set()
            combined_relatorio[key].add(row["Paciente"])
        for key in combined_relatorio:
            combined_relatorio[key] = len(combined_relatorio[key])
        st.session_state["relatorio_mensal"] = combined_relatorio
        st.session_state["lista_calculos"] = combined_df.to_dict(orient="records")

    # -------------------------------
    # MONTAGEM DO RELATÓRIO E DA LISTA (EM ABAS)
    # -------------------------------
    report_md = "Pacientes encontrados com cálculos por mês:\n"
    for key in sorted(st.session_state["relatorio_mensal"].keys(), key=lambda x: (x[0], x[1]) if isinstance(x, tuple) and len(x)==2 else (0,0)):
        ano, mes = key if isinstance(key, tuple) and len(key)==2 else (0, 0)
        nome_mes = calendar.month_name[mes] if 1 <= mes <= 12 else "Desconhecido"
        report_md += f"- <span style='color: yellow; font-size: 20px;'>{nome_mes}/{ano}</span>: {st.session_state['relatorio_mensal'].get((ano, mes), 0)} paciente(s)<br>"
    report_md += "<br>Dados dos pacientes minerados:<br>"
    
    df_para_exibicao = st.session_state["pacientes_minerados_df"].drop(columns=["pdf_bytes", "Arquivo", "Sentenca"], errors="ignore")
    
    # Prepara o relatório diário
    relatorio_diario = {}
    for idx, row in st.session_state["pacientes_minerados_df"].iterrows():
        data = row["Data do Exame"]
        partes = data.split("/")
        if len(partes) == 3:
            dia = partes[0].zfill(2)
            try:
                mes = int(partes[1])
            except:
                mes = 0
            ano = partes[2]
            key = (ano, mes, dia)
            if key not in relatorio_diario:
                relatorio_diario[key] = set()
            relatorio_diario[key].add(row["Paciente"])
    
    grouped_by_month = {}
    for (ano, mes, dia), pacientes in relatorio_diario.items():
        month_key = (ano, mes)
        if month_key not in grouped_by_month:
            grouped_by_month[month_key] = {}
        grouped_by_month[month_key][dia] = len(pacientes)
    
    daily_report_md = "<h3>Pacientes minerados por dia</h3>"
    for (ano, mes) in sorted(grouped_by_month.keys(), key=lambda x: (x[0], x[1])):
        nome_mes = calendar.month_name[mes] if 1 <= mes <= 12 else "Desconhecido"
        daily_report_md += f"<h4 style='color: cyan;'>{nome_mes}/{ano}</h4>"
        daily_report_md += (
            "<table style='width: 50%; border-collapse: collapse;'>"
            "<tr>"
            "<th style='border: 1px solid #ffffff; padding: 4px;'>Dia</th>"
            "<th style='border: 1px solid #ffffff; padding: 4px;'>Pacientes</th>"
            "</tr>"
        )
        for dia in sorted(grouped_by_month[(ano, mes)].keys()):
            count = grouped_by_month[(ano, mes)][dia]
            daily_report_md += (
                f"<tr>"
                f"<td style='border: 1px solid #ffffff; padding: 4px;'>{dia}</td>"
                f"<td style='border: 1px solid #ffffff; padding: 4px;'>{count}</td>"
                f"</tr>"
            )
        daily_report_md += "</table><br>"
    
    # Cria os dois tabs: um para o relatório e outro para a lista com acesso ao PDF
    tab1, tab2 = st.tabs(["Relatório", "Lista de Pacientes Minerados com Acesso ao PDF"])
    
    def remove_html_tags(text):
        """Remove quaisquer tags HTML de uma string."""
        if not isinstance(text, str):
            return text
        return re.sub(r'<.*?>', '', text)

    with tab1:
        st.markdown(report_md, unsafe_allow_html=True)
        st.dataframe(df_para_exibicao)
        st.markdown(daily_report_md, unsafe_allow_html=True)
    
    # -------------------------------
    # SEÇÃO: Lista de Pacientes Minerados com Acesso ao PDF (segunda aba)
    # -------------------------------
    def create_download_link(pdf_bytes, file_name):
        try:
            b64 = base64.b64encode(pdf_bytes).decode()
        except Exception as e:
            return "Erro na conversão"
        return f'<a href="data:application/octet-stream;base64,{b64}" download="{file_name}">Download PDF</a>'
    
    df_display = st.session_state["pacientes_minerados_df"].copy()
    df_display["Acesso PDF"] = df_display.apply(lambda row: create_download_link(row["pdf_bytes"], row["Arquivo"]), axis=1)
    df_display = df_display.drop(columns=["pdf_bytes", "Arquivo"], errors="ignore")
    
    with tab2:
        st.markdown("### Lista de Pacientes Minerados com Acesso ao PDF:")

        # Mantém a coluna "Sentenca" com destaque para exibição
        df_display = st.session_state["pacientes_minerados_df"].copy()
        df_display["Acesso PDF"] = df_display.apply(
            lambda row: create_download_link(row["pdf_bytes"], row["Arquivo"]), axis=1
        )
        df_display = df_display.drop(columns=["pdf_bytes", "Arquivo"], errors="ignore")
        
        # Exibe com destaque na tela (a coluna "Sentenca" ainda contém HTML)
        st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

        # -------------------------------
        # DOWNLOAD DO ARQUIVO EXCEL (Pacientes Minerados) SEM FORMATAÇÃO
        # -------------------------------
        df_export = st.session_state["pacientes_minerados_df"].copy()
        # Remove as tags HTML somente para exportação
        df_export["Sentenca"] = df_export["Sentenca"].apply(remove_html_tags)
        # Remove as colunas "Arquivo" e "pdf_bytes"
        df_export = df_export.drop(columns=["Arquivo", "pdf_bytes"], errors="ignore")


        towrite = BytesIO()
        df_export.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        st.download_button(
            label="Download Excel de Pacientes Minerados (Sem Destaque)",
            data=towrite,
            file_name="pacientes_minerados_sem_formatacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # -------------------------------
    # Correlação com Internados (se arquivo fornecido)
    # -------------------------------
    if internados_file:
        internados_df = pd.read_excel(internados_file)
        correlated_df = correlacionar_pacientes_fuzzy(
            st.session_state["pacientes_minerados_df"].copy(), internados_df, threshold=70
        )
        # Save in session state for later access
        st.session_state["correlated_df"] = correlated_df
        
        st.markdown(f"### Correlação com Internados:\nForam encontrados {len(correlated_df)} pacientes minerados internados.")
        df_para_exibicao2 = st.session_state["correlated_df"].drop(columns=["Tamanho", "Sentenca"], errors="ignore")
        st.dataframe(df_para_exibicao2)
        # ... rest of your code
        towrite_corr = BytesIO()
        correlated_df.to_excel(towrite_corr, index=False, engine='openpyxl')
        towrite_corr.seek(0)
        st.download_button(
            label="Download Excel de Pacientes Internados Correlacionados",
            data=towrite_corr,
            file_name="pacientes_internados_correlacionados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # Correlação com Atendimentos PA (se arquivo fornecido)
    if atendimentos_file:
        atendimentos_df = pd.read_excel(atendimentos_file)
        correlated_pa_df = correlacionar_pacientes_fuzzy(
            st.session_state["pacientes_minerados_df"].copy(), atendimentos_df, threshold=70
        )
        st.markdown(f"### Correlação com Atendimentos PA:\nForam encontrados {len(correlated_pa_df)} pacientes minerados atendidos no PA.")
        
        # Atualiza o DataFrame principal para incluir o 'Convenio' do PA
        # Supondo que ambos os DataFrames possuem a coluna 'Paciente'
        # Se o DataFrame já tiver uma coluna 'Convenio', você pode optar por preencher os ausentes
        df_pa = correlated_pa_df[['Paciente', 'Convenio']]
        st.session_state["pacientes_minerados_df"] = st.session_state["pacientes_minerados_df"].merge(
            df_pa, on='Paciente', how='left', suffixes=('', '_pa')
        )
        
        # Verifica se a coluna "Convenio_pa" existe antes de utilizá-la
        if "Convenio_pa" in st.session_state["pacientes_minerados_df"].columns:
            st.session_state["pacientes_minerados_df"]["Convenio"] = st.session_state["pacientes_minerados_df"]["Convenio"].combine_first(
                st.session_state["pacientes_minerados_df"]["Convenio_pa"]
            )
            st.session_state["pacientes_minerados_df"].drop(columns=["Convenio_pa"], inplace=True)

        # Atualiza a exibição dos dados
        df_para_exibicao_atend = st.session_state["pacientes_minerados_df"].drop(columns=["pdf_bytes", "Arquivo", "Sentenca"], errors="ignore")
        st.dataframe(df_para_exibicao_atend)
