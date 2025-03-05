import streamlit as st
import requests
import base64
import os
import json
import time
import jwt  # pip install pyjwt
import cv2
import io
import requests

def get_oauth_token_manual(service_account_info):
    """
    Gera um JWT manualmente usando PyJWT (incluindo o header "kid") e troca por um token OAuth 2.0.
    """
    private_key = service_account_info["private_key"]
    client_email = service_account_info["client_email"]
    token_uri = service_account_info["token_uri"]
    now = int(time.time())
    
    payload = {
        "iss": client_email,
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,  # Token válido por 1 hora
    }
    
    # Inclua o header "kid" com o ID da chave privada
    jwt_headers = {
        "kid": service_account_info["private_key_id"]
    }
    
    # Gera o JWT usando RS256 e incluindo o header "kid"
    signed_jwt = jwt.encode(payload, private_key, algorithm="RS256", headers=jwt_headers)
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": signed_jwt,
    }
    
    response = requests.post(token_uri, headers=headers, data=data)
    
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Falha ao obter token: {response.status_code} {response.text}")

def generate_text_from_image(image_bytes, prompt, service_account_info):
    """
    Converte a imagem para base64, obtém o token manualmente e envia o payload para a API.
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
        access_token = get_oauth_token_manual(service_account_info)
    except Exception as e:
        return f"Erro ao obter token OAuth manual: {e}"
    
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
