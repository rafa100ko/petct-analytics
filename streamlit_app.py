import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pdfplumber
import re
import numpy as np
import sqlite3
from scipy import stats
import io
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

st.set_page_config(page_title="PET-CT Analytics PRO", layout="wide")
st.title("📊 PET-CT Analytics PRO")

# ================= BANCO =================

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

# ================= FUNÇÕES =================

def classificar_imc(imc):
    if pd.isna(imc): return None
    if imc < 18.5: return "Baixo peso"
    elif imc < 25: return "Normal"
    elif imc < 30: return "Sobrepeso"
    else: return "Obesidade"

def classificar_hgt(hgt):
    if pd.isna(hgt): return None
    if hgt < 70: return "Hipoglicemia"
    elif hgt <= 140: return "Normal"
    else: return "Hiperglicemia"

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

# ================= UPLOAD =================

uploaded_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        data = extract_data(file)
        saved = save_data(data)
        if saved:
            st.success(f"{data['nome']} salvo.")
        else:
            st.warning(f"{data['nome']} já existe.")

df = pd.read_sql_query("SELECT * FROM exames", conn)

if not df.empty:

    df["data_exame"] = pd.to_datetime(df["data_exame"], dayfirst=True)
    df["imc_class"] = df["imc"].apply(classificar_imc)
    df["hgt_class"] = df["hgt"].apply(classificar_hgt)

    # ================= SIDEBAR FILTROS =================

    st.sidebar.header("Filtros")

    inicio = st.sidebar.date_input("Data inicial", df["data_exame"].min())
    fim = st.sidebar.date_input("Data final", df["data_exame"].max())

    df = df[(df["data_exame"] >= pd.to_datetime(inicio)) &
            (df["data_exame"] <= pd.to_datetime(fim))]

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Dashboard", "Indicadores", "Estatísticas", "Pacientes", "Relatório"]
    )

    # ================= DASHBOARD =================

    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Exames", len(df))
        col2.metric("Idade Média", round(df["idade"].mean(),2))
        col3.metric("IMC Médio", round(df["imc"].mean(),2))
        col4.metric("HGT Médio", round(df["hgt"].mean(),2))

        evolucao = df.copy()
        evolucao["mes"] = evolucao["data_exame"].dt.strftime("%Y-%m")
        evolucao = evolucao.groupby("mes").size().reset_index(name="exames")

        st.plotly_chart(px.line(evolucao, x="mes", y="exames"), use_container_width=True)

        st.plotly_chart(px.histogram(df, x="idade"), use_container_width=True)
        st.plotly_chart(px.box(df, x="sexo", y="imc"), use_container_width=True)

    # ================= INDICADORES =================

    with tab2:
        st.plotly_chart(px.pie(df, names="imc_class"), use_container_width=True)
        st.plotly_chart(px.pie(df, names="hgt_class"), use_container_width=True)

        corr, p = stats.pearsonr(df["idade"].dropna(), df["imc"].dropna())
        st.write(f"Correlação idade vs IMC: r={round(corr,2)} | p={round(p,4)}")

        heat = df[["idade","imc","hgt"]].corr()
        st.plotly_chart(px.imshow(heat, text_auto=True), use_container_width=True)

    # ================= ESTATÍSTICAS =================

    with tab3:
        desc = df[["idade","imc","hgt"]].describe().T
        desc["Mediana"] = df[["idade","imc","hgt"]].median()
        desc["DP"] = df[["idade","imc","hgt"]].std()
        st.dataframe(desc)

        grupos = df.groupby("sexo")["idade"].apply(list)
        if len(grupos)==2:
            t,p = stats.ttest_ind(grupos.iloc[0], grupos.iloc[1])
            st.write("Teste t (idade por sexo) p=", round(p,4))

    # ================= PACIENTES =================

    with tab4:
        busca = st.text_input("Buscar paciente")
        df_busca = df[df["nome"].str.contains(busca, case=False)] if busca else df
        st.dataframe(df_busca)

        paciente_id = st.selectbox("Excluir ID", df_busca["id"])
        if st.button("Excluir"):
            cursor.execute("DELETE FROM exames WHERE id=?", (int(paciente_id),))
            conn.commit()
            st.success("Excluído.")
            st.rerun()

    # ================= RELATÓRIO =================

    with tab5:
        sexo_pred = df["sexo"].value_counts().idxmax()
        resumo = f"""
        Foram analisados {len(df)} exames PET-CT.
        Idade média: {round(df['idade'].mean(),2)} anos.
        Sexo predominante: {sexo_pred}.
        Correlação idade-IMC: {round(corr,2)}.
        """

        st.write(resumo)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "dados_petct.csv")

        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        st.download_button("Download Excel", excel_buffer.getvalue(), "dados_petct.xlsx")

        if st.button("Gerar PDF"):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer)
            styles = getSampleStyleSheet()
            elements = []
            elements.append(Paragraph("Relatório PET-CT", styles["Heading1"]))
            elements.append(Spacer(1, 0.5 * inch))
            elements.append(Paragraph(resumo, styles["Normal"]))
            doc.build(elements)
            st.download_button("Download PDF", buffer.getvalue(), "relatorio.pdf")

else:
    st.info("Nenhum exame cadastrado.")
