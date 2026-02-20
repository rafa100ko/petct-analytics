import streamlit as st
import pandas as pd
import plotly.express as px
import pdfplumber
import re
import numpy as np

st.set_page_config(page_title="PET-CT Analytics", layout="wide")

st.title("📊 Plataforma de Análise PET-CT")

# =========================
# FUNÇÃO DE EXTRAÇÃO
# =========================

def extract_data_from_pdf(file):
    text = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted

    data = {}

    nome = re.search(r"Paciente:\s*(.+)", text)
    data["nome"] = nome.group(1).strip() if nome else None

    sexo = re.search(r"\b(FEMININO|MASCULINO)\b", text)
    if sexo:
        data["sexo"] = "F" if sexo.group(1) == "FEMININO" else "M"
    else:
        data["sexo"] = None

    idade = re.search(r"(\d+)\s+Anos", text)
    data["idade"] = int(idade.group(1)) if idade else None

    data_exame = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    data["data_exame"] = data_exame.group(1) if data_exame else None

    peso = re.search(r"(\d+)Peso", text)
    data["peso"] = int(peso.group(1)) if peso else None

    altura = re.search(r"Altura:\s*(\d+)", text)
    data["altura"] = int(altura.group(1)) if altura else None

    imc = re.search(r"IMC:\s*(\d+\.?\d*)", text)
    data["imc"] = float(imc.group(1)) if imc else None

    if "CÂNCER DE PULMÃO" in text:
        data["tipo_cancer"] = "Pulmão"
    else:
        data["tipo_cancer"] = None

    data["reestadiamento"] = "Sim" if "REESTADIAMENTO" in text else "Não"

    return data


# =========================
# BANCO TEMPORÁRIO
# =========================

if "database" not in st.session_state:
    st.session_state.database = pd.DataFrame()

uploaded_files = st.file_uploader(
    "Faça upload das anamneses (PDF)",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    new_data = []

    for file in uploaded_files:
        data = extract_data_from_pdf(file)
        new_data.append(data)

    new_df = pd.DataFrame(new_data)

    st.session_state.database = pd.concat(
        [st.session_state.database, new_df],
        ignore_index=True
    )

df = st.session_state.database

# =========================
# DASHBOARD
# =========================

if not df.empty:

    st.subheader("📌 Visão Geral")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total de Exames", len(df))
    col2.metric("Idade Média", round(df["idade"].mean(), 2))
    col3.metric("IMC Médio", round(df["imc"].mean(), 2))

    st.divider()

    st.subheader("📊 Distribuição por Sexo")
    fig_sexo = px.pie(df, names="sexo", title="Distribuição por Sexo")
    st.plotly_chart(fig_sexo, use_container_width=True)

    st.subheader("📈 Idade dos Pacientes")
    fig_idade = px.histogram(df, x="idade", nbins=10)
    st.plotly_chart(fig_idade, use_container_width=True)

    st.subheader("📦 IMC por Sexo")
    fig_box = px.box(df, x="sexo", y="imc")
    st.plotly_chart(fig_box, use_container_width=True)

    # =========================
    # HEATMAP DE CORRELAÇÃO
    # =========================

    st.subheader("🔥 Correlação entre Indicadores")

    numeric_df = df.select_dtypes(include=np.number)

    if len(numeric_df.columns) > 1:
        corr = numeric_df.corr()
        fig_corr = px.imshow(corr, text_auto=True)
        st.plotly_chart(fig_corr, use_container_width=True)

    st.subheader("📄 Dados Extraídos")
    st.dataframe(df)

    if st.button("🗑 Limpar Base"):
        st.session_state.database = pd.DataFrame()
        st.experimental_rerun()

else:
    st.info("Faça upload de PDFs para iniciar a análise.")
