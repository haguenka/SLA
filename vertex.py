import streamlit as st
from google import genai
from google.genai import types
import base64

def generate(image_bytes, prompt="analise a imagem"):
    # Inicializa o cliente do Vertex AI
    client = genai.Client(
        vertexai=True,
        project="vertex-api-452717",
        location="us-central1",
    )
    
    # Cria a parte da imagem a partir dos bytes carregados
    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type="image/jpeg",  # ajuste para "image/png" se necessário
    )
    
    # Instrução do sistema para definir o papel do radiologista
    si_text1 = (
        "Você é um radiologista sênior com anos de experiência. Sua função é analisar as imagens e retornar:\n"
        " - Tipo de exame\n"
        " - Se há ou não contraste venoso\n"
        " - Identificação das estruturas anatômicas contidas na imagem\n"
        " - Descrição dos achados de anormalidade\n"
        " - Possíveis diagnósticos diferenciais"
    )
    
    model = "gemini-2.0-flash-001"
    contents = [
        types.Content(
            role="user",
            parts=[
                image_part,
                types.Part.from_text(text=prompt)
            ]
        )
    ]
    
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=8192,
        response_modalities=["TEXT"],
        system_instruction=[types.Part.from_text(text=si_text1)],
    )
    
    output_text = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        output_text += chunk.text
    return output_text

def main():
    st.title("Análise de Imagem com Vertex AI")
    st.write("Carregue um arquivo de imagem para análise pela IA.")
    
    # Uploader para o arquivo de imagem
    uploaded_file = st.file_uploader("Escolha uma imagem (JPG ou PNG)", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # Lê os bytes da imagem
        image_bytes = uploaded_file.read()
        st.image(image_bytes, caption="Imagem carregada", use_column_width=True)
        
        # Permite ao usuário definir um prompt opcional
        prompt = st.text_area("Digite seu prompt para a análise (ou deixe o padrão)", value="analise a imagem", height=100)
        
        if st.button("Analisar Imagem"):
            with st.spinner("Analisando..."):
                result = generate(image_bytes, prompt)
            st.subheader("Resultado da Análise")
            st.write(result)

if __name__ == "__main__":
    main()
