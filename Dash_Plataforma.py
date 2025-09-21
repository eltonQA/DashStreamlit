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
    Processa os dados extraídos, agrupa por plataforma e história, e calcula métricas.
    A lógica é baseada na identificação de padrões de texto para plataforma, história e status.
    """
    text_data = extracted_data["text"]
    lines = text_data.split('\n')
    
    raw_test_data = []
    
    # Variáveis para rastrear o contexto atual
    current_story_id = "Não Identificada"
    current_platform = "Não Identificada"
    
    # Regex para identificar padrões
    # ATUALIZADO: Regex mais flexível para a suíte de testes
    regex_story = re.compile(r'Suite de Testes\s*:\s*([\w-]+)')
    # ATUALIZADO: Regex mais flexível para a plataforma (aceita números e novos nomes)
    regex_platform = re.compile(r'\d*\.?\s*Plataforma\s*:\s*(\w+)', re.IGNORECASE)
    regex_status_res = re.compile(r'Resultado da Execução:\s*(\w+)')
    regex_status_est = re.compile(r'Estado da\s*Execução:\s*(\w+)')

    for line in lines:
        line = line.strip()
        
        # Tenta encontrar a plataforma para atualizar o contexto
        platform_match = regex_platform.search(line)
        if platform_match:
            # Captura o grupo 1, que é o nome da plataforma
            current_platform = platform_match.group(1).strip()
            continue

        # Tenta encontrar a história para atualizar o contexto
        story_match = regex_story.search(line)
        if story_match:
            current_story_id = story_match.group(1).strip()
            continue

        # Tenta encontrar o status do teste
        status_match = regex_status_res.search(line) or regex_status_est.search(line)
        if status_match:
            status = status_match.group(1).strip()
            raw_test_data.append({
                'platform': current_platform,
                'story_id': current_story_id,
                'status': status
            })
            continue

    if not raw_test_data:
        st.warning("Não foi possível identificar testes no arquivo. Verifique se o formato do PDF contém os status de execução (ex: 'Resultado da Execução: Passou').")
        return {
            "df_status": pd.DataFrame(),
            "kpis": {},
            "df_tests": pd.DataFrame()
        }

    df_tests = pd.DataFrame(raw_test_data)
    
    # Mapeia 'Falhou' para 'Falhado' para unificar
    df_tests['status'] = df_tests['status'].replace('Falhou', 'Falhado')
    
    # Agrupa por história, plataforma e status para criar a tabela de dados
    grouped_data = df_tests.groupby(['platform', 'story_id', 'status']).size().reset_index(name='Total')

    # Calcula KPIs totais
    total_cases = len(df_tests)
    passed_cases = len(df_tests[df_tests['status'].str.contains("Passou", case=False, na=False)])
    executed_cases = len(df_tests[~df_tests['status'].str.contains("Não Executado", case=False, na=False)])

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
        "df_status": df_tests.groupby('status').size().reset_index(name='Total').rename(columns={'status': 'Status'}),
        "kpis": kpis,
        "df_tests": df_tests # Retorna o dataframe completo com a coluna de plataforma
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

def generate_ai_text(df_tests, kpis, genai_instance):
    """Gera resumo usando IA, com detalhamento por plataforma e história."""
    if not genai_instance:
        return "Erro: IA não configurada ou indisponível."
    
    try:
        model = genai_instance.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
Com base nos seguintes dados de um dashboard de QA, crie um resumo profissional e conciso para o Microsoft Teams.

Regras:
- Use emojis relevantes 📊.
- Destaque **palavras-chave** com negrito (padrão Markdown).
- Use frases curtas e objetivas.
- Enfatize as métricas totais, depois resuma por plataforma e história.

### 📈 Resumo Geral:
- **Total de Casos de Teste**: {kpis.get("Total de Casos de Teste", 0)}
- **Casos Passados**: {kpis.get("Casos Passados", 0)}
- **Percentual de Execução**: {kpis.get("Percentual de Execucao", 0):.1f}%
- **Percentual de Sucesso**: {kpis.get("Percentual de Sucesso", 0):.1f}%

### 📱 Detalhamento por Plataforma:
"""
        # Agrupar por plataforma e depois por história
        for platform, platform_df in df_tests.groupby('platform'):
            prompt += f"\n- **Plataforma: {platform}**\n"
            stories_summary = platform_df.groupby(['story_id', 'status']).size().unstack(fill_value=0)
            
            for story_id, row in stories_summary.iterrows():
                total_story_tests = row.sum()
                status_list = ", ".join([f"{status}: {count}" for status, count in row.items() if count > 0])
                prompt += f"  - **{story_id}**: {total_story_tests} casos ({status_list})\n"
        
        # Chamada para a API
        response = model.generate_content(prompt)
        
        # Adiciona a frase inspiradora no final
        inspirational_quote = get_inspirational_quote()
        return f"{response.text}\n\n{inspirational_quote}"
    except Exception as e:
        return f"Erro ao gerar texto: {e}"

