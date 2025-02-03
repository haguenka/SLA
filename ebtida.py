import streamlit as st

# Configura a página
st.set_page_config(
    page_title="Calculadora de EBITDA - Radiologia",
    page_icon="🩺",
    layout="centered"
)

# CSS customizado para uma UI moderna e fancy
st.markdown(
    """
    <style>
    /* Define a cor de fundo da página */
    .stApp {
        background-color: #f0f2f6;
    }
    /* Estilização dos botões */
    .stButton>button {
        background-color: #1f77b4;
        color: white;
        border-radius: 8px;
        padding: 0.5em 1em;
        border: none;
        font-size: 16px;
        font-weight: bold;
    }
    /* Estilização do título */
    .title {
        font-size: 2.5em;
        color: #333333;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True
)

# Título e descrição
st.markdown('<p class="title">Calculadora de EBITDA para Serviço de Radiologia</p>', unsafe_allow_html=True)
st.write("Preencha os campos abaixo e clique em **Calcular EBITDA** para obter o resultado.")

# Criação do formulário para entrada de dados
with st.form("formulario"):
    col1, col2 = st.columns(2)
    with col1:
        receita = st.number_input(
            "Receita Total (R$):", 
            min_value=0.0, 
            value=0.0, 
            step=1000.0, 
            format="%.2f"
        )
        despesas = st.number_input(
            "Despesas Operacionais (R$):", 
            min_value=0.0, 
            value=0.0, 
            step=1000.0, 
            format="%.2f"
        )
    with col2:
        depreciacao = st.number_input(
            "Depreciação (R$):", 
            min_value=0.0, 
            value=0.0, 
            step=1000.0, 
            format="%.2f"
        )
        amortizacao = st.number_input(
            "Amortização (R$):", 
            min_value=0.0, 
            value=0.0, 
            step=1000.0, 
            format="%.2f"
        )
    
    calcular = st.form_submit_button("Calcular EBITDA")

# Cálculo do EBITDA e exibição do resultado
if calcular:
    ebitda = (receita - despesas) + depreciacao + amortizacao
    st.success(f"**EBITDA calculado:** R$ {ebitda:,.2f}")
