import streamlit as st
import requests
import base64
import os
import cv2
import io

# --- Configurações ---
# Defina sua chave de API do Google na variável de ambiente ou diretamente aqui (NÃO deixe a chave em código para produção)
API_KEY = os.environ.get("GOOGLE_API_KEY") or "AIzaSyA91XZICNDN_nysC6Gj3eZEyevPMvme8xE"

# Modelo desejado e URL da API
MODEL = "gemini-2.0-flash-001"
URL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"

def generate_text_from_image(image_bytes, prompt):
    """
    Converte a imagem para base64, monta o payload e envia para a API do Generative Language.
    Retorna a resposta da análise.
    """
    # Converte a imagem para base64
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Monta o payload da requisição
    payload = {
        "instances": [
            {
                "image": image_base64,
                "prompt": prompt
            }
        ],
        "parameters": {
            "temperature": 1,
            "topP": 0.95,
            "maxOutputTokens": 8192
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    response = requests.post(URL, json=payload, headers=headers)
    
    if response.status_code == 200:
        # Supondo que a resposta retorne um JSON com o campo "predictions" e dentro dele "text"
        try:
            return response.json()["predictions"][0]["text"]
        except Exception as e:
            return f"Erro ao interpretar a resposta: {e}"
    else:
        return f"Erro na análise: {response.status_code} - {response.text}"

def main():
    st.title("Análise de Imagem com Generative Language API")
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