# --- Funções de exibição ---
custom_colors = {
    'Passou': '#008000',
    'Falhado': '#FF2800',
    'Bloqueado': '#FFFF00',
    'Não Executado': '#0000FF'
}

def display_kpis(kpis, title="KPIs", key_prefix=""):
    """Exibe os KPIs principais em colunas."""
    st.subheader(title)
    cols = st.columns(len(kpis))
    # Adicionado key_prefix para garantir unicidade das chaves
    for (label, value), col in zip(kpis.items(), cols):
        if isinstance(value, float):
            col.metric(label, f"{value:.1f}%", key=f"{key_prefix}_{label}")
        else:
            col.metric(label, value, key=f"{key_prefix}_{label}")


def display_overall_dashboard(df_status, kpis):
    """Exibe o dashboard geral com gráficos."""
    st.header("📈 Dashboard Geral de Testes")
    display_kpis(kpis, title="", key_prefix="overall") # Título já está no header
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Distribuição por Status (Geral)")
        if not df_status.empty:
            fig_pie = px.pie(
                df_status,
                values='Total',
                names='Status',
                title="Total de Casos por Status",
                color='Status',
                color_discrete_map=custom_colors
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Sem dados para exibir o gráfico de pizza.")

    with col2:
        st.subheader("📈 Casos por Status (Geral)")
        if not df_status.empty:
            fig_bar = px.bar(
                df_status,
                x='Status',
                y='Total',
                title="Número de Casos por Status",
                color='Status',
                color_discrete_map=custom_colors
            )
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Sem dados para exibir o gráfico de barras.")
    st.markdown("---")


def display_dashboard(processed_data, genai_instance=None):
    """Exibe o dashboard principal com agrupamento por plataforma e história."""
    df_status = processed_data["df_status"]
    df_tests = processed_data["df_tests"]
    kpis = processed_data["kpis"]

    display_overall_dashboard(df_status, kpis)
    
    if genai_instance and GENAI_AVAILABLE:
        st.header("🤖 Gerar Resumo para Teams com IA")
        if st.button("✨ Gerar Resumo"):
            with st.spinner("Gerando texto com IA..."):
                ai_text = generate_ai_text(df_tests, kpis, genai_instance)
                st.text_area(
                    "Texto gerado (copie e cole no Teams):", 
                    ai_text, 
                    height=350
                )
        st.markdown("---")

    # --- NOVA SEÇÃO: Análise por Plataforma ---
    st.header("📱 Análise Detalhada por Plataforma")

    unique_platforms = df_tests['platform'].unique()
    
    if len(unique_platforms) == 0:
        st.info("Nenhuma plataforma foi identificada no arquivo.")
        return

    for platform in sorted(unique_platforms):
        with st.expander(f"**{platform}**"):
            platform_data = df_tests[df_tests['platform'] == platform]
            
            # KPIs da plataforma
            total = len(platform_data)
            passed = len(platform_data[platform_data['status'] == 'Passou'])
            executed = len(platform_data[platform_data['status'] != 'Não Executado'])
            success_rate = (passed / executed) * 100 if executed > 0 else 0

            platform_kpis = {
                "Total de Casos": total,
                "Casos Passados": passed,
                "Taxa de Sucesso": success_rate
            }
            display_kpis(platform_kpis, title=f"KPIs para {platform}", key_prefix=platform)

            # Gráficos da plataforma
            col1, col2 = st.columns(2)
            platform_status_counts = platform_data.groupby('status').size().reset_index(name='Total')
            with col1:
                fig_pie = px.pie(platform_status_counts, values='Total', names='status', title="Distribuição de Status", color='status', color_discrete_map=custom_colors)
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                # Adicionada chave única para o gráfico de pizza
                st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_chart_{platform}")
            
            with col2:
                fig_bar = px.bar(platform_status_counts, x='status', y='Total', title="Casos por Status", color='status', color_discrete_map=custom_colors)
                fig_bar.update_layout(showlegend=False)
                # Adicionada chave única para o gráfico de barras
                st.plotly_chart(fig_bar, use_container_width=True, key=f"bar_chart_{platform}")
            
            # Detalhes por história dentro da plataforma
            st.subheader("Detalhes por História")
            for story_id, story_data in platform_data.groupby('story_id'):
                story_status_summary = story_data['status'].value_counts().reset_index()
                story_status_summary.columns = ['Status', 'Total']
                # Adicionada chave única para o markdown e dataframe
                st.markdown(f"**História:** `{story_id}`", key=f"md_{platform}_{story_id}")
                st.dataframe(story_status_summary, use_container_width=True, key=f"df_{platform}_{story_id}")
    
    st.markdown("---")
    st.subheader("💾 Exportar Dados Completos")
    csv = df_tests.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar CSV da Análise Completa",
        data=csv,
        file_name="qa_metrics_full.csv",
        mime="text/csv"
    )

