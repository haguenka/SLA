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
# Streamlit app
@st.cache_data
def load_logo(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))
# Load and display logo from GitHub
url_logo = 'https://raw.githubusercontent.com/haguenka/SLA/main/sj.png'
logo = load_logo(url_logo)
st.title("Rastreador de Cálculo Renal CSSJ")
    
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
        if not texto.strip():  # Se não houver texto, aplica OCR
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
    """
    relatorio_mensal = {}
    lista_calculos = []
    for uploaded_file in pdf_files:
        # Cria um objeto BytesIO para cada PDF
        pdf_stream = BytesIO(uploaded_file.read())
        texto_completo = extrair_texto(pdf_stream)
        cabecalho = extrair_informacoes(texto_completo)
        # Divide o texto em sentenças (usando pontuação como delimitador)
        sentencas = re.split(r'(?<=[.!?])\s+', texto_completo)
        ocorrencias_validas = []
        for sentenca in sentencas:
            linhas = sentenca.splitlines()
            valido = False
            for linha in linhas:
                if re.search(regex_calculo, linha):
                    if re.search(r'\bbiliar(?:es)?\b', linha, re.IGNORECASE):
                        continue
                    else:
                        valido = True
                        break
            if valido and re.search(regex_calculo, sentenca):
                tamanho_match = re.search(regex_tamanho, sentenca)
                if tamanho_match:
                    ocorrencias_validas.append(tamanho_match.group(0))
                else:
                    ocorrencias_validas.append("Não informado")
        if ocorrencias_validas:
            # Processa a data para o relatório mensal
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
            for tamanho in ocorrencias_validas:
                lista_calculos.append({**cabecalho, "Tamanho": tamanho})
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
    Recebe um arquivo ZIP (upload) e extrai todos os PDFs contidos nele.
    Processa cada PDF e retorna o relatório mensal, uma lista de registros e um DataFrame.
    """
    relatorio_mensal = {}
    lista_calculos = []
    zip_data = BytesIO(zip_file.read())
    with zipfile.ZipFile(zip_data, "r") as z:
        pdf_names = [name for name in z.namelist() if name.lower().endswith(".pdf")]
        for pdf_name in pdf_names:
            with z.open(pdf_name) as pdf_file:
                pdf_stream = BytesIO(pdf_file.read())
                texto_completo = extrair_texto(pdf_stream)
                cabecalho = extrair_informacoes(texto_completo)
                sentencas = re.split(r'(?<=[.!?])\s+', texto_completo)
                ocorrencias_validas = []
                for sentenca in sentencas:
                    linhas = sentenca.splitlines()
                    valido = False
                    for linha in linhas:
                        if re.search(regex_calculo, linha):
                            if re.search(r'\bbiliar(?:es)?\b', linha, re.IGNORECASE):
                                continue
                            else:
                                valido = True
                                break
                    if valido and re.search(regex_calculo, sentenca):
                        tamanho_match = re.search(regex_tamanho, sentenca)
                        if tamanho_match:
                            ocorrencias_validas.append(tamanho_match.group(0))
                        else:
                            ocorrencias_validas.append("Não informado")
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
                    for tamanho in ocorrencias_validas:
                        lista_calculos.append({**cabecalho, "Tamanho": tamanho})
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

def correlacionar_pacientes_fuzzy(pacientes_df, internados_df, threshold=70):
    """
    Correlaciona os pacientes minerados com os internados usando fuzzy matching.
    Retorna um DataFrame com os pacientes que tiveram correspondência com pontuação >= threshold.
    """
    pacientes_df['Paciente'] = pacientes_df['Paciente'].fillna("").astype(str)
    internados_df['Paciente'] = internados_df['Paciente'].fillna("").astype(str)
    pacientes_df['Paciente_lower'] = pacientes_df['Paciente'].str.lower()
    internados_df['Paciente_lower'] = internados_df['Paciente'].str.lower()
    internados_list = internados_df['Paciente_lower'].tolist()
    matched_indices = []
    for idx, row in pacientes_df.iterrows():
        nome = row['Paciente_lower']
        if not nome:
            continue
        best_match, score = process.extractOne(nome, internados_list, scorer=fuzz.ratio)
        if score >= threshold:
            matched_indices.append(idx)
    correlated_df = pacientes_df.loc[matched_indices].copy()
    correlated_df.drop(columns=['Paciente_lower'], inplace=True)
    return correlated_df

# -------------------------------
# Armazenamento em cache via session_state
# -------------------------------
if "pacientes_minerados_df" not in st.session_state:
    st.session_state["pacientes_minerados_df"] = pd.DataFrame(columns=["Paciente", "Idade", "Same", "Data do Exame", "Tamanho"])
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

# -------------------------------
# BOTÃO DE PROCESSAMENTO
# -------------------------------
if st.sidebar.button("Processar"):
    # Processamento dos novos arquivos
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
        # Reaplica a deduplicação, dando preferência a registros com medida extraída
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

        # Atualiza a lista de cálculos
        st.session_state["lista_calculos"] = combined_df.to_dict(orient="records")

    # -------------------------------
    # MONTAGEM DO RELATÓRIO
    # -------------------------------
    report_md = "### Pacientes encontrados com cálculos por mês:\n"
    for key in sorted(st.session_state["relatorio_mensal"].keys(), key=lambda x: (x[0], x[1]) if isinstance(x, tuple) and len(x)==2 else (0,0)):
        ano, mes = key if isinstance(key, tuple) and len(key)==2 else (0, 0)
        nome_mes = calendar.month_name[mes] if 1 <= mes <= 12 else "Desconhecido"
        report_md += f"- **{nome_mes}/{ano}**: {st.session_state['relatorio_mensal'].get((ano, mes), 0)} paciente(s)\n"
    report_md += "\n### Dados dos pacientes minerados:\n"
    
    st.markdown(report_md)
    st.dataframe(st.session_state["pacientes_minerados_df"])

    # -------------------------------
    # DOWNLOAD DO ARQUIVO EXCEL (Pacientes Minerados)
    # -------------------------------
    towrite = BytesIO()
    st.session_state["pacientes_minerados_df"].to_excel(towrite, index=False, engine='openpyxl')
    towrite.seek(0)
    st.download_button(
        label="Download Excel de Pacientes Minerados (Atualizado)",
        data=towrite,
        file_name="pacientes_minerados_atualizado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    # Se o arquivo de internados for carregado, realiza a correlação
    if internados_file:
        internados_df = pd.read_excel(internados_file)
        correlated_df = correlacionar_pacientes_fuzzy(st.session_state["pacientes_minerados_df"].copy(), internados_df, threshold=70)
        st.markdown(f"### Correlação com Internados:\nForam encontrados **{len(correlated_df)}** pacientes minerados internados.")
        st.dataframe(correlated_df)
        towrite_corr = BytesIO()
        correlated_df.to_excel(towrite_corr, index=False, engine='openpyxl')
        towrite_corr.seek(0)
        st.download_button(
            label="Download Excel de Pacientes Internados Correlacionados",
            data=towrite_corr,
            file_name="pacientes_internados_correlacionados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
