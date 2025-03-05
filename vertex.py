import streamlit as st
import google.auth
import google.auth.transport.requests
import requests
import base64

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
MODEL = "gemini-2.0-flash-001"
URL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"

def get_token_default():
    credentials, _ = google.auth.default(scopes=SCOPES)
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

def generate_text_from_image(image_bytes, prompt):
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
    token = get_token_default()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
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
    uploaded_file = st.file_uploader("Escolha uma imagem", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        image_bytes = uploaded_file.read()
        st.image(image_bytes, caption="Imagem carregada", use_column_width=True)
        prompt = st.text_area("Digite seu prompt para a análise",
                              value="Analise a imagem e descreva os achados.", height=100)
        if st.button("Analisar Imagem"):
            with st.spinner("Analisando..."):
                result = generate_text_from_image(image_bytes, prompt)
            st.subheader("Resultado da Análise")
            st.write(result)

if __name__ == "__main__":
    main()
