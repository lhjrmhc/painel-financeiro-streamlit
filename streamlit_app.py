import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime

st.set_page_config(page_title="Painel Financeiro Interativo", layout="wide")

# --- Funções de processamento ---
def parse_csv(df):
    # Garantir colunas essenciais
    if 'data' not in df.columns:
        st.error("CSV inválido: coluna 'data' não encontrada.")
        st.stop()
    if 'valor' not in df.columns:
        st.error("CSV inválido: coluna 'valor' não encontrada.")
        st.stop()
    # Normaliza
    df.columns = [c.strip().lower() for c in df.columns]
    if 'descricao' not in df.columns:
        df['descricao'] = 'N/A'
    if 'tipo' not in df.columns:
        df['tipo'] = df['valor'].apply(lambda x: 'Entrada' if x > 0 else 'Saída')
    if 'categoria' not in df.columns:
        df['categoria'] = 'N/A'
    # Converte tipos
    df['data'] = pd.to_datetime(df['data'], dayfirst=True, errors='coerce')
    df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0.0)
    return df


def parse_pdf(file):
    text = ''
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ''
    records = []
    current_date = None
    for line in text.splitlines():
        line = line.strip()
        date_match = re.match(r"^(\d{2}/\d{2}/\d{4})$", line)
        if date_match:
            try:
                current_date = datetime.strptime(date_match.group(1), '%d/%m/%Y')
            except:
                current_date = None
            continue
        val_match = re.search(r"R\$\s*([\d\.,]+)", line)
        if val_match and current_date:
            num = val_match.group(1).replace('.', '').replace(',', '.')
            try:
                valor = float(num)
            except:
                continue
            desc = line[:val_match.start()].strip() or 'N/A'
            records.append({
                'data': current_date,
                'descricao': desc,
                'valor': valor,
                'tipo': 'Entrada' if valor > 0 else 'Saída',
                'categoria': 'N/A'
            })
    return pd.DataFrame(records)

# --- Interface ---
st.title("📊 Painel Financeiro Interativo")

uploaded = st.file_uploader(
    "Envie CSV, XLSX ou PDF de extrato bancário", type=["csv","xlsx","xls","pdf"]
)
if uploaded:
    fname = uploaded.name.lower()
    if fname.endswith('.csv'):
        df = pd.read_csv(uploaded, sep=';', encoding='latin1')
        df = parse_csv(df)
    elif fname.endswith(('.xlsx', '.xls')):
        try:
            df = pd.read_excel(uploaded, engine='openpyxl')
        except:
            df = pd.read_excel(uploaded)
        df = parse_csv(df)
    elif fname.endswith('.pdf'):
        df = parse_pdf(uploaded)
        df = parse_csv(df)
    else:
        st.error("Formato não suportado. Envie CSV, XLSX ou PDF.")
        st.stop()

    # Filtros na sidebar
    st.sidebar.header("Filtros")
    min_date, max_date = df['data'].min(), df['data'].max()
    start, end = st.sidebar.date_input("Período", [min_date, max_date])
    cat_options = ['All'] + sorted(df['categoria'].unique().tolist())
    tipo_options = ['All'] + sorted(df['tipo'].unique().tolist())
    selected_cat = st.sidebar.selectbox("Categoria", cat_options)
    selected_tipo = st.sidebar.selectbox("Tipo", tipo_options)
    mask = (df['data'] >= pd.to_datetime(start)) & (df['data'] <= pd.to_datetime(end))
    if selected_cat != 'All': mask &= df['categoria'] == selected_cat
    if selected_tipo != 'All': mask &= df['tipo'] == selected_tipo
    df_filtered = df[mask]

    # Métricas
    rec = df_filtered[df_filtered['valor'] > 0]['valor'].sum()
    desp = -df_filtered[df_filtered['valor'] < 0]['valor'].sum()
    lucro = rec - desp
    col1, col2, col3 = st.columns(3)
    col1.metric("Receita", f"R$ {rec:,.2f}")
    col2.metric("Despesa", f"R$ {desp:,.2f}")
    col3.metric("Lucro", f"R$ {lucro:,.2f}")

    st.markdown("---")
    # Gráficos
    st.subheader("Evolução do Valor no Tempo")
    series_time = df_filtered.groupby(df_filtered['data'].dt.date)['valor'].sum()
    st.line_chart(series_time)

    st.subheader("Distribuição por Categoria")
    series_cat = df_filtered.groupby('categoria')['valor'].sum()
    st.bar_chart(series_cat)

    st.subheader("Top 5 Serviços (Despesas)")
    top5 = df_filtered[df_filtered['valor'] < 0].groupby('descricao')['valor'].sum().abs().nlargest(5)
    st.bar_chart(top5)

    st.subheader("Transações Filtradas")
    st.dataframe(df_filtered)
else:
    st.info("Por favor, envie um arquivo CSV, XLSX ou PDF para começar.")
