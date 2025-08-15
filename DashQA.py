"""
QA Dashboard App - Aplicativo para análise de métricas de QA a partir de PDFs
Versão otimizada para Streamlit Cloud com agrupamento por história
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
import random

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
    
    api_key = None
    try:
        if hasattr(st, 'secrets'):
            api_key = st.secrets.get("GOOGLE_API_KEY", None)
    except Exception:
        api_key = None
    
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

def process_extracted_data(extracted_data):
    """
    Processa os dados extraídos, agrupa por história e calcula métricas.
    A lógica agora é baseada na identificação de padrões de texto.
    """
    text_data = extracted_data["text"]
    lines = text_data.split('\n')
    
    # Listas para armazenar os dados brutos e agrupados
    raw_test_data = []
    
    # Variáveis para rastrear a história e o caso de teste atuais
    current_story_id = "Não Identificado"
    current_story_title = "Não Identificado"
    
    # Regex para identificar padrões
    # 'Suite de Testes : ECOMDGT-9755: Refatoração de Meus pedidos 1'
    regex_story = re.compile(r'Suite de Testes\s*:\s*(ECOMDGT-\d+):\s*(.*)')
    # 'Caso de Teste ECMA-220: CT01: ...'
    regex_test_case = re.compile(r'Caso de Teste\s*(ECMA-\d+):\s*(.*)')
    # 'Resultado da Execução: Falhado'
    regex_status = re.compile(r'Resultado da Execução:\s*(\w+)')
    # 'Estado da Execução: Passou'
    regex_status_alt = re.compile(r'Estado da\s*Execução:\s*(\w+)')

    for line in lines:
        line = line.strip()
        
        # Tenta encontrar a história
        story_match = regex_story.search(line)
        if story_match:
            current_story_id = story_match.group(1).strip()
            current_story_title = story_match.group(2).strip()
            continue
            
        # Tenta encontrar o status do teste.
        # A lógica aqui é que o status geralmente está após o "Caso de Teste"
        status_match = regex_status.search(line) or regex_status_alt.search(line)
        if status_match:
            status = status_match.group(1).strip()
            raw_test_data.append({
                'story_id': current_story_id,
                'story_title': current_story_title,
                'status': status
            })
            continue

    if not raw_test_data:
        # Fallback para a lógica anterior se a nova não encontrar nada
        st.warning("Não foi possível identificar as histórias de teste. Usando o modo de extração básico.")
        status_keywords = ["Passou", "Falhado", "Bloqueado", "Não Executado", "Falhou"]
        status_counts = {keyword: 0 for keyword in status_keywords}
        for keyword in status_keywords:
            status_counts[keyword] += text_data.count(keyword)
        
        df_status = pd.DataFrame(list(status_counts.items()), columns=["Status", "Total"])
        df_status = df_status[df_status["Total"] > 0]
        
        kpis = {}
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
            "kpis": kpis,
            "df_stories": pd.DataFrame() # Retorna um dataframe vazio para compatibilidade
        }

    df_stories = pd.DataFrame(raw_test_data)
    
    # Mapeia 'Falhou' para 'Falhado' para unificar
    df_stories['status'] = df_stories['status'].replace('Falhou', 'Falhado')
    
    # Agrupa por história e status para criar a tabela de dados
    grouped_data = df_stories.groupby(['story_id', 'story_title', 'status']).size().reset_index(name='Total')

    # Calcula KPIs totais
    total_cases = len(df_stories)
    passed_cases = len(df_stories[df_stories['status'].str.contains("Passou", case=False, na=False)])
    executed_cases = len(df_stories[~df_stories['status'].str.contains("Não Executado", case=False, na=False)])

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
        "df_stories": grouped_data
    }

# --- Funções para gerar texto com IA ---
def get_inspirational_quote():
    """Retorna uma frase inspiradora aleatória."""
    quotes = [
        ("O fracasso é uma opção. Se as coisas não estão a falhar, você não está a inovar o suficiente.", "Elon Musk"),
        ("A inovação distingue um líder de um seguidor.", "Steve Jobs"),
        ("Se você constrói grandes experiências, os clientes contam uns aos outros sobre isso.", "Bill Gates"),
        ("O primeiro passo é estabelecer que algo é possível; a probabilidade ocorrerá em seguida.", "Elon Musk"),
        ("A paciência é um elemento-chave do sucesso.", "Bill Gates"),
    ]
    quote, author = random.choice(quotes)
    return f"*{quote}* - {author}"

def generate_ai_text(df_stories, kpis, genai_instance):
    """Gera resumo usando IA, agora com detalhamento por história."""
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
- Enfatize as métricas totais e, em seguida, forneça um breve resumo por história de teste.

### Dados de entrada:
- KPIs Totais:
    - Total de Casos de Teste: {kpis.get("Total de Casos de Teste", 0)}
    - Casos Passados: {kpis.get("Casos Passados", 0)}
    - Percentual de Execucao: {kpis.get("Percentual de Execucao", 0):.1f}%
    - Percentual de Sucesso: {kpis.get("Percentual de Sucesso", 0):.1f}%

- Resumo por História:
"""
        # Agrupar e formatar o resumo por história
        stories_summary = df_stories.groupby(['story_id', 'story_title', 'status']).size().unstack(fill_value=0)
        
        for index, row in stories_summary.iterrows():
            story_id, story_title = index
            total_story_tests = row.sum()
            passed_story_tests = row.get('Passou', 0)
            
            prompt += f"""
- **{story_id} - {story_title}**:
    - Casos totais: {total_story_tests}
    - Status:
"""
            for status, count in row.items():
                prompt += f"        - {status}: {count}\n"
        
        # Chamada para a API
        response = model.generate_content(prompt)
        
        # Adiciona a frase inspiradora no final
        inspirational_quote = get_inspirational_quote()
        return f"{response.text}\n\n{inspirational_quote}"
    except Exception as e:
        return f"Erro ao gerar texto: {e}"

