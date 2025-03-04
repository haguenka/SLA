import streamlit as st
import requests
import base64
import os
from google.oauth2 import service_account
import google.auth.transport.requests

# --- Configurações ---
SERVICE_ACCOUNT_FILE = "Users/henrique_guenka/Downloads/client_secret_175959353866-19tf5mtk2q0nu0daahjvnnf4pqk624k0.apps.googleusercontent.com (1).json"  # Atualize com o caminho correto
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
MODEL = "gemini-2.0-flash-001"  # Atualize conforme necessário
URL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"

def get_oauth_token():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

def generate_text_from_image(image_bytes, prompt):
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
    
    # Obtém o token OAuth 2.0
    access_token = get_oauth_token()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.post(URL, json=payload, headers=headers)
    
    if response.status_code == 200:
        try:
            return response.json()["predictions"][0]["text"]
        except Exception as e:
            return f"Erro ao interpretar a resposta: {e}"
    else:
        return f"Erro na análise: {response.status_code} - {response.text}"

def main():
    st.title("Análise de Imagem com Generative Language API")
    st.write("Carregue um arquivo de imagem (JPG ou PNG) para análise pela IA.")
    
    uploaded_file = st.file_uploader("Escolha uma imagem", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        image_bytes = uploaded_file.read()
        st.image(image_bytes, caption="Imagem carregada", use_column_width=True)
        
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
