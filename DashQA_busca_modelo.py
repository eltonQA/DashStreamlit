import streamlit as st
import pandas as pd
import plotly.express as px
import os
import PyPDF2
import re
import random
import google.generativeai as genai

# --- AJUSTE 1: Configuração da página no topo do script ---
# É uma boa prática do Streamlit chamar isso apenas uma vez e no início.
st.set_page_config(
    page_title="QA Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- AJUSTE 2: Definição do dicionário de cores ---
# A variável 'custom_colors' não estava definida, o que causaria um erro.
custom_colors = {
    'Passou': '#2ca02c',   # Verde
    'Falhado': '#d62728',  # Vermelho
    'Bloqueado': '#ff7f0e', # Laranja
    'Não Executado': '#7f7f7f' # Cinza
}

# --- Funções de extração e processamento (sem grandes alterações) ---
def extract_text_from_pdf(pdf_file):
    """Extrai texto de um arquivo PDF."""
    text = ""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        st.error(f"Erro ao ler o PDF: {e}")
    return text

def process_extracted_data(extracted_data):
    """Processa os dados extraídos, agrupa por história e calcula métricas."""
    text_data = extracted_data["text"]
    lines = text_data.split('\n')
    
    raw_test_data = []
    current_story_id = "Não Identificado"
    
    # Expressões regulares para capturar os dados
    regex_story = re.compile(r'Suite de Testes\s*:\s*([A-Z]+-\d+)')
    regex_status_res = re.compile(r'Resultado da Execução:\s*(\w+)')
    regex_status_est = re.compile(r'Estado da\s*Execução:\s*(\w+)')

    for line in lines:
        line = line.strip()
        
        story_match = regex_story.search(line)
        if story_match:
            current_story_id = story_match.group(1).strip()
            continue

        status_match = regex_status_res.search(line) or regex_status_est.search(line)
        if status_match:
            status = status_match.group(1).strip()
            raw_test_data.append({
                'story_id': current_story_id,
                'status': status
            })
            continue

    if not raw_test_data:
        st.warning("Não foi possível identificar testes no arquivo. Verifique se o formato do PDF é o esperado.")
        return None

    df_stories = pd.DataFrame(raw_test_data)
    df_stories['status'] = df_stories['status'].replace({'Falhou': 'Falhado', 'Passou': 'Passou'})
    
    total_cases = len(df_stories)
    passed_cases = len(df_stories[df_stories['status'] == "Passou"])
    executed_cases = len(df_stories[df_stories['status'] != "Não Executado"])

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
        "df_status": df_stories.groupby('status').size().reset_index(name='Total').rename(columns={'status': 'Status'}),
        "kpis": kpis,
        "df_stories": df_stories.groupby(['story_id', 'status']).size().reset_index(name='Total')
    }

def get_inspirational_quote():
    """Retorna uma frase inspiradora aleatória."""
    quotes = [
        ("O fracasso é uma opção. Se as coisas não estão a falhar, você não está a inovar o suficiente.", "Elon Musk"),
        ("A inovação distingue um líder de um seguidor.", "Steve Jobs"),
        ("Se você constrói grandes experiências, os clientes contam uns aos outros sobre isso.", "Bill Gates")
    ]
    quote, author = random.choice(quotes)
    return f"_{quote}_ - {author}"

# --- AJUSTE 3: Lógica de IA simplificada e mais robusta ---
def generate_ai_text(df_stories, kpis):
    """Gera resumo usando a IA do Google."""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest') # Usando um modelo moderno e estável
        
        prompt_parts = [
            "Com base nos seguintes dados de um dashboard de QA, crie um resumo profissional e conciso para o Microsoft Teams.",
            "Use emojis relevantes 📊, destaque **palavras-chave** importantes e use frases curtas.",
            "\n### KPIs Gerais:",
            f"- **Total de Casos:** {kpis.get('Total de Casos de Teste', 0)}",
            f"- **Execução:** {kpis.get('Percentual de Execucao', 0):.1f}%",
            f"- **Sucesso (dos executados):** {kpis.get('Percentual de Sucesso', 0):.1f}%",
            "\n### Detalhes por História:"
        ]

        stories_summary = df_stories.groupby(['story_id', 'status']).size().unstack(fill_value=0)
        for story_id, row in stories_summary.iterrows():
            details = ", ".join([f"{status}: {count}" for status, count in row.items() if count > 0])
            prompt_parts.append(f"- **{story_id}**: {details}")
        
        prompt = "\n".join(prompt_parts)
        
        response = model.generate_content(prompt)
        inspirational_quote = get_inspirational_quote()
        return f"{response.text}\n\n{inspirational_quote}"

    except Exception as e:
        st.error(f"Ocorreu um erro ao gerar o texto com IA: {e}")
        return "Não foi possível gerar o resumo. Verifique a chave de API e as configurações."

