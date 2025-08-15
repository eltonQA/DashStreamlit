"""
QA Dashboard App - Aplicativo para análise de métricas de QA a partir de PDFs
Versão otimizada para Streamlit Cloud
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import tempfile
import PyPDF2
import pdfplumber
import re

# Configuração da página
st.set_page_config(
    page_title="QA Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Importa a biblioteca de IA da Google (opcional)
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

# --- Configuração da API de IA ---
def configure_ai():
    """Configura a API de IA se disponível"""
    if not GENAI_AVAILABLE:
        return None
    
    # Tenta obter a chave dos secrets do Streamlit de forma segura
    api_key = None
    try:
        if hasattr(st, 'secrets'):
            api_key = st.secrets.get("GOOGLE_API_KEY", None)
    except Exception:
        # Se não conseguir acessar secrets, continua sem erro
        api_key = None
    
    # Se não encontrar nos secrets, permite inserção manual
    if not api_key:
        with st.sidebar.expander("🤖 Configuração de IA (Opcional)"):
            api_key = st.text_input(
                "Chave da API Google Gemini",
                type="password",
                help="Obtenha sua chave em https://aistudio.google.com/app/apikey"
            )
    
    if api_key and api_key.strip():
        try:
            genai.configure(api_key=api_key)
            return genai
        except Exception as e:
            st.sidebar.error(f"Erro ao configurar IA: {e}")
            return None
    
    return None

# --- Funções de extração de dados ---
def extract_text_from_pdf(pdf_file):
    """Extrai texto de um arquivo PDF"""
    text = ""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        for page_num in range(len(reader.pages)):
            text += reader.pages[page_num].extract_text() or ""
    except Exception as e:
        st.error(f"Erro ao extrair texto: {e}")
    return text

def extract_tables_from_pdf(pdf_file):
    """Extrai tabelas de um arquivo PDF"""
    tables = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    for table in page_tables:
                        # Limpa a tabela removendo linhas/colunas vazias
                        cleaned_table = []
                        for row in table:
                            cleaned_row = [cell.replace('\n', ' ') if cell else '' for cell in row]
                            if any(cell.strip() for cell in cleaned_row):
                                cleaned_table.append(cleaned_row)
                        if cleaned_table:
                            tables.append(cleaned_table)
    except Exception as e:
        st.error(f"Erro ao extrair tabelas: {e}")
    
    return tables

def extract_data_from_pdf(pdf_file):
    """Extrai dados completos de um arquivo PDF"""
    extracted_data = {
        "text": "",
        "tables": []
    }
    
    extracted_data["text"] = extract_text_from_pdf(pdf_file)
    extracted_data["tables"] = extract_tables_from_pdf(pdf_file)
    
    return extracted_data

def process_extracted_data(extracted_data):
    """Processa os dados extraídos e calcula métricas"""
    df_status = pd.DataFrame()
    kpis = {}
    
    tables = extracted_data["tables"]
    text_data = extracted_data["text"]
    
    # Palavras-chave para status de teste
    status_keywords = ["Passou", "Falhado", "Bloqueado", "Não Executado", "Falhou"]
    status_counts = {keyword: 0 for keyword in status_keywords}
    
    # Tenta encontrar dados de status nas tabelas primeiro
    for table in tables:
        for row in table:
            for cell in row:
                if cell:
                    for keyword in status_keywords:
                        if keyword.lower() in cell.lower():
                            status_counts[keyword] += 1
    
    # Converte contagens para DataFrame
    if any(status_counts.values()):
        df_status = pd.DataFrame(list(status_counts.items()), columns=["Status", "Total"])
        df_status = df_status[df_status["Total"] > 0]
    else:
        # Fallback para extração baseada em texto
        lines = text_data.split("\\n")
        status_data = []
        table_header_found = False
        
        for line in lines:
            line = line.strip()
            if "Status | Total" in line or "Status|Total" in line:
                table_header_found = True
                continue
            if table_header_found and line:
                # Tenta diferentes separadores
                for separator in ["|", "\\t", "  "]:
                    if separator in line:
                        parts = line.split(separator)
                        if len(parts) >= 2:
                            status = parts[0].strip()
                            try:
                                total = int(parts[1].strip())
                                status_data.append([status, total])
                                break
                            except ValueError:
                                pass
        
        if status_data:
            df_status = pd.DataFrame(status_data, columns=["Status", "Total"])
    
    # Calcula KPIs
    if not df_status.empty:
        total_cases = df_status["Total"].sum()
        passed_cases = df_status[df_status["Status"].str.contains("Passou", case=False, na=False)]["Total"].sum()
        executed_cases = df_status[~df_status["Status"].str.contains("Não Executado", case=False, na=False)]["Total"].sum()
        
        percent_execution = (executed_cases / total_cases) * 100 if total_cases > 0 else 0
        percent_success = (passed_cases / executed_cases) * 100 if executed_cases > 0 else 0
        
        kpis = {
            "Total de Casos de Teste": total_cases,
            "Casos Passados": passed_cases,
            "Casos Executados": executed_cases,
            "Percentual de Execucao": percent_execution,
            "Percentual de Sucesso": percent_success
        }
    
    return {
        "df_status": df_status,
        "kpis": kpis
    }

# --- Função para gerar texto com IA ---
def generate_ai_text(df_status, kpis, genai_instance):
    """Gera resumo usando IA"""
    if not genai_instance:
        return "Erro: IA não configurada ou indisponível."
    
    try:
        model = genai_instance.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
Com base nos seguintes dados de um dashboard de métricas de QA (Quality Assurance),
crie um resumo **profissional**, **claro** e **conciso** para ser publicado no Microsoft Teams.

Regras de formatação:
- Use *emojis relevantes* 📊 para tornar a leitura mais visual.
- Destaque **palavras-chave** importantes usando **duplo asterisco** para o **negrito** (padrão Markdown do Teams).
- Use frases curtas e objetivas.
- Enfatize:
    - **Total de casos**
    - **Percentual de sucesso**
    - **Distribuição dos status de teste**

### Dados de entrada:
- KPIs:
    - Total de Casos de Teste: {kpis.get("Total de Casos de Teste", 0)}
    - Casos Passados: {kpis.get("Casos Passados", 0)}
    - Percentual de Execução: {kpis.get("Percentual de Execucao", 0):.1f}%
    - Percentual de Sucesso: {kpis.get("Percentual de Sucesso", 0):.1f}%

- Distribuição por Status:
"""
        for index, row in df_status.iterrows():
            prompt += f"    - {row['Status']}: {row['Total']} casos\\n"
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro ao gerar texto: {e}"

