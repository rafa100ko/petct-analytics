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
st.title("📊 Plataforma Avançada de Indicadores PET-CT")

# =========================
# BANCO DE DADOS
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
    plano TEXT,
    convenio TEXT,
    medico TEXT,
    diabetes TEXT,
    quimioterapia TEXT,
    terapia_alvo TEXT,
    radioterapia TEXT,
    tabagismo TEXT,
    peso REAL,
    altura REAL,
    imc REAL,
    hgt REAL,
    reestadiamento TEXT,
    tipo_cancer TEXT,
    UNIQUE(nome, data_exame)
)
""")
conn.commit()

# =========================
# EXTRAÇÃO MELHORADA
# =========================

def extract_data_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted

    data = {}

    data["nome"] = re.search(r"Paciente:\s*(.+)", text).group(1).strip()
    data["sexo"] = "F" if "FEMININO" in text else "M"

    idade_match = re.search(r"(\d+)\s+Anos", text)
    data["idade"] = int(idade_match.group(1)) if idade_match else None

    data_exame = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    data["data_exame"] = data_exame.group(1) if data_exame else None

    plano_match = re.search(r"-\s*(.+)", text)
    data["plano"] = plano_match.group(1) if plano_match else None

    convenio = re.search(r"Convênio:(\d+)", text)
    data["convenio"] = convenio.group(1) if convenio else None

    medico = re.search(r"\n([A-Z\s]+) Espec", text)
    data["medico"] = medico.group(1).strip() if medico else None

    data["diabetes"] = "Sim" if "SIM NÃODiabetes" in text else "Não"
    data["quimioterapia"] = "Sim" if "FEZ 4 SESSÕES" in text else "Não"
    data["terapia_alvo"] = "Sim" if "OSIMERTINIBE" in text else "Não"
    data["radioterapia"] = "Sim" if "Radioterapia: SIM" in text else "Não"
    data["tabagismo"] = "Nunca Fumou" if "Nunca Fumou" in text else None

    peso = re.search(r"(\d+)Peso", text)
    data["peso"] = float(peso.group(1)) if peso else None

    altura = re.search(r"Altura:\s*(\d+)", text)
    data["altura"] = float(altura.group(1)) if altura else None

    imc = re.search(r"IMC:\s*(\d+\.?\d*)", text)
    data["imc"] = float(imc.group(1)) if imc else None

    hgt = re.search(r"=\s*(\d+)HGT", text)
    data["hgt"] = float(hgt.group(1)) if hgt else None

    data["reestadiamento"] = "Sim" if "REESTADIAMENTO" in text else "Não"
    data["tipo_cancer"] = "Pulmão" if "CÂNCER DE PULMÃO" in text else None

    return data

def save_to_database(data):
    try:
        cursor.execute("""
            INSERT INTO exames
            (nome, sexo, idade, data_exame, plano, convenio, medico,
             diabetes, quimioterapia, terapia_alvo, radioterapia,
             tabagismo, peso, altura, imc, hgt, reestadiamento, tipo_cancer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data = extract_data_from_pdf(file)
        saved = save_to_database(data)
        if saved:
            st.success(f"{data['nome']} salvo com sucesso!")
        else:
            st.warning(f"{data['nome']} já existe no banco (evitado duplicação).")

df = pd.read_sql_query("SELECT * FROM exames", conn)

if not df.empty:

    df["data_exame"] = pd.to_datetime(df["data_exame"], dayfirst=True)

    # SIDEBAR FILTROS
    st.sidebar.header("🔎 Filtros")
    inicio = st.sidebar.date_input("Data inicial", df["data_exame"].min())
    fim = st.sidebar.date_input("Data final", df["data_exame"].max())

    df = df[(df["data_exame"] >= pd.to_datetime(inicio)) &
            (df["data_exame"] <= pd.to_datetime(fim))]

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Dashboard", "📈 Indicadores", "📑 Estatísticas", "👥 Pacientes"]
    )

    # DASHBOARD
    with tab1:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Exames", len(df))
        col2.metric("Idade Média", round(df["idade"].mean(),2))
        col3.metric("IMC Médio", round(df["imc"].mean(),2))

        fig = px.line(
            df.groupby(df["data_exame"].dt.to_period("M")).size().reset_index(name="exames"),
            x="data_exame",
            y="exames",
            title="Evolução Mensal"
        )
        st.plotly_chart(fig, use_container_width=True)

    # INDICADORES
    with tab2:
        st.subheader("Distribuição por Sexo")
        st.plotly_chart(px.pie(df, names="sexo"), use_container_width=True)

        st.subheader("Boxplot Idade por Sexo")
        st.plotly_chart(px.box(df, x="sexo", y="idade"), use_container_width=True)

        numeric_df = df.select_dtypes(include=np.number)
        if len(numeric_df.columns) > 1:
            corr = numeric_df.corr()
            st.plotly_chart(px.imshow(corr, text_auto=True), use_container_width=True)

    # ESTATÍSTICAS
    with tab3:
        st.subheader("Teste t Idade por Sexo")
        grupos = df.groupby("sexo")["idade"].apply(list)
        if len(grupos) == 2:
            t_stat, p = stats.ttest_ind(grupos.iloc[0], grupos.iloc[1])
            st.write("p-value:", round(p,4))
            if p < 0.05:
                st.success("Diferença significativa")
            else:
                st.info("Sem diferença significativa")

    # PACIENTES
    with tab4:
        st.dataframe(df)

        paciente_delete = st.selectbox("Selecione paciente para excluir", df["nome"].unique())
        if st.button("Excluir Paciente"):
            cursor.execute("DELETE FROM exames WHERE nome = ?", (paciente_delete,))
            conn.commit()
            st.success("Paciente removido.")
            st.experimental_rerun()

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Baixar CSV", csv, "dados_petct.csv")

else:
    st.info("Ainda não há exames cadastrados.")
