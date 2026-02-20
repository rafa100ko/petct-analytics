import streamlit as st
import pandas as pd
import plotly.express as px
import pdfplumber
import re
import numpy as np
import sqlite3
from scipy import stats
import io

st.set_page_config(page_title="PET-CT Analytics Pro", layout="wide")
st.title("📊 PET-CT Analytics | Plataforma Avançada")

# =========================
# BANCO
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
    if imc is None:
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
    if hgt is None:
        return None
    if hgt < 70:
        return "Hipoglicemia"
    elif hgt <= 140:
        return "Normal"
    else:
        return "Hiperglicemia"

# =========================
# EXTRAÇÃO PDF
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
    data["quimioterapia"] = "Sim" if "FEZ 4 SESSÕES" in text else "Não"
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
            st.warning(f"{data['nome']} já existe (duplicação evitada).")

df = pd.read_sql_query("SELECT * FROM exames", conn)

if not df.empty:

    df["data_exame"] = pd.to_datetime(df["data_exame"], dayfirst=True)
    df["imc_class"] = df["imc"].apply(classificar_imc)
    df["hgt_class"] = df["hgt"].apply(classificar_hgt)

    # =========================
    # FILTROS
    # =========================

    st.sidebar.header("🔎 Filtros")
    inicio = st.sidebar.date_input("Data inicial", df["data_exame"].min())
    fim = st.sidebar.date_input("Data final", df["data_exame"].max())

    df = df[(df["data_exame"] >= pd.to_datetime(inicio)) &
            (df["data_exame"] <= pd.to_datetime(fim))]

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Dashboard", "📈 Indicadores", "📑 Estatísticas", "👥 Pacientes"]
    )

    # =========================
    # DASHBOARD
    # =========================

    with tab1:

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Exames", len(df))
        col2.metric("Idade Média", round(df["idade"].mean(),2))
        col3.metric("IMC Médio", round(df["imc"].mean(),2))

        evolucao = df.copy()
        evolucao["mes"] = evolucao["data_exame"].dt.strftime("%Y-%m")
        evolucao = evolucao.groupby("mes").size().reset_index(name="exames")

        fig_line = px.line(evolucao, x="mes", y="exames", title="Evolução Mensal")
        st.plotly_chart(fig_line, use_container_width=True)

        fig_pie = px.pie(df, names="sexo", title="Distribuição por Sexo")
        st.plotly_chart(fig_pie, use_container_width=True)

    # =========================
    # INDICADORES
    # =========================

    with tab2:

        st.subheader("Classificação IMC")
        st.plotly_chart(px.pie(df, names="imc_class"), use_container_width=True)

        st.subheader("Classificação Glicêmica (HGT)")
        st.plotly_chart(px.pie(df, names="hgt_class"), use_container_width=True)

        st.subheader("Boxplot Idade por Sexo")
        st.plotly_chart(px.box(df, x="sexo", y="idade"), use_container_width=True)

        numeric_df = df.select_dtypes(include=np.number)
        if len(numeric_df.columns) > 1:
            corr = numeric_df.corr()
            fig_corr = px.imshow(corr, text_auto=True)
            st.plotly_chart(fig_corr, use_container_width=True)

    # =========================
    # ESTATÍSTICAS
    # =========================

    with tab3:

        st.subheader("Teste t Idade por Sexo")
        grupos = df.groupby("sexo")["idade"].apply(list)

        if len(grupos) == 2:
            t_stat, p = stats.ttest_ind(grupos.iloc[0], grupos.iloc[1])
            st.write("p-value:", round(p,4))

            if p < 0.05:
                st.success("Diferença estatisticamente significativa")
            else:
                st.info("Sem diferença significativa")

    # =========================
    # PACIENTES
    # =========================

    with tab4:

        st.dataframe(df)

        paciente_id = st.selectbox("Selecione ID para excluir", df["id"])

        if st.button("Excluir Paciente"):
            cursor.execute("DELETE FROM exames WHERE id = ?", (int(paciente_id),))
            conn.commit()
            st.success("Paciente removido.")
            st.experimental_rerun()

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Baixar CSV", csv, "dados_petct.csv")

else:
    st.info("Ainda não há exames cadastrados.")
