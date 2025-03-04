import streamlit as st
import pydicom
import numpy as np
import io
import os
import cv2
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Image

# --- Configuração Inicial ---

os.environ["GOOGLE_CLOUD_PROJECT"] = "vertex-api-452717"  # Substitua pelo seu projeto!
LOCATION = "us-central1"  # Ou a região desejada.

try:
    vertexai.init(project=os.environ["GOOGLE_CLOUD_PROJECT"], location=LOCATION)
    model = GenerativeModel("gemini-1.5-pro-002")
except Exception as e:
    st.error(f"Erro ao inicializar o modelo Gemini: {e}.")
    st.stop()

# --- Funções Auxiliares ---

def window_image(image, window_center, window_width):
    """Aplica janelamento à imagem."""
    img_min = window_center - window_width // 2
    img_max = window_center + window_width // 2
    windowed_image = np.clip(image, img_min, img_max)
    # Normaliza para 0-255
    windowed_image = ((windowed_image - img_min) / (img_max - img_min) * 255).astype(np.uint8)
    return windowed_image

def apply_zoom_and_pan(image, zoom, pan_x, pan_y):
    """Aplica zoom e pan à imagem.
       Se zoom == 1, retorna a imagem original.
       Caso contrário, recorta uma região central (ajustada pelo pan) e a redimensiona para o tamanho original."""
    if zoom == 1.0:
        return image
    h, w = image.shape
    new_w = int(w / zoom)
    new_h = int(h / zoom)
    center_x = w // 2 + pan_x
    center_y = h // 2 + pan_y
    # Garante que o recorte não ultrapasse os limites da imagem
    x1 = max(center_x - new_w // 2, 0)
    y1 = max(center_y - new_h // 2, 0)
    x2 = min(x1 + new_w, w)
    y2 = min(y1 + new_h, h)
    cropped = image[y1:y2, x1:x2]
    zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
    return zoomed

@st.cache_data(show_spinner=False)
def load_dicom_slices(file_bytes_tuple):
    """Função cacheada para ler os arquivos DICOM e retornar uma lista de slices."""
    slices = []
    for file_bytes in file_bytes_tuple:
        try:
            ds = pydicom.dcmread(io.BytesIO(file_bytes))
            slices.append(ds)
        except Exception as e:
            st.error(f"Erro ao ler um arquivo DICOM: {e}")
    return slices

def get_pixels_hu(scans):
    """Converte uma lista de fatias para unidades Hounsfield (HU)."""
    image = np.stack([s.pixel_array for s in scans])
    image = image.astype(np.int16)
    image[image == -2000] = 0
    intercept = scans[0].RescaleIntercept
    slope = scans[0].RescaleSlope
    if slope != 1:
        image = slope * image.astype(np.float64)
        image = image.astype(np.int16)
    image += np.int16(intercept)
    return np.array(image, dtype=np.int16)

def generate_text_from_image(image_obj, prompt, metadata, dicom_data):
    """Envia a imagem e o prompt para o Gemini e retorna a resposta."""
    full_prompt = f"""
    {prompt}

    Informações adicionais do estudo:
    - Modalidade: {dicom_data.Modality}
    - Espessura da fatia: {dicom_data.get('SliceThickness', 'N/A')}
    - ID do Paciente: {dicom_data.get('PatientID', 'N/A')}  (Anonimizado na prática)
    - Data do Estudo: {dicom_data.get('StudyDate', 'N/A')}
    - Instituição: {dicom_data.get('InstitutionName', 'N/A')}
    {metadata}
    """
    try:
        response = model.generate_content([Part.from_image(image_obj), full_prompt])
        return response.text
    except Exception as e:
        st.error(f"Erro ao chamar a API do Gemini: {e}")
        return "Não foi possível obter uma resposta do modelo."

# --- Interface Streamlit ---

st.title("Visualizador Interativo de Tomografia com Gemini")

# Carregamento de múltiplos arquivos DICOM pela sidebar
uploaded_files = st.sidebar.file_uploader(
    "Carregue um ou mais arquivos DICOM",
    type=["dcm"],
    accept_multiple_files=True
)

if uploaded_files:
    # Converte os arquivos para bytes e usa uma tupla para que seja hashable no cache
    file_bytes_tuple = tuple(file.getvalue() for file in uploaded_files)
    slices = load_dicom_slices(file_bytes_tuple)
    
    if slices:
        # Ordena as fatias, se possível (usando ImagePositionPatient ou SliceLocation)
        try:
            slices.sort(key=lambda ds: float(ds.ImagePositionPatient[2]) if 'ImagePositionPatient' in ds else (float(ds.SliceLocation) if 'SliceLocation' in ds else float('inf')))
        except Exception:
            st.warning("Não foi possível ordenar as fatias. Usando a ordem de carregamento.")
        
        st.write(f"{len(slices)} arquivos DICOM carregados com sucesso!")
        
        # Se houver mais de uma fatia, permite selecionar qual visualizar
        slice_idx = st.sidebar.slider("Selecione a fatia", min_value=0, max_value=len(slices)-1, value=len(slices)//2)
        selected_slice = slices[slice_idx]
        image = selected_slice.pixel_array
        
        # Janelamento: parâmetros via sliders
        default_center = int(np.median(image))
        default_width = int(np.max(image) - np.min(image))
        window_center = st.sidebar.slider("Window Center", min_value=int(np.min(image)), max_value=int(np.max(image)), value=default_center)
        window_width = st.sidebar.slider("Window Width", min_value=1, max_value=int(np.max(image)-np.min(image)), value=default_width)
        windowed_image = window_image(image, window_center, window_width)
        
        # Zoom e Pan: parâmetros via sliders
        zoom_factor = st.sidebar.slider("Zoom Factor", min_value=1.0, max_value=3.0, value=1.0, step=0.1)
        if zoom_factor > 1:
            h, w = windowed_image.shape
            max_offset_x = w // 2
            max_offset_y = h // 2
            pan_x = st.sidebar.slider("Pan X", min_value=-max_offset_x, max_value=max_offset_x, value=0)
            pan_y = st.sidebar.slider("Pan Y", min_value=-max_offset_y, max_value=max_offset_y, value=0)
        else:
            pan_x = pan_y = 0
        
        final_image = apply_zoom_and_pan(windowed_image, zoom_factor, pan_x, pan_y)
        
        st.image(final_image, caption=f"Fatia {slice_idx}", use_column_width=True)
        
        # Integração com o Gemini (opcional)
        prompt = st.text_area("Digite seu prompt para o Gemini:",
                              value="Descreva a imagem de tomografia computadorizada. ...",
                              height=150)
        metadata = f"""
        Shape da imagem: {windowed_image.shape}
        Fatia selecionada: {slice_idx}
        Window Center: {window_center}, Window Width: {window_width}
        Zoom Factor: {zoom_factor}
        """
        if st.button("Analisar Imagem com Gemini"):
            with st.spinner("Analisando a imagem... (Isso pode levar algum tempo)"):
                vertex_image = Image.from_bytes(cv2.imencode(".png", final_image)[1].tobytes())
                result = generate_text_from_image(vertex_image, prompt, metadata, selected_slice)
                st.subheader("Resultado da Análise:")
                st.write(result)
    else:
        st.write("Não foi possível carregar as fatias do estudo DICOM.")
else:
    st.write("Por favor, carregue um ou mais arquivos DICOM para começar.")
