import streamlit as st
import pandas as pd
import plotly.express as px
import pdfplumber
import re
import numpy as np
import sqlite3
from scipy import stats

st.set_page_config(page_title="PET-CT Analytics Pro", layout="wide")
st.title("📊 PET-CT Analytics | Painel Analítico")

# =========================
# BANCO (SEM RESET)
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
    peso REAL,
    altura REAL,
    imc REAL,
    hgt REAL,
    diabetes TEXT,
    quimioterapia TEXT,
    radioterapia TEXT,
    reestadiamento TEXT,
    UNIQUE(nome, data_exame)
)
""")
conn.commit()

# =========================
# CLASSIFICAÇÕES
# =========================

def classificar_imc(imc):
    if pd.isna(imc):
        return None
    if imc < 18.5:
        return "Baixo peso"
    elif imc < 25:
        return "Normal"
    elif imc < 30:
        return "Sobrepeso"
    else:
        return "Obesidade"

def classificar_hgt(hgt):
    if pd.isna(hgt):
        return None
    if hgt < 70:
        return "Hipoglicemia"
    elif hgt <= 140:
        return "Normal"
    else:
        return "Hiperglicemia"

# =========================
# EXTRAÇÃO
# =========================

def extract_data(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t

    data = {}

    nome = re.search(r"Paciente:\s*(.+)", text)
    data["nome"] = nome.group(1).strip() if nome else None

    data["sexo"] = "F" if "FEMININO" in text else "M"

    idade = re.search(r"(\d+)\s+Anos", text)
    data["idade"] = int(idade.group(1)) if idade else None

    data_exame = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    data["data_exame"] = data_exame.group(1) if data_exame else None

    peso = re.search(r"(\d+)Peso", text)
    data["peso"] = float(peso.group(1)) if peso else None

    altura = re.search(r"Altura:\s*(\d+)", text)
    data["altura"] = float(altura.group(1)) if altura else None

    imc = re.search(r"IMC:\s*(\d+\.?\d*)", text)
    data["imc"] = float(imc.group(1)) if imc else None

    hgt = re.search(r"=\s*(\d+)HGT", text)
    data["hgt"] = float(hgt.group(1)) if hgt else None

    data["diabetes"] = "Sim" if "Diabetes: SIM" in text else "Não"
    data["quimioterapia"] = "Sim" if "FEZ" in text else "Não"
    data["radioterapia"] = "Sim" if "Radioterapia: SIM" in text else "Não"
    data["reestadiamento"] = "Sim" if "REESTADIAMENTO" in text else "Não"

    return data

def save_data(data):
    try:
        cursor.execute("""
        INSERT INTO exames
        (nome, sexo, idade, data_exame, peso, altura, imc, hgt,
         diabetes, quimioterapia, radioterapia, reestadiamento)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(data.values()))
        conn.commit()
        return True
    except:
        return False

# =========================
# UPLOAD
# =========================

uploaded_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        data = extract_data(file)
        saved = save_data(data)
        if saved:
            st.success(f"{data['nome']} salvo com sucesso.")
        else:
            st.warning(f"{data['nome']} já existe.")

df = pd.read_sql_query("SELECT * FROM exames", conn)

if not df.empty:

    df["data_exame"] = pd.to_datetime(df["data_exame"], dayfirst=True)
    df["imc_class"] = df["imc"].apply(classificar_imc)
    df["hgt_class"] = df["hgt"].apply(classificar_hgt)

    # =========================
    # DASHBOARD
    # =========================

    st.header("📊 Dashboard Executivo")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Exames", len(df))
    col2.metric("Idade Média", round(df["idade"].mean(),2))
    col3.metric("IMC Médio", round(df["imc"].mean(),2))
    col4.metric("HGT Médio", round(df["hgt"].mean(),2))

    st.divider()

    # Evolução Temporal
    evolucao = df.copy()
    evolucao["mes"] = evolucao["data_exame"].dt.strftime("%Y-%m")
    evolucao = evolucao.groupby("mes").size().reset_index(name="exames")

    st.subheader("Evolução Mensal")
    st.plotly_chart(px.line(evolucao, x="mes", y="exames"), use_container_width=True)

    # =========================
    # INDICADORES
    # =========================

    st.header("📈 Indicadores Clínicos")

    colA, colB = st.columns(2)

    with colA:
        st.subheader("Distribuição IMC")
        st.plotly_chart(px.pie(df, names="imc_class"), use_container_width=True)

    with colB:
        st.subheader("Distribuição Glicêmica")
        st.plotly_chart(px.pie(df, names="hgt_class"), use_container_width=True)

    st.subheader("Boxplot Idade por Sexo")
    st.plotly_chart(px.box(df, x="sexo", y="idade"), use_container_width=True)

    # =========================
    # ESTATÍSTICAS COMPLETAS
    # =========================

    st.header("📑 Estatísticas")

    st.subheader("Estatísticas Descritivas")

    desc = df[["idade","imc","hgt"]].describe().T
    desc["mediana"] = df[["idade","imc","hgt"]].median()
    desc["desvio_padrao"] = df[["idade","imc","hgt"]].std()

    st.dataframe(desc)

    st.subheader("Correlação")

    numeric_df = df[["idade","imc","hgt"]]
    corr = numeric_df.corr()
    st.plotly_chart(px.imshow(corr, text_auto=True), use_container_width=True)

    st.subheader("Teste t - Idade por Sexo")

    grupos = df.groupby("sexo")["idade"].apply(list)
    if len(grupos) == 2:
        t_stat, p = stats.ttest_ind(grupos.iloc[0], grupos.iloc[1])
        st.write("p-value:", round(p,4))

        if p < 0.05:
            st.success("Diferença significativa entre sexos")
        else:
            st.info("Sem diferença significativa")

    # =========================
    # SUMÁRIO EXECUTIVO
    # =========================

    st.header("📝 Sumário Executivo")

    sexo_pred = df["sexo"].value_counts().idxmax()
    tendencia = "aumento" if evolucao["exames"].iloc[-1] > evolucao["exames"].iloc[0] else "estabilidade"

    st.write(f"""
    No período analisado foram realizados {len(df)} exames PET-CT.
    A idade média foi {round(df['idade'].mean(),2)} anos.
    O sexo predominante foi {sexo_pred}.
    Observou-se {tendencia} na demanda ao longo dos meses.
    """)

    # =========================
    # EXPORTAÇÃO
    # =========================

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Baixar Base CSV", csv, "petct_dados.csv")

else:
    st.info("Ainda não há exames cadastrados.")
