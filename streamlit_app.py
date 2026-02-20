import streamlit as st
import pandas as pd
import plotly.express as px
import pdfplumber
import re
import numpy as np
import sqlite3
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

st.set_page_config(page_title="PET-CT Analytics", layout="wide")

st.title("📊 Plataforma Completa de Análise PET-CT")

# =========================
# BANCO SQLITE (PERSISTENTE)
# =========================

conn = sqlite3.connect("petct_database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS exames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    sexo TEXT,
    idade INTEGER,
    data_exame TEXT,
    peso INTEGER,
    altura INTEGER,
    imc REAL,
    tipo_cancer TEXT,
    reestadiamento TEXT
)
""")

conn.commit()

# =========================
# EXTRAÇÃO PDF
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
    data["sexo"] = "F" if sexo and sexo.group(1) == "FEMININO" else "M"

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
# SALVAR NO BANCO
# =========================

def save_to_database(data):
    cursor.execute("""
        INSERT INTO exames
        (nome, sexo, idade, data_exame, peso, altura, imc, tipo_cancer, reestadiamento)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["nome"],
        data["sexo"],
        data["idade"],
        data["data_exame"],
        data["peso"],
        data["altura"],
        data["imc"],
        data["tipo_cancer"],
        data["reestadiamento"]
    ))
    conn.commit()

# =========================
# UPLOAD
# =========================

uploaded_files = st.file_uploader(
    "Faça upload das anamneses (PDF)",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    for file in uploaded_files:
        data = extract_data_from_pdf(file)
        save_to_database(data)
    st.success("Dados salvos permanentemente!")

# =========================
# CARREGAR DADOS
# =========================

df = pd.read_sql_query("SELECT * FROM exames", conn)

if not df.empty:

    df["data_exame"] = pd.to_datetime(df["data_exame"], dayfirst=True)

    st.sidebar.header("🔎 Filtros")

    data_inicio = st.sidebar.date_input("Data inicial", df["data_exame"].min())
    data_fim = st.sidebar.date_input("Data final", df["data_exame"].max())

    df_filtrado = df[
        (df["data_exame"] >= pd.to_datetime(data_inicio)) &
        (df["data_exame"] <= pd.to_datetime(data_fim))
    ]

    st.subheader("📌 Visão Geral")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total de Exames", len(df_filtrado))
    col2.metric("Idade Média", round(df_filtrado["idade"].mean(), 2))
    col3.metric("IMC Médio", round(df_filtrado["imc"].mean(), 2))

    st.divider()

    st.subheader("📊 Distribuição por Sexo")
    fig_sexo = px.pie(df_filtrado, names="sexo")
    st.plotly_chart(fig_sexo, use_container_width=True)

    st.subheader("📈 Evolução Temporal")
    evolucao = df_filtrado.groupby(df_filtrado["data_exame"].dt.to_period("M")).size().reset_index(name="quantidade")
    evolucao["data_exame"] = evolucao["data_exame"].astype(str)
    fig_line = px.line(evolucao, x="data_exame", y="quantidade")
    st.plotly_chart(fig_line, use_container_width=True)

    st.subheader("🔥 Correlação")
    numeric_df = df_filtrado.select_dtypes(include=np.number)
    if len(numeric_df.columns) > 1:
        corr = numeric_df.corr()
        fig_corr = px.imshow(corr, text_auto=True)
        st.plotly_chart(fig_corr, use_container_width=True)

    st.subheader("📄 Dados Filtrados")
    st.dataframe(df_filtrado)

    # =========================
    # EXPORTAR CSV
    # =========================

    csv = df_filtrado.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Baixar CSV",
        csv,
        "dados_petct.csv",
        "text/csv"
    )

    # =========================
    # RELATÓRIO PDF
    # =========================

    if st.button("📑 Gerar Relatório PDF"):
        filename = "relatorio_petct.pdf"
        doc = SimpleDocTemplate(filename)
        elements = []
        styles = getSampleStyleSheet()

        summary = f"""
        No período selecionado foram realizados {len(df_filtrado)} exames PET-CT.
        A idade média foi {round(df_filtrado['idade'].mean(),2)} anos.
        """

        elements.append(Paragraph("Relatório PET-CT", styles["Heading1"]))
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(Paragraph(summary, styles["Normal"]))

        doc.build(elements)

        with open(filename, "rb") as f:
            st.download_button(
                "📥 Baixar Relatório PDF",
                f,
                file_name="relatorio_petct.pdf"
            )

else:
    st.info("Ainda não há exames cadastrados.")