# --- Funções de exibição ---
def display_dashboard(processed_data, genai_instance=None):
    """Exibe o dashboard principal"""
    df_status = processed_data["df_status"]
    kpis = processed_data["kpis"]
    
    # Seção de KPIs
    st.header("📈 KPIs Principais")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total de Casos de Teste",
            value=kpis.get("Total de Casos de Teste", 0)
        )
    
    with col2:
        st.metric(
            label="Casos Passados",
            value=kpis.get("Casos Passados", 0)
        )
    
    with col3:
        st.metric(
            label="Percentual de Execução",
            value=f"{kpis.get('Percentual de Execucao', 0):.1f}%"
        )
    
    with col4:
        st.metric(
            label="Percentual de Sucesso",
            value=f"{kpis.get('Percentual de Sucesso', 0):.1f}%"
        )
    
    st.markdown("---")
    
    # Seção de gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Distribuição por Status")
        fig_pie = px.pie(
            df_status,
            values='Total',
            names='Status',
            title="Total de Casos por Status",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.subheader("📈 Casos por Status")
        fig_bar = px.bar(
            df_status,
            x='Status',
            y='Total',
            title="Número de Casos por Status",
            color='Status',
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # Tabela de dados
    st.subheader("📋 Dados Detalhados")
    st.dataframe(df_status, use_container_width=True)
    
    # Funcionalidade de exportação
    st.subheader("💾 Exportar Dados")
    csv = df_status.to_csv(index=False)
    st.download_button(
        label="📥 Baixar CSV",
        data=csv,
        file_name="qa_metrics.csv",
        mime="text/csv"
    )
    
    # --- Seção de Geração de Texto com IA ---
    if genai_instance and GENAI_AVAILABLE:
        st.markdown("---")
        st.header("🤖 Gerar Resumo para Teams com IA")
        
        if st.button("✨ Gerar Resumo"):
            with st.spinner("Gerando texto com IA..."):
                ai_text = generate_ai_text(df_status, kpis, genai_instance)
                st.text_area(
                    "Texto gerado:", 
                    ai_text, 
                    height=200
                )

def display_sample_dashboard():
    """Exibe dashboard de exemplo"""
    st.header("📊 Dashboard de Exemplo")
    st.info("Este é um exemplo de como o dashboard aparecerá com dados reais.")
    
    # Dados de exemplo
    sample_data = pd.DataFrame({
        'Status': ['Passou', 'Falhou', 'Bloqueado', 'Não Executado'],
        'Total': [100, 10, 5, 20]
    })
    
    sample_kpis = {
        "Total de Casos de Teste": 135,
        "Casos Passados": 100,
        "Percentual de Execucao": 85.2,
        "Percentual de Sucesso": 87.0
    }
    
    # Seção de KPIs
    st.subheader("📈 KPIs Principais")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total de Casos de Teste",
            value=sample_kpis["Total de Casos de Teste"]
        )
    
    with col2:
        st.metric(
            label="Casos Passados",
            value=sample_kpis["Casos Passados"]
        )
    
    with col3:
        st.metric(
            label="Percentual de Execução",
            value=f"{sample_kpis['Percentual de Execucao']:.1f}%"
        )
    
    with col4:
        st.metric(
            label="Percentual de Sucesso",
            value=f"{sample_kpis['Percentual de Sucesso']:.1f}%"
        )
    
    # Seção de gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Distribuição por Status")
        fig_pie = px.pie(
            sample_data,
            values='Total',
            names='Status',
            title="Total de Casos por Status",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.subheader("📈 Casos por Status")
        fig_bar = px.bar(
            sample_data,
            x='Status',
            y='Total',
            title="Número de Casos por Status",
            color='Status',
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # Tabela de dados
    st.subheader("📋 Dados de Exemplo")
    st.dataframe(sample_data, use_container_width=True)

# --- Aplicação Principal ---
def main():
    """Função principal da aplicação"""
    st.title("📊 QA Dashboard - Análise de Métricas de Testes")
    st.markdown("---")
    
    # Configura IA se disponível
    genai_instance = configure_ai()
    
    # Sidebar para upload de arquivo
    st.sidebar.header("📁 Upload de Arquivo PDF")
    uploaded_file = st.sidebar.file_uploader(
        "Selecione um arquivo PDF com métricas de QA",
        type=['pdf'],
        help="Faça upload de um arquivo PDF contendo dados de testes de QA"
    )
    
    if uploaded_file is not None:
        # Processa o PDF
        with st.spinner("Extraindo dados do PDF..."):
            extracted_data = extract_data_from_pdf(uploaded_file)
            processed_data = process_extracted_data(extracted_data)
        
        # Exibe os resultados
        if not processed_data["df_status"].empty:
            display_dashboard(processed_data, genai_instance)
        else:
            st.error("Não foi possível extrair dados válidos do PDF. Verifique se o arquivo contém tabelas de métricas de QA.")
    else:
        # Exibe dados de exemplo para demonstração
        st.info("👈 Faça upload de um arquivo PDF para visualizar as métricas de QA")
        display_sample_dashboard()

if __name__ == "__main__":
    main()

