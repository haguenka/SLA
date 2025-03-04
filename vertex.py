import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Image
import os
import cv2
import io

# --- Configuração do Vertex AI ---
os.environ["GOOGLE_CLOUD_PROJECT"] = "vertex-api-452717"  # Substitua pelo seu projeto
LOCATION = "southamerica-east1"  # Região desejada

try:
    vertexai.init(project=os.environ["GOOGLE_CLOUD_PROJECT"], location=LOCATION)
    # Escolha o modelo desejado (por exemplo, "gemini-2.0-flash-001" ou "gemini-pro-vision")
    model = GenerativeModel("gemini-2.0-flash-001")
except Exception as e:
    st.error(f"Erro ao inicializar o Vertex AI: {e}")
    st.stop()

def generate_text_from_image(image_bytes, prompt):
    """
    Converte os bytes da imagem para o objeto Vertex AI e envia junto com o prompt
    para gerar uma resposta.
    """
    # Cria o objeto Image a partir dos bytes (a imagem deve estar em PNG ou JPEG)
    vertex_image = Image.from_bytes(image_bytes)
    
    # Você pode adicionar mais contexto ao prompt se desejar
    full_prompt = prompt
    try:
        response = model.generate_content([Part.from_image(vertex_image), full_prompt])
        return response.text
    except Exception as e:
        return f"Erro na análise: {e}"

def main():
    st.title("Análise de Imagem com Vertex AI")
    st.write("Carregue um arquivo de imagem (JPG ou PNG) para análise pela IA.")
    
    # Uploader para o arquivo de imagem
    uploaded_file = st.file_uploader("Escolha uma imagem", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # Lê os bytes da imagem e a exibe
        image_bytes = uploaded_file.read()
        st.image(image_bytes, caption="Imagem carregada", use_column_width=True)
        
        # Permite ao usuário definir um prompt opcional para a análise
        prompt = st.text_area(
            "Digite seu prompt para a análise",
            value="Analise a imagem e descreva os achados.",
            height=100
        )
        
        if st.button("Analisar Imagem"):
            with st.spinner("Analisando..."):
                result = generate_text_from_image(image_bytes, prompt)
            st.subheader("Resultado da Análise")
            st.write(result)

if __name__ == "__main__":
    main()