def display_sample_dashboard():
    """Exibe dashboard de exemplo com a nova estrutura de plataforma."""
    st.header("📊 Dashboard de Exemplo")
    st.info("Este é um exemplo de como o dashboard aparecerá com dados separados por plataforma e história.")

    sample_data = pd.DataFrame({
        'platform': ['Android', 'Android', 'Android', 'iOS', 'iOS', 'Web'],
        'story_id': ['ECPU-213', 'ECPU-213', 'ECPU-456', 'ECPU-213', 'ECPU-213', 'ECOM-101'],
        'status': ['Passou', 'Falhado', 'Passou', 'Bloqueado', 'Passou', 'Não Executado']
    })
    
    df_status = sample_data.groupby('status').size().reset_index(name='Total').rename(columns={'status': 'Status'})

    display_dashboard({
        "df_status": df_status,
        "kpis": {
            "Total de Casos de Teste": 6,
            "Casos Passados": 3,
            "Casos Executados": 5,
            "Percentual de Execucao": 83.3,
            "Percentual de Sucesso": 60.0
        },
        "df_tests": sample_data
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
        help="O PDF deve conter 'Plataforma:', 'Suite de Testes:' e status de execução para a extração correta dos dados."
    )
    
    if uploaded_file is not None:
        with st.spinner("Extraindo e processando dados do PDF..."):
            extracted_data = {}
            extracted_data["text"] = extract_text_from_pdf(uploaded_file)
            
            if extracted_data["text"]:
                processed_data = process_extracted_data(extracted_data)
                
                if not processed_data["df_tests"].empty:
                    display_dashboard(processed_data, genai_instance)
                else:
                    st.error("Não foi possível agrupar os testes. Verifique se o arquivo segue o padrão esperado.")
            else:
                st.error("Não foi possível extrair dados válidos do PDF.")
    else:
        st.info("👈 Faça upload de um arquivo PDF para visualizar as métricas de QA")
        display_sample_dashboard()

if __name__ == "__main__":
    main()
