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
import base64  # Para download do PDF/Excel

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
    body {
        background-color: #121212;
        color: #ffffff;
    }
    .css-1d391kg, .css-1d391kg div {
        background-color: #1e1e1e;
    }
    .reportview-container .main .block-container{
        padding: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

# -------------------------------
# TÍTULO E LOGO NA SIDEBAR
# -------------------------------
st.title("Rastreador de Nódulos Pulmonares CSSJ")
if logo is not None:
    st.sidebar.image(logo, use_container_width=True)
st.sidebar.header("Selecione os Arquivos")

# -------------------------------
# EXPRESSÕES REGULARES GLOBAIS
# -------------------------------
regex_nodulo = re.compile(r"n[oó]dulo[s]?", re.IGNORECASE)
regex_tamanho = re.compile(r"\b\d+[.,]?\d*\s?(?:mm|cm)\b", re.IGNORECASE)
regex_nome = re.compile(r"(?i)paciente\s*:\s*(.+)")
regex_idade = re.compile(r"(?i)idade\s*:\s*(\d+[Aa]?\s*\d*[Mm]?)")
regex_same = re.compile(r"(?i)same\s*:\s*(\S+)")
regex_data = re.compile(r"(?i)data\s*do\s*exame\s*:\s*([\d/]+)")
regex_context = re.compile(r"\b(pulmão|pulmões|lobo|lobos)\b", re.IGNORECASE)
regex_contorno = re.compile(r"\bcontorno[s]?\b\s+(\w+)", re.IGNORECASE)
regex_calc = re.compile(r"\b(c[áa]lcificad[o]s?|c[áa]lcic[óo]s?)\b", re.IGNORECASE)
regex_calc_exceptions = re.compile(r"\b(sem calcifica[cç][ãa]o|não calcificado|parcialmente calcificado)\b", re.IGNORECASE)
regex_exclude = re.compile(r"\b(tire[oó]ide|f[ií]gado|rins?|ba[çc]o)\b", re.IGNORECASE)
regex_contorno_keywords = re.compile(r"\b(lobulad[oó]s?|bocelad[oó]s?|irregular[es]?)\b", re.IGNORECASE)
# Novas expressões para extração de "Localização" e "Densidade"
regex_localizacao = re.compile(r"\b(lobo superior|segmento superior)\b", re.IGNORECASE)
regex_densidade = re.compile(
    r"\b(s[óo]lido[s]?|semi-?s[óo]lido[s]?|semisolido[s]?|vidro\s*fosco|subs[óo]lido[s]?|partes?\s*moles?)\b",
    re.IGNORECASE
)

# -------------------------------
# FUNÇÃO PARA DESTACAR "NÓDULO" EM VERDE
# -------------------------------
def highlight_nodulo(sentence):
    pattern = r"(n[oó]dulo[s]?)"
    highlighted = re.sub(
        pattern,
        r"<span style='background-color: green;'>\1</span>",
        sentence,
        flags=re.IGNORECASE
    )
    return highlighted

# -------------------------------
# FUNÇÃO PARA DESTACAR A PALAVRA EXTRAÍDA APÓS "CONTORNO(S)" EM VERDE
# -------------------------------
def highlight_contorno(sentence):
    def repl(match):
        return f"{match.group(1)} <span style='background-color: green;'>{match.group(2)}</span>"
    return re.sub(r"(\bcontorno[s]?\b)\s+(\w+)", repl, sentence, flags=re.IGNORECASE)

# -------------------------------
# FUNÇÕES DE PROCESSAMENTO
# -------------------------------
def extrair_texto(pdf_input):
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
    dados_cabecalho = {}
    dados_cabecalho["Paciente"] = regex_nome.search(texto_completo).group(1).strip() if regex_nome.search(texto_completo) else "N/D"
    dados_cabecalho["Idade"] = regex_idade.search(texto_completo).group(1).strip() if regex_idade.search(texto_completo) else "N/D"
    dados_cabecalho["Same"] = regex_same.search(texto_completo).group(1).strip() if regex_same.search(texto_completo) else "N/D"
    dados_cabecalho["Data do Exame"] = regex_data.search(texto_completo).group(1).strip() if regex_data.search(texto_completo) else "N/D"
    return dados_cabecalho

def processar_pdfs_streamlit(pdf_files):
    relatorio_mensal = {}
    lista_nodulos = []
    for uploaded_file in pdf_files:
        file_name = uploaded_file.name
        pdf_bytes = uploaded_file.read()
        pdf_stream = BytesIO(pdf_bytes)
        texto_completo = extrair_texto(pdf_stream)
        cabecalho = extrair_informacoes(texto_completo)
        sentencas = re.split(r'(?<=[.!?])\s+', texto_completo)
        ocorrencias_validas = []
        for sentenca in sentencas:
            # Verifica se a sentença contém "nódulo" e uma palavra de contexto obrigatória
            if regex_nodulo.search(sentenca) and regex_context.search(sentenca):
                if re.search(r"\bsem\b", sentenca, re.IGNORECASE):
                    continue
                if re.search(r"\b(não\s+há|não\s+apresenta|não\s+possui|nenhum)\b", sentenca, re.IGNORECASE):
                    continue
                if regex_exclude.search(sentenca):
                    continue
                if regex_calc.search(sentenca) and not regex_calc_exceptions.search(sentenca):
                    continue
                # Extrai informações de contorno: via "contorno(s)" ou palavras-chave
                contorno_match = regex_contorno.search(sentenca)
                if contorno_match:
                    contorno_word = contorno_match.group(1)
                    sentenca = highlight_contorno(sentenca)
                else:
                    keyword_match = regex_contorno_keywords.search(sentenca)
                    if keyword_match:
                        contorno_word = keyword_match.group(0)
                    else:
                        contorno_word = "Não informado"
                # Extrai a localização, se houver (ex.: "lobo superior" ou "segmento superior")
                match_localizacao = regex_localizacao.search(sentenca)
                if match_localizacao:
                    localizacao = match_localizacao.group(0)
                else:
                    localizacao = "Não informado"
                # Extrai densidade, se presente
                match_densidade = regex_densidade.search(sentenca)
                if match_densidade:
                    densidade = match_densidade.group(0)
                else:
                    densidade = "Não informado"
                # Destaca "nódulo" em verde
                sentenca_destacada = highlight_nodulo(sentenca)
                tamanho_match = re.search(regex_tamanho, sentenca)
                tamanho_valor = tamanho_match.group(0) if tamanho_match else "Não informado"
                ocorrencias_validas.append((tamanho_valor, sentenca_destacada, contorno_word, localizacao, densidade))
        
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
            for tamanho, sentenca_destacada, contorno_word, localizacao, densidade in ocorrencias_validas:
                record = {**cabecalho,
                          "Tamanho": tamanho,
                          "Sentenca": sentenca_destacada,
                          "Arquivo": file_name,
                          "pdf_bytes": pdf_bytes,
                          "Contornos": contorno_word,
                          "Localização": localizacao,
                          "Densidade": densidade}
                lista_nodulos.append(record)
    for key in relatorio_mensal:
        relatorio_mensal[key] = len(relatorio_mensal[key])
    pacientes_minerados_df = pd.DataFrame(lista_nodulos)
    if not pacientes_minerados_df.empty:
        pacientes_minerados_df['has_measure'] = pacientes_minerados_df['Tamanho'].apply(
            lambda x: 0 if x.strip().lower() == "não informado" else 1
        )
        pacientes_minerados_df = pacientes_minerados_df.sort_values('has_measure', ascending=False)
        pacientes_minerados_df = pacientes_minerados_df.drop_duplicates(subset=['Paciente', 'Same'], keep='first')
        pacientes_minerados_df.drop(columns=['has_measure'], inplace=True)
    return relatorio_mensal, lista_nodulos, pacientes_minerados_df

def processar_pdfs_from_zip(zip_file):
    relatorio_mensal = {}
    lista_nodulos = []
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
                    if regex_nodulo.search(sentenca) and regex_context.search(sentenca):
                        if re.search(r"\bsem\b", sentenca, re.IGNORECASE):
                            continue
                        if re.search(r"\b(não\s+há|não\s+apresenta|não\s+possui|nenhum)\b", sentenca, re.IGNORECASE):
                            continue
                        if regex_exclude.search(sentenca):
                            continue
                        if regex_calc.search(sentenca) and not regex_calc_exceptions.search(sentenca):
                            continue
                        contorno_match = regex_contorno.search(sentenca)
                        if contorno_match:
                            contorno_word = contorno_match.group(1)
                            sentenca = highlight_contorno(sentenca)
                        else:
                            keyword_match = regex_contorno_keywords.search(sentenca)
                            if keyword_match:
                                contorno_word = keyword_match.group(0)
                            else:
                                contorno_word = "Não informado"
                        match_localizacao = regex_localizacao.search(sentenca)
                        if match_localizacao:
                            localizacao = match_localizacao.group(0)
                        else:
                            localizacao = "Não informado"
                        match_densidade = regex_densidade.search(sentenca)
                        if match_densidade:
                            densidade = match_densidade.group(0)
                        else:
                            densidade = "Não informado"
                        sentenca_destacada = highlight_nodulo(sentenca)
                        tamanho_match = re.search(regex_tamanho, sentenca)
                        tamanho_valor = tamanho_match.group(0) if tamanho_match else "Não informado"
                        ocorrencias_validas.append((tamanho_valor, sentenca_destacada, contorno_word, localizacao, densidade))
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
                    for tamanho, sentenca_destacada, contorno_word, localizacao, densidade in ocorrencias_validas:
                        record = {**cabecalho,
                                  "Tamanho": tamanho,
                                  "Sentenca": sentenca_destacada,
                                  "Arquivo": pdf_name,
                                  "pdf_bytes": pdf_bytes,
                                  "Contornos": contorno_word,
                                  "Localização": localizacao,
                                  "Densidade": densidade}
                        lista_nodulos.append(record)
    for key in relatorio_mensal:
        relatorio_mensal[key] = len(relatorio_mensal[key])
    pacientes_minerados_df = pd.DataFrame(lista_nodulos)
    if not pacientes_minerados_df.empty:
        pacientes_minerados_df['has_measure'] = pacientes_minerados_df['Tamanho'].apply(
            lambda x: 0 if x.strip().lower() == "não informado" else 1
        )
        pacientes_minerados_df = pacientes_minerados_df.sort_values('has_measure', ascending=False)
        pacientes_minerados_df = pacientes_minerados_df.drop_duplicates(subset=['Paciente', 'Same'], keep='first')
        pacientes_minerados_df.drop(columns=['has_measure'], inplace=True)
        pacientes_minerados_df = pacientes_minerados_df.drop(columns=["Arquivo", "pdf_bytes"], errors="ignore")
    return relatorio_mensal, lista_nodulos, pacientes_minerados_df

def correlacionar_pacientes_fuzzy(pacientes_df, internados_df, threshold=70):
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
    st.session_state["pacientes_minerados_df"] = pd.DataFrame(columns=["Paciente", "Idade", "Same", "Data do Exame", "Tamanho", "Sentenca", "pdf_bytes", "Contornos", "Localização", "Densidade"])
    st.session_state["relatorio_mensal"] = {}
    st.session_state["lista_nodulos"] = []

# -------------------------------
# INTERFACE STREAMLIT (SIDEBAR)
# -------------------------------
upload_method = st.sidebar.radio("Selecione o método de upload:", 
                                 ("Upload de PDFs", "Upload de ZIP contendo PDFs"))

if upload_method == "Upload de PDFs":
    pdf_files = st.sidebar.file_uploader("Selecione os arquivos PDF", type="pdf", accept_multiple_files=True)
else:
    zip_file = st.sidebar.file_uploader("Selecione o arquivo ZIP contendo os PDFs", type="zip")

internados_file = st.sidebar.file_uploader("Arquivo internados.xlsx (opcional)", type="xlsx")

# -------------------------------
# BOTÃO DE PROCESSAMENTO
# -------------------------------
if st.sidebar.button("Processar"):
    if upload_method == "Upload de PDFs" and pdf_files:
        with st.spinner("Processando PDFs..."):
            new_relatorio, new_lista_nodulos, new_df = processar_pdfs_streamlit(pdf_files)
        st.success("Processamento concluído!")
    elif upload_method == "Upload de ZIP" and zip_file:
        with st.spinner("Processando arquivo ZIP..."):
            new_relatorio, new_lista_nodulos, new_df = processar_pdfs_from_zip(zip_file)
        st.success("Processamento concluído!")
    else:
        st.error("Por favor, selecione os arquivos PDF ou o arquivo ZIP.")
        new_relatorio, new_lista_nodulos, new_df = {}, [], pd.DataFrame()

    if not new_df.empty:
        combined_df = pd.concat([st.session_state["pacientes_minerados_df"], new_df], ignore_index=True)
        combined_df['has_measure'] = combined_df['Tamanho'].apply(lambda x: 0 if x.strip().lower() == "não informado" else 1)
        combined_df = combined_df.sort_values('has_measure', ascending=False)
        combined_df = combined_df.drop_duplicates(subset=['Paciente', 'Same'], keep='first')
        combined_df.drop(columns=['has_measure'], inplace=True)
        st.session_state["pacientes_minerados_df"] = combined_df

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
        st.session_state["lista_nodulos"] = combined_df.to_dict(orient="records")

    report_md = "Pacientes encontrados com nódulos por mês:<br>"
    for key in sorted(st.session_state["relatorio_mensal"].keys(), key=lambda x: (x[0], x[1]) if isinstance(x, tuple) and len(x)==2 else (0,0)):
        ano, mes = key if isinstance(key, tuple) and len(key)==2 else (0, 0)
        nome_mes = calendar.month_name[mes] if 1 <= mes <= 12 else "Desconhecido"
        report_md += f"- <span style='color: green; font-size: 20px;'>{nome_mes}/{ano}</span>: {st.session_state['relatorio_mensal'].get((ano, mes), 0)} paciente(s)<br>"
    report_md += "<br>Dados dos pacientes minerados:<br>"
    
    df_para_exibicao = st.session_state["pacientes_minerados_df"].drop(columns=["pdf_bytes", "Sentenca"], errors="ignore")
    
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
    
    tab1, tab2 = st.tabs(["Relatório", "Lista de Pacientes Minerados com Acesso ao PDF"])
    
    with tab1:
        st.markdown(report_md, unsafe_allow_html=True)
        st.dataframe(df_para_exibicao)
        st.markdown(daily_report_md, unsafe_allow_html=True)
    
    def create_download_link(pdf_bytes, file_name):
        try:
            b64 = base64.b64encode(pdf_bytes).decode()
        except Exception as e:
            return "Erro na conversão"
        return f'<a href="data:application/octet-stream;base64,{b64}" download="{file_name}">Download PDF</a>'
    
    df_display = st.session_state["pacientes_minerados_df"].copy()
    df_display["Acesso PDF"] = df_display.apply(lambda row: create_download_link(row["pdf_bytes"], row["Arquivo"]), axis=1)
    df_display = df_display.drop(columns=["pdf_bytes"], errors="ignore")
    
    with tab2:
        st.markdown("### Lista de Pacientes Minerados com Acesso ao PDF:")
        st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    
    towrite = BytesIO()
    st.session_state["pacientes_minerados_df"].to_excel(towrite, index=False, engine='openpyxl')
    towrite.seek(0)
    st.download_button(
        label="Download Excel de Pacientes Minerados (Atualizado)",
        data=towrite,
        file_name="pacientes_minerados_atualizado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    if internados_file:
        internados_df = pd.read_excel(internados_file)
        correlated_df = correlacionar_pacientes_fuzzy(st.session_state["pacientes_minerados_df"].copy(), internados_df, threshold=70)
        st.markdown(f"### Correlação com Internados:\nForam encontrados {len(correlated_df)} pacientes minerados internados.")
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
