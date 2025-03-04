import streamlit as st
import pydicom
import numpy as np
import io
import os
import cv2
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Image

# --- Configuração Inicial ---

# 1. Autenticação Vertex AI (SECRETO!)
# Configure a autenticação da Vertex AI *ANTES* de executar o aplicativo.
# Há várias maneiras:
#    a) Variável de Ambiente GOOGLE_APPLICATION_CREDENTIALS:
#       - Baixe o arquivo JSON da chave da sua conta de serviço.
#       - Defina a variável de ambiente:
#         ```bash
#         export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service_account_key.json"
#         ```
#    b)  `gcloud auth application-default login` (se você tiver o SDK do Google Cloud instalado):
#       ```bash
#       gcloud auth application-default login
#       ```
#    c)  Dentro do próprio código (NÃO RECOMENDADO para produção, APENAS para testes rápidos):
#        ```python
#        import os
#        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/caminho/para/seu/client_secret.json"
#        ```
#        *MUITO IMPORTANTE:* Nunca coloque suas credenciais diretamente no código em um ambiente de produção!

# Defina a variável de ambiente *DENTRO* do código (MENOS SEGURO)
os.environ["GOOGLE_CLOUD_PROJECT"] = "vertex-api-452717"  # Substitua!
LOCATION = "us-central1"  # Ou a região desejada.

try:
    # Inicializa o Vertex AI (boa prática, mesmo que a variável de ambiente esteja definida)
    vertexai.init(project=os.environ["GOOGLE_CLOUD_PROJECT"], location=LOCATION)
    model = GenerativeModel("gemini-1.5-pro-002")
except Exception as e:
    st.error(f"Erro ao inicializar o modelo Gemini: {e}.")
    st.stop()

# --- Funções Auxiliares ---

def load_dicom_image(file_content):
    """Carrega e converte uma imagem DICOM para um formato utilizável."""
    try:
        dicom_file = pydicom.dcmread(io.BytesIO(file_content))
        image = dicom_file.pixel_array
        return image, dicom_file  # Retorna imagem e metadata
    except Exception as e:
        st.error(f"Erro ao ler o arquivo DICOM: {e}")
        return None, None

def window_image(image, window_center, window_width):
    """Aplica janelamento a uma imagem."""
    img_min = window_center - window_width // 2
    img_max = window_center + window_width // 2
    windowed_image = image.copy()
    windowed_image[windowed_image < img_min] = img_min
    windowed_image[windowed_image > img_max] = img_max
    return windowed_image

def normalize_image(image):
    """Normaliza uma imagem para o intervalo [0, 1]."""
    normalized_image = (image - np.min(image)) / (np.max(image) - np.min(image))
    return normalized_image

def dicom_to_vertexai_image(image, dicom_data):
    """Converte uma imagem DICOM processada para um objeto vertexai.Part.Image."""
    # 1. Janelamento (exemplo para pulmão - ajuste conforme necessário)
    windowed_image = window_image(image, -600, 1500)

    # 2. Normalização
    normalized_image = normalize_image(windowed_image)

    # 3. Conversão para uint8 (escala de cinza 0-255) - IMPORTANTE para visualização
    image_uint8 = (normalized_image * 255).astype(np.uint8)

    # 4. Se a imagem for 3D (múltiplas fatias), usa apenas uma fatia para este exemplo.
    if len(image_uint8.shape) == 3:
         image_uint8 = image_uint8[image_uint8.shape[0] // 2]  # Pega a fatia do meio

    # 5. Conversão para PNG (formato aceito pelo Gemini)
    _, encoded_image = cv2.imencode(".png", image_uint8)
    image_bytes = encoded_image.tobytes()

    # 6. Criação do objeto Image do Vertex AI
    vertex_image = Image.from_bytes(image_bytes)
    return vertex_image

def get_pixels_hu(scans):
    """Converte uma lista de fatias para unidades Hounsfield (HU)."""
    image = np.stack([s.pixel_array for s in scans])
    image = image.astype(np.int16)

    # Define pixels fora do exame para 0
    image[image == -2000] = 0

    # Converte para Hounsfield Units (HU)
    intercept = scans[0].RescaleIntercept
    slope = scans[0].RescaleSlope

    if slope != 1:
        image = slope * image.astype(np.float64)
        image = image.astype(np.int16)

    image += np.int16(intercept)
    return np.array(image, dtype=np.int16)

def generate_text_from_image(image, prompt, metadata, dicom_data):
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
        response = model.generate_content(
            [Part.from_image(image), full_prompt]
        )
        return response.text
    except Exception as e:
        st.error(f"Erro ao chamar a API do Gemini: {e}")
        return "Não foi possível obter uma resposta do modelo."

# --- Interface Streamlit ---

st.title("Análise de Tomografia Computadorizada com Gemini")

# Atualização: Carregamento de múltiplos arquivos DICOM pela sidebar
uploaded_files = st.sidebar.file_uploader(
    "Carregue um ou mais arquivos DICOM",
    type=["dcm"],
    accept_multiple_files=True
)

if uploaded_files:
    slices = []
    for file in uploaded_files:
        try:
            ds = pydicom.dcmread(io.BytesIO(file.getvalue()))
            slices.append(ds)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {file.name}: {e}")
    
    if slices:
        # Ordena as fatias, se possível (utilizando ImagePositionPatient ou SliceLocation)
        try:
            slices.sort(key=lambda ds: float(ds.ImagePositionPatient[2]) if 'ImagePositionPatient' in ds else (float(ds.SliceLocation) if 'SliceLocation' in ds else float('inf')))
        except Exception:
            st.warning("Não foi possível ordenar as fatias. Usando a ordem de carregamento.")
        
        # Exibe informações gerais do estudo
        st.write(f"{len(slices)} arquivos DICOM carregados com sucesso!")
        
        image_hu = get_pixels_hu(slices)
        metadata = f"""
        Shape da imagem: {image_hu.shape}
        Número de fatias: {len(slices)}
        Espessura da fatia: {slices[0].SliceThickness if hasattr(slices[0], 'SliceThickness') else 'N/A'}
        """
        
        prompt = st.text_area("Digite seu prompt para o Gemini:",
                              value="Descreva a imagem de tomografia computadorizada. ...",
                              height=150)
        
        if st.button("Analisar Imagem com Gemini"):
            with st.spinner("Analisando a imagem... (Isso pode levar algum tempo)"):
                # Seleciona a fatia do meio para análise (pode-se adaptar para outras lógicas)
                slice_to_analyze = slices[len(slices) // 2]
                vertex_image = dicom_to_vertexai_image(slice_to_analyze.pixel_array, slice_to_analyze)
                result = generate_text_from_image(vertex_image, prompt, metadata, slice_to_analyze)
                st.subheader("Resultado da Análise:")
                st.write(result)
    else:
        st.write("Não foi possível carregar as fatias do estudo DICOM.")
else:
    st.write("Por favor, carregue um ou mais arquivos DICOM para começar.")