# --- Funções de exibição ---
def display_kpis(kpis):
    """Exibe os KPIs principais em colunas."""
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

def display_dashboard(processed_data, genai_instance=None):
    """Exibe o dashboard principal com agrupamento por história."""
    df_status = processed_data["df_status"]
    df_stories = processed_data["df_stories"]
    kpis = processed_data["kpis"]

    # Seção de KPIs Gerais
    st.header("📈 KPIs Gerais do Relatório")
    display_kpis(kpis)
    st.markdown("---")
    
    # Seção de Geração de Texto com IA
    if genai_instance and GENAI_AVAILABLE:
        st.header("🤖 Gerar Resumo para Teams com IA")
        if st.button("✨ Gerar Resumo"):
            with st.spinner("Gerando texto com IA..."):
                ai_text = generate_ai_text(df_stories, kpis, genai_instance)
                st.text_area(
                    "Texto gerado (copie e cole no Teams):", 
                    ai_text, 
                    height=300
                )
        st.markdown("---")

    # Seção de Análise por História
    st.header("📋 Análise Detalhada por História")

    unique_stories = df_stories[['story_id', 'story_title']].drop_duplicates().sort_values(by='story_id')
    
    if unique_stories.empty:
        st.info("Nenhuma história de teste foi identificada no arquivo.")
        return

    for index, story in unique_stories.iterrows():
        story_id = story['story_id']
        story_title = story['story_title']
        
        # Filtra os dados para a história atual
        story_data = df_stories[df_stories['story_id'] == story_id]

        # Calcula KPIs da história
        story_kpis = {
            "Total de Casos de Teste": story_data['Total'].sum(),
            "Casos Passados": story_data[story_data['status'] == 'Passou']['Total'].sum(),
            "Casos Executados": story_data[story_data['status'] != 'Não Executado']['Total'].sum()
        }
        
        story_kpis["Percentual de Execucao"] = (story_kpis["Casos Executados"] / story_kpis["Total de Casos de Teste"]) * 100 if story_kpis["Total de Casos de Teste"] > 0 else 0
        story_kpis["Percentual de Sucesso"] = (story_kpis["Casos Passados"] / story_kpis["Casos Executados"]) * 100 if story_kpis["Casos Executados"] > 0 else 0
        
        # Expander para cada história
        with st.expander(f"📚 {story_id} - {story_title}"):
            st.markdown(f"**KPIs para a História:** `{story_id}`")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total de Casos", story_kpis["Total de Casos de Teste"])
            with col2:
                st.metric("Taxa de Sucesso", f"{story_kpis['Percentual de Sucesso']:.1f}%")

            # Gráficos da história
            col1, col2 = st.columns(2)
            with col1:
                fig_pie = px.pie(
                    story_data,
                    values='Total',
                    names='status',
                    title="Distribuição de Status",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                fig_bar = px.bar(
                    story_data,
                    x='status',
                    y='Total',
                    title="Casos por Status",
                    color='status',
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            st.subheader("Dados Detalhados")
            st.dataframe(story_data.rename(columns={'status': 'Status'}), use_container_width=True)
    
    st.subheader("💾 Exportar Dados Completos")
    csv = df_stories.to_csv(index=False)
    st.download_button(
        label="📥 Baixar CSV da Análise por História",
        data=csv,
        file_name="qa_metrics_by_story.csv",
        mime="text/csv"
    )

def display_sample_dashboard():
    """Exibe dashboard de exemplo com a nova estrutura."""
    st.header("📊 Dashboard de Exemplo")
    st.info("Este é um exemplo de como o dashboard aparecerá com dados de um relatório com histórias de teste.")

    sample_data = pd.DataFrame({
        'story_id': ['ECOMDGT-12128', 'ECOMDGT-12128', 'ECOMDGT-9755', 'ECOMDGT-9755', 'ECOMDGT-9755', 'ECOMDGT-9755'],
        'story_title': ['Refatoração do banner', 'Refatoração do banner', 'Refatoração de Meus pedidos', 'Refatoração de Meus pedidos', 'Refatoração de Meus pedidos', 'Refatoração de Meus pedidos'],
        'status': ['Passou', 'Falhado', 'Passou', 'Falhado', 'Bloqueado', 'Não Executado'],
        'Total': [2, 1, 3, 1, 1, 1]
    })
    
    grouped_data = sample_data.groupby(['story_id', 'story_title', 'status']).sum().reset_index()

    display_dashboard({
        "df_status": sample_data.groupby('status').sum().reset_index().rename(columns={'status': 'Status'}),
        "kpis": {
            "Total de Casos de Teste": 9,
            "Casos Passados": 5,
            "Casos Executados": 7,
            "Percentual de Execucao": 77.8,
            "Percentual de Sucesso": 71.4
        },
        "df_stories": grouped_data
    })
    
# --- Aplicação Principal ---
def main():
    """Função principal da aplicação"""
    st.title("📊 QA Dashboard - Análise de Métricas de Testes")
    st.markdown("---")
    
    genai_instance = configure_ai()
    
    st.sidebar.header("📁 Upload de Arquivo PDF")
    uploaded_file = st.sidebar.file_uploader(
        "Selecione um arquivo PDF com métricas de QA",
        type=['pdf'],
        help="Faça upload de um arquivo PDF contendo dados de testes de QA"
    )
    
    if uploaded_file is not None:
        with st.spinner("Extraindo e processando dados do PDF..."):
            extracted_data = {}
            # Como a extração de tabelas está fora de uso na nova lógica,
            # focamos apenas na extração de texto
            extracted_data["text"] = extract_text_from_pdf(uploaded_file)
            
            # Se o texto for extraído, processamos os dados
            if extracted_data["text"]:
                processed_data = process_extracted_data(extracted_data)
                
                if not processed_data["df_stories"].empty:
                    display_dashboard(processed_data, genai_instance)
                else:
                    st.error("Não foi possível agrupar os testes por história. Verifique se o arquivo segue o padrão esperado.")
            else:
                st.error("Não foi possível extrair dados válidos do PDF.")
    else:
        st.info("👈 Faça upload de um arquivo PDF para visualizar as métricas de QA")
        display_sample_dashboard()

if __name__ == "__main__":
    main()
