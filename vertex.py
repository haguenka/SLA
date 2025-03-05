import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Image
import os
import time
from vertexai.errors import VertexAiError

# --- Configuração do Vertex AI ---
try:
    PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]  # Get from environment variable
    LOCATION = "us-central1"  # Região desejada

    vertexai.init(project=PROJECT_ID, location=LOCATION)
    model = GenerativeModel("gemini-pro-vision")
except VertexAiError as e:
    st.error(f"Erro ao inicializar o Vertex AI: {e}")
    st.stop()
except KeyError:
    st.error("A variável de ambiente GOOGLE_CLOUD_PROJECT não está definida.")
    st.stop()

def generate_text_from_image(image_bytes, prompt):
    """
    Converte os bytes da imagem para o objeto Vertex AI e envia junto com o prompt
    para gerar uma resposta.
    """
    try:
        vertex_image = Image.from_bytes(image_bytes)
        response = model.generate_content([Part.from_image(vertex_image), prompt])
        return response.text
    except VertexAiError as e:
        return f"Erro na análise com Vertex AI: {e}"
    except Exception as e:
        return f"Erro inesperado: {e}"

def main():
    st.title("Análise de Imagem com Vertex AI")
    st.write("Carregue um arquivo de imagem (JPG ou PNG) para análise pela IA.")

    uploaded_file = st.file_uploader("Escolha uma imagem", type=["jpg", "png"])

    if uploaded_file is not None:
        image_bytes = uploaded_file.read()
        st.image(image_bytes, caption="Imagem carregada", use_container_width=True)

        prompt = st.text_area(
            "Digite seu prompt para a análise",
            value="Analise a imagem e descreva os achados.",
            height=100,
        )

        if st.button("Analisar Imagem"):
            with st.spinner("Analisando..."):
                start_time = time.time()
                result = generate_text_from_image(image_bytes, prompt)
                elapsed_time = time.time() - start_time
            st.subheader("Resultado da Análise")
            st.write(result)
            st.write(f"Tempo de resposta: {elapsed_time:.2f} segundos")
    if st.button("Clear"):
        st.session_state.clear()
        st.rerun()

if __name__ == "__main__":
    main()
