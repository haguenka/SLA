import streamlit as st
import json
import requests
import base64
import os
import cv2
import io
from google.oauth2 import service_account
import google.auth.transport.requests

# --- Configurações ---
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
MODEL = "gemini-2.0-flash-001"  # Atualize conforme necessário
URL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"

def get_oauth_token_google_auth(service_account_info):
    """
    Obtém o token OAuth 2.0 utilizando a biblioteca google-auth.
    """
    try:
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    except Exception as e:
        raise Exception(f"Erro ao obter token com google-auth: {e}")

def generate_text_from_image(image_bytes, prompt, service_account_info):
    """
    Converte a imagem para base64, obtém o token OAuth via google-auth e envia o payload para a API.
    """
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    payload = {
        "instances": [
            {"image": image_base64, "prompt": prompt}
        ],
        "parameters": {
            "temperature": 1,
            "topP": 0.95,
            "maxOutputTokens": 8192
        }
    }
    
    try:
        access_token = get_oauth_token_google_auth(service_account_info)
    except Exception as e:
        return f"Erro ao obter token OAuth: {e}"
    
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
    st.write("Carregue seu arquivo de credenciais da conta de serviço (JSON) e uma imagem (JPG ou PNG) para análise pela IA.")
    
    sa_file = st.file_uploader("Carregue o arquivo JSON da conta de serviço", type=["json"])
    uploaded_image = st.file_uploader("Escolha uma imagem", type=["jpg", "jpeg", "png"])
    
    if sa_file is not None and uploaded_image is not None:
        try:
            service_account_info = json.load(sa_file)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo de credenciais: {e}")
            return
        
        image_bytes = uploaded_image.read()
        st.image(image_bytes, caption="Imagem carregada", use_column_width=True)
        
        prompt = st.text_area(
            "Digite seu prompt para a análise",
            value="Analise a imagem e descreva os achados.",
            height=100
        )
        
        if st.button("Analisar Imagem"):
            with st.spinner("Analisando..."):
                result = generate_text_from_image(image_bytes, prompt, service_account_info)
            st.subheader("Resultado da Análise")
            st.write(result)
    else:
        st.info("Por favor, carregue o arquivo de credenciais e a imagem para continuar.")

if __name__ == "__main__":
    main()
