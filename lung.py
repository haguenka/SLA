import os
import re
import fitz  # PyMuPDF
import streamlit as st
from io import BytesIO
import base64
import logging
import requests
from PIL import Image

# Configurar a página antes de qualquer outra chamada do Streamlit
st.set_page_config(page_title="Minerador de PDF - Nódulo", layout="wide")
st.title("Minerador de PDF - Busca por Nódulo e Massa")
st.sidebar.header("Upload de PDFs")
pdf_files = st.sidebar.file_uploader("Selecione os arquivos PDF", type="pdf", accept_multiple_files=True)

# Configuração do logging (opcional)
logging.basicConfig(level=logging.INFO)

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
if logo is not None:
    st.sidebar.image(logo, use_container_width=True)
st.sidebar.header("Selecione os Arquivos")

# -------------------------------
# PADRÕES DE BUSCA E REGEX
# -------------------------------
# Para "massa"
search_words_massa = [r'\bmassa[s]?\b']
# Para "nódulo" (aceita nódulo ou nodulo)
search_words_nodulo = [r'\bn[oó]dulo[s]?\b']
# Palavras de contorno e textura (usadas para validar os nódulos)
contour_words = [r'\bcontorno[s]?\b']
texture_keywords = [r'\birregular[es]?\b', r'\bespiculado[s]?\b', r'\blobulado[s]?\b', r'\bbocelado[s]?\b']
# Palavras de exclusão (evitar falsos positivos)
exclusion_words = [r'\blinfonodomegalia[s]?\b', r'\baus[eê]ncia[s]?\b', r'\bf[ií]gado?\b', r'\brim?\b', r'\rins?\b']
# Padrão para medições (ex.: 8,5 cm ou 10 mm)
measurement_pattern = re.compile(r'(\d{1,2}(?:,\d+)?\s?(?:cm|mm)?)', re.IGNORECASE)

# -------------------------------
# FUNÇÃO DE PROCESSAMENTO DO PDF
# -------------------------------
def process_pdf(file_obj, filename):
    """
    Abre o PDF a partir dos bytes, percorre cada página e realiza
    a busca e highlight conforme as condições:
      - Destaca palavras relacionadas à "massa" com cor laranja.
      - Destaca nódulos (se atender às condições) com cor amarela,
        destaca contornos e texturas com verde e medições >6mm com vermelho.
    Retorna os bytes do PDF (modificados ou não) e um flag indicando se houve alterações.
    """
    modified = False

    # Abre o PDF a partir do objeto BytesIO
    try:
        doc = fitz.open(stream=file_obj.read(), filetype="pdf")
    except Exception as e:
        st.error(f"Erro ao abrir {filename}: {e}")
        return None

    for page in doc:
        text = page.get_text("text")
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            # Bloco para "massa"
            if (any(re.search(pattern, sentence, re.IGNORECASE) for pattern in search_words_massa) and
                not any(re.search(excl, sentence, re.IGNORECASE) for excl in exclusion_words)):
                for pattern in search_words_massa:
                    regex = re.compile(pattern, re.IGNORECASE)
                    for match in regex.finditer(sentence):
                        highlight_instances = page.search_for(match.group())
                        for inst in highlight_instances:
                            annot = page.add_highlight_annot(inst)
                            annot.set_colors(stroke=(1, 0.5, 0))  # Laranja
                            annot.update()
                            modified = True

            # Bloco para "nódulo"
            if (any(re.search(pattern, sentence, re.IGNORECASE) for pattern in search_words_nodulo)
                and not any(re.search(excl, sentence, re.IGNORECASE) for excl in exclusion_words)
                and (any(re.search(c, sentence, re.IGNORECASE) for c in contour_words) or
                     any(re.search(t, sentence, re.IGNORECASE) for t in texture_keywords))):
                # Destaca nódulo com amarelo
                for pattern in search_words_nodulo:
                    regex = re.compile(pattern, re.IGNORECASE)
                    for match in regex.finditer(sentence):
                        highlight_instances = page.search_for(match.group())
                        for inst in highlight_instances:
                            annot = page.add_highlight_annot(inst)
                            annot.set_colors(stroke=(1, 1, 0))  # Amarelo
                            annot.update()
                            modified = True

                # Destaca contornos em verde
                for contour in contour_words:
                    regex = re.compile(contour, re.IGNORECASE)
                    for match in regex.finditer(sentence):
                        highlight_instances = page.search_for(match.group())
                        for inst in highlight_instances:
                            annot = page.add_highlight_annot(inst)
                            annot.set_colors(stroke=(0, 1, 0))  # Verde
                            annot.update()
                            modified = True

                # Destaca texturas em verde
                for texture in texture_keywords:
                    regex = re.compile(texture, re.IGNORECASE)
                    for match in regex.finditer(sentence):
                        highlight_instances = page.search_for(match.group())
                        for inst in highlight_instances:
                            annot = page.add_highlight_annot(inst)
                            annot.set_colors(stroke=(0, 1, 0))  # Verde
                            annot.update()
                            modified = True

                # Verifica medições e destaca em vermelho se > 6mm
                for match in measurement_pattern.finditer(sentence):
                    value = match.group()
                    number = re.findall(r'\d+,\d+|\d+', value)
                    unit = re.findall(r'cm|mm', value, re.IGNORECASE)
                    if number and unit:
                        num_value = float(number[0].replace(',', '.'))
                        if unit[0].lower() == 'cm':
                            num_value *= 10  # Converter para mm
                        if num_value > 6:
                            highlight_instances = page.search_for(match.group())
                            for inst in highlight_instances:
                                annot = page.add_highlight_annot(inst)
                                annot.set_colors(stroke=(1, 0, 0))  # Vermelho
                                annot.update()
                                modified = True

    # Salva o PDF modificado em um buffer
    out_buffer = BytesIO()
    doc.save(out_buffer)
    doc.close()
    out_buffer.seek(0)
    return out_buffer.getvalue(), modified

# -------------------------------
# FUNÇÃO PARA GERAR LINK DE DOWNLOAD
# -------------------------------
def create_download_link(pdf_bytes, filename):
    try:
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">Download {filename}</a>'
        return href
    except Exception as e:
        return f"Erro ao gerar link de download: {e}"

# -------------------------------
# PROCESSAMENTO DOS ARQUIVOS UPLOADADOS
# -------------------------------
if st.sidebar.button("Processar PDFs"):
    if pdf_files:
        results = []
        for uploaded_file in pdf_files:
            filename = uploaded_file.name
            st.write(f"Processando {filename}...")
            result = process_pdf(uploaded_file, filename)
            if result is not None:
                pdf_bytes, modified = result
                results.append((filename, pdf_bytes, modified))
        if results:
            st.success("Processamento concluído!")
            st.markdown("### Downloads dos PDFs Processados:")
            for filename, pdf_bytes, modified in results:
                if modified:
                    st.markdown(create_download_link(pdf_bytes, filename), unsafe_allow_html=True)
                else:
                    st.markdown(f"**{filename}** não teve modificações.", unsafe_allow_html=True)
        else:
            st.warning("Nenhum PDF processado.")
    else:
        st.error("Por favor, selecione pelo menos um arquivo PDF.")
