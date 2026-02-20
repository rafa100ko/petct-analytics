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
from scipy import stats
import io

st.set_page_config(page_title="PET-CT Analytics Pro", layout="wide")

st.title("📊 Plataforma Avançada de Análise PET-CT")

# =========================
# BANCO SQLITE
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
    "Upload de Anamneses PET-CT (PDF)",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    for file in uploaded_files:
        data = extract_data_from_pdf(file)
        save_to_database(data)
    st.success("Exames salvos com sucesso!")

# =========================
# CARREGAR DADOS
# =========================

df = pd.read_sql_query("SELECT * FROM exames", conn)

if not df.empty:

    df["data_exame"] = pd.to_datetime(df["data_exame"], dayfirst=True)

    st.sidebar.header("🔎 Filtros")

    data_inicio = st.sidebar.date_input("Data inicial", df["data_exame"].min())
    data_fim = st.sidebar.date_input("Data final", df["data_exame"].max())

    df = df[
        (df["data_exame"] >= pd.to_datetime(data_inicio)) &
        (df["data_exame"] <= pd.to_datetime(data_fim))
    ]

    # =========================
    # VISÃO GERAL
    # =========================

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Exames", len(df))
    col2.metric("Idade Média", round(df["idade"].mean(), 2))
    col3.metric("IMC Médio", round(df["imc"].mean(), 2))

    st.divider()

    # =========================
    # GRÁFICOS
    # =========================

    fig_sexo = px.pie(df, names="sexo", title="Distribuição por Sexo")
    st.plotly_chart(fig_sexo, use_container_width=True)

    evolucao = df.groupby(df["data_exame"].dt.to_period("M")).size().reset_index(name="quantidade")
    evolucao["data_exame"] = evolucao["data_exame"].astype(str)
    fig_line = px.line(evolucao, x="data_exame", y="quantidade", title="Evolução Temporal")
    st.plotly_chart(fig_line, use_container_width=True)

    fig_box = px.box(df, x="sexo", y="idade", title="Idade por Sexo")
    st.plotly_chart(fig_box, use_container_width=True)

    # =========================
    # TESTE ESTATÍSTICO
    # =========================

    st.subheader("🔬 Teste Estatístico (Idade por Sexo)")

    grupos = df.groupby("sexo")["idade"].apply(list)

    if len(grupos) == 2:
        grupo1, grupo2 = grupos.iloc[0], grupos.iloc[1]
        t_stat, p_value = stats.ttest_ind(grupo1, grupo2)
        st.write(f"p-value: {round(p_value,4)}")

        if p_value < 0.05:
            st.success("Diferença estatisticamente significativa (p < 0.05)")
        else:
            st.info("Não houve diferença estatisticamente significativa")

    # =========================
    # SUMÁRIO EXECUTIVO AUTOMÁTICO
    # =========================

    st.subheader("📑 Sumário Executivo Automático")

    sexo_pred = df["sexo"].value_counts().idxmax()
    resumo = f"""
    No período analisado foram realizados {len(df)} exames PET-CT.
    A idade média foi {round(df['idade'].mean(),2)} anos.
    O sexo predominante foi {sexo_pred}.
    """

    st.write(resumo)

    # =========================
    # EXPORTAÇÃO CSV E EXCEL
    # =========================

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Baixar CSV", csv, "dados_petct.csv", "text/csv")

    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False)
    st.download_button(
        "📥 Baixar Excel",
        excel_buffer.getvalue(),
        "dados_petct.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # =========================
    # RELATÓRIO PDF
    # =========================

    if st.button("📄 Gerar Relatório PDF"):
        filename = "relatorio_petct.pdf"
        doc = SimpleDocTemplate(filename)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("RELATÓRIO PET-CT", styles["Heading1"]))
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(Paragraph(resumo, styles["Normal"]))

        doc.build(elements)

        with open(filename, "rb") as f:
            st.download_button("📥 Baixar PDF", f, file_name="relatorio_petct.pdf")

else:
    st.info("Ainda não há exames cadastrados.")