# --- Funções de exibição (com pequenas melhorias) ---
def display_kpis(kpis):
    """Exibe os KPIs principais."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Casos de Teste", kpis.get("Total de Casos de Teste", 0))
    col2.metric("Casos Passados", kpis.get("Casos Passados", 0))
    col3.metric("Percentual de Execução", f"{kpis.get('Percentual de Execucao', 0):.1f}%")
    col4.metric("Percentual de Sucesso", f"{kpis.get('Percentual de Sucesso', 0):.1f}%")

def display_dashboard(processed_data, ia_habilitada):
    """Exibe o dashboard completo."""
    df_status = processed_data["df_status"]
    df_stories = processed_data["df_stories"]
    kpis = processed_data["kpis"]

    st.header("📈 Dashboard Geral de Testes")
    display_kpis(kpis)
    
    col1, col2 = st.columns(2)
    with col1:
        fig_pie = px.pie(df_status, values='Total', names='Status', title="Distribuição Geral por Status", color='Status', color_discrete_map=custom_colors)
        st.plotly_chart(fig_pie, use_container_width=True)
    with col2:
        fig_bar = px.bar(df_status, x='Status', y='Total', title="Contagem Geral por Status", color='Status', color_discrete_map=custom_colors)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    st.markdown("---")

    # Seção de IA só aparece se a chave de API estiver configurada
    if ia_habilitada:
        st.header("🤖 Gerar Resumo para Teams com IA")
        if st.button("✨ Gerar Resumo"):
            with st.spinner("Criando resumo..."):
                ai_text = generate_ai_text(df_stories, kpis)
                st.text_area("Texto gerado:", ai_text, height=350)
        st.markdown("---")

    st.header("📋 Análise Detalhada por História")
    unique_stories = df_stories['story_id'].unique()

    for story_id in sorted(unique_stories):
        with st.expander(f"📚 {story_id}"):
            story_data = df_stories[df_stories['story_id'] == story_id]
            fig = px.pie(story_data, values='Total', names='status', title=f"Distribuição para {story_id}", color='status', color_discrete_map=custom_colors)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(story_data, use_container_width=True)

def display_sample_dashboard():
    """Exibe um dashboard de exemplo quando nenhum arquivo é carregado."""
    st.info("👈 Faça upload de um arquivo PDF para visualizar as métricas ou veja um exemplo abaixo.")
    sample_data = {
        "df_status": pd.DataFrame({'Status': ['Passou', 'Falhado', 'Bloqueado'], 'Total': [2, 1, 1]}),
        "kpis": {"Total de Casos de Teste": 4, "Casos Passados": 2, "Casos Executados": 4, "Percentual de Execucao": 100.0, "Percentual de Sucesso": 50.0},
        "df_stories": pd.DataFrame({'story_id': ['ECPU-123', 'ECPU-123', 'ECPU-123'], 'status': ['Passou', 'Falhado', 'Bloqueado'], 'Total': [2, 1, 1]})
    }
    display_dashboard(sample_data, ia_habilitada=False) # IA desabilitada para o exemplo

def main():
    """Função principal da aplicação."""
    st.title("📊 QA Dashboard - Análise de Métricas de Testes")
    
    # --- AJUSTE 4: Gerenciamento centralizado da API Key ---
    ia_habilitada = False
    if 'GOOGLE_API_KEY' in st.secrets:
        try:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            ia_habilitada = True
            st.sidebar.success("✅ Funcionalidades de IA habilitadas!")
        except Exception as e:
            st.sidebar.error(f"Erro ao configurar a API de IA: {e}")
    else:
        st.sidebar.warning("🔑 Chave de API do Google não encontrada. Funcionalidades de IA desabilitadas.")

    st.sidebar.header("📁 Upload de Arquivo PDF")
    uploaded_file = st.sidebar.file_uploader("Selecione um arquivo PDF", type=['pdf'])
    
    if uploaded_file:
        with st.spinner("Processando PDF..."):
            extracted_data = {"text": extract_text_from_pdf(uploaded_file)}
            if extracted_data["text"]:
                processed_data = process_extracted_data(extracted_data)
                if processed_data:
                    display_dashboard(processed_data, ia_habilitada)
    else:
        display_sample_dashboard()

if __name__ == "__main__":
    main()