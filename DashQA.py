"""
QA Dashboard App - Aplicativo para análise de métricas de QA a partir de PDFs
Versão otimizada para Streamlit Cloud
"""
# Código revertido para a versão que não inclui agrupamento por plataforma
# a fim de evitar erros de extração e duplicidade de IDs.
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
def configurar_ai():
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
def extrair_texto_do_pdf(pdf_file):
    """Extrai texto de um arquivo PDF"""
    text = ""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        for page_num in range(len(reader.pages)):
            text += reader.pages[page_num].extract_text() or ""
    except Exception as e:
        st.error(f"Erro ao extrair texto: {e}")
    return text

def processar_dados_extraidos(extracted_data):
    """
    Processa os dados extraídos e calcula métricas.
    A lógica agora é baseada na identificação de padrões de texto.
    """
    text_data = extracted_data["text"]
    lines = text_data.split('\n')
    
    raw_test_data = []
    
    current_story_id = "Não Identificado"
    current_story_title = "Não Identificado"
    
    regex_story = re.compile(r'Suite de Testes\s*:\s*([A-Z]+-\d+)\s*(.*)')
    regex_test_case = re.compile(r'Caso de Teste\s*([A-Z]+-\d+):\s*(.*)')
    regex_status_res = re.compile(r'(?:Resultado da Execução|Estado da Execução):\s*(\w+)', re.IGNORECASE)
    regex_comments = re.compile(r'Comentários\s*(.*?)?\s*(https:\/\/.*)?', re.DOTALL | re.IGNORECASE)

    temp_test_case_info = {}

    for i, line in enumerate(lines):
        line = line.strip()
        
        story_match = regex_story.search(line)
        if story_match:
            current_story_id = story_match.group(1).strip()
            current_story_title = story_match.group(2).strip()
            continue
        
        test_case_match = regex_test_case.search(line)
        if test_case_match:
            test_case_id = test_case_match.group(1).strip()
            test_case_name = test_case_match.group(2).strip()
            temp_test_case_info = {
                'story_id': current_story_id,
                'story_title': current_story_title,
                'test_case_id': test_case_id,
                'test_case_name': test_case_name,
                'status': 'Não Executado',
                'comments': ''
            }
            continue

        status_match_res = regex_status_res.search(line)
        comments_match = regex_comments.search(line)
        
        if temp_test_case_info:
            if status_match_res:
                temp_test_case_info['status'] = status_match_res.group(1).strip()
                raw_test_data.append(temp_test_case_info)
                temp_test_case_info = {}
                continue
            if comments_match:
                temp_test_case_info['comments'] = comments_match.group(1).strip()
                
    if temp_test_case_info:
        raw_test_data.append(temp_test_case_info)

    if not raw_test_data:
        st.warning("Não foi possível identificar testes no arquivo. Verifique se o formato do PDF é o esperado.")
        return {
            "df_status": pd.DataFrame(),
            "kpis": {},
            "df_stories": pd.DataFrame(),
            "df_platform_stories": pd.DataFrame()
        }

    df_stories = pd.DataFrame(raw_test_data)
    
    df_stories['status'] = df_stories['status'].replace('Falhou', 'Falhado')
    
    grouped_data = df_stories.groupby(['story_id', 'story_title', 'status']).size().reset_index(name='Total')

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
        "df_stories": grouped_data,
        "df_platform_stories": df_stories
    }

# --- Funções para gerar texto com IA ---
def obter_frase_inspiradora():
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

def gerar_texto_ai(df_platform_stories, kpis, genai_instance):
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
- Enfatize as métricas totais e, em seguida, forneça um breve resumo por história de teste, agrupando por plataforma.

### Dados de entrada:
- KPIs Totais:
    - Total de Casos de Teste: {kpis.get("Total de Casos de Teste", 0)}
    - Casos Passados: {kpis.get("Casos Passados", 0)}
    - Percentual de Execucao: {kpis.get("Percentual de Execucao", 0):.1f}%
    - Percentual de Sucesso: {kpis.get("Percentual de Sucesso", 0):.1f}%

- Resumo por Plataforma e História:
"""
        platforms_summary = df_platform_stories.groupby(['story_id', 'story_title', 'status']).size().unstack(fill_value=0)
        
        unique_stories = df_platform_stories[['story_id', 'story_title']].drop_duplicates().sort_values(by='story_id')
        for index, story in unique_stories.iterrows():
            story_id = story['story_id']
            story_title = story['story_title']
            
            story_data = platforms_summary.loc[(story_id, story_title)]
            total_story_tests = story_data.sum()
                
            prompt += f"""
- **{story_id} - {story_title}**:
    - Casos totais: {total_story_tests}
    - Status:
"""
            for status, count in story_data.items():
                prompt += f"        - {status}: {count}\n"
        
        response = model.generate_content(prompt)
        
        inspirational_quote = obter_frase_inspiradora()
        return f"{response.text}\n\n{inspirational_quote}"
    except Exception as e:
        return f"Erro ao gerar texto: {e}"

# --- Funções de exibição ---
# Mapa de cores personalizado para os gráficos
custom_colors = {
    'Passou': '#008000',      # Verde
    'Falhado': '#FF2800',     # Vermelho Ferrari
    'Bloqueado': '#FFFF00',   # Amarelo
    'Não Executado': '#0000FF'# Azul
}

def exibir_kpis(kpis):
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
        
def exibir_dashboard_geral(df_status, kpis):
    """Exibe o dashboard geral com gráficos 2D e 3D."""
    st.header("📈 Dashboard Geral de Testes")
    exibir_kpis(kpis)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Distribuição por Status (Geral)")
        fig_pie = px.pie(
            df_status,
            values='Total',
            names='Status',
            title="Total de Casos por Status",
            color_discrete_map=custom_colors
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True, key="geral-pie")
    
    with col2:
        st.subheader("📈 Casos por Status (Geral)")
        fig_bar = px.bar(
            df_status,
            x='Status',
            y='Total',
            title="Número de Casos por Status",
            color='Status',
            color_discrete_map=custom_colors
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True, key="geral-bar")
    st.markdown("---")


def exibir_dashboard(processed_data, genai_instance=None):
    """Exibe o dashboard principal com agrupamento por plataforma e história."""
    df_status = processed_data["df_status"]
    df_stories = processed_data["df_stories"]
    df_platform_stories = processed_data["df_platform_stories"]
    kpis = processed_data["kpis"]

    exibir_dashboard_geral(df_status, kpis)
    
    if genai_instance and GENAI_AVAILABLE:
        st.header("🤖 Gerar Resumo para Teams com IA")
        if st.button("✨ Gerar Resumo"):
            with st.spinner("Gerando texto com IA..."):
                ai_text = gerar_texto_ai(df_platform_stories, kpis, genai_instance)
                st.text_area(
                    "Texto gerado (copie e cole no Teams):", 
                    ai_text, 
                    height=300
                )
        st.markdown("---")

    st.header("📋 Análise Detalhada por História")

    unique_stories = df_platform_stories[['story_id', 'story_title']].drop_duplicates().sort_values(by='story_id')
    
    if len(unique_stories) == 0:
        st.info("Nenhuma história de teste foi identificada no arquivo.")
        return

    for index, story in unique_stories.iterrows():
        story_id = story['story_id']
        story_title = story['story_title']
        
        story_key = f"story-{story_id}"
        
        story_data = df_platform_stories[df_platform_stories['story_id'] == story_id]
        
        story_status_counts = story_data.groupby('status').size().reset_index(name='Total')

        story_kpis = {
            "Total de Casos de Teste": story_status_counts['Total'].sum(),
            "Casos Passados": story_status_counts[story_status_counts['status'] == 'Passou']['Total'].sum(),
            "Casos Executados": story_status_counts[story_status_counts['status'] != 'Não Executado']['Total'].sum()
        }
        
        story_kpis["Percentual de Execucao"] = (story_kpis["Casos Executados"] / story_kpis["Total de Casos de Teste"]) * 100 if story_kpis["Total de Casos de Teste"] > 0 else 0
        story_kpis["Percentual de Sucesso"] = (story_kpis["Casos Passados"] / story_kpis["Casos Executados"]) * 100 if story_kpis["Casos Executados"] > 0 else 0
        
        with st.expander(f"📚 {story_id} - {story_title}", expanded=False):
            st.markdown(f"**KPIs para a História:** `{story_title}`")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total de Casos", story_kpis["Total de Casos de Teste"])
            with col2:
                st.metric("Taxa de Sucesso", f"{story_kpis['Percentual de Sucesso']:.1f}%")

            col1, col2 = st.columns(2)
            with col1:
                fig_pie = px.pie(
                    story_status_counts,
                    values='Total',
                    names='status',
                    title="Distribuição de Status",
                    color_discrete_map=custom_colors
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True, key=f"pie-{story_id}")
            
            with col2:
                fig_bar = px.bar(
                    story_status_counts,
                    x='status',
                    y='Total',
                    title="Casos por Status",
                    color='status',
                    color_discrete_map=custom_colors
                )
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True, key=f"bar-{story_id}")
            
            st.subheader("Dados Detalhados")
            st.dataframe(story_data[['test_case_id', 'test_case_name', 'status', 'comments']].rename(columns={'test_case_id': 'ID', 'test_case_name': 'Nome do Caso de Teste', 'status': 'Status', 'comments': 'Comentários'}), use_container_width=True)
    
    st.subheader("💾 Exportar Dados Completos")
    csv = df_stories.to_csv(index=False)
    st.download_button(
        label="📥 Baixar CSV da Análise por História",
        data=csv,
        file_name="qa_metrics_by_story.csv",
        mime="text/csv"
    )

def exibir_dashboard_exemplo():
    """Exibe dashboard de exemplo com a nova estrutura."""
    st.header("📊 Dashboard de Exemplo")
    st.info("Este é um exemplo de como o dashboard aparecerá com dados de um relatório com histórias de teste.")

    sample_data = pd.DataFrame({
        'story_id': ['ECPU-213', 'ECPU-213', 'ECPU-213', 'ECPU-94', 'ECPU-94'],
        'story_title': ['Incluir informações de parcelamento...', 'Incluir informações de parcelamento...', 'Incluir informações de parcelamento...', 'Validar exibição de parcelamento...', 'Validar exibição de parcelamento...'],
        'status': ['Passou', 'Falhado', 'Bloqueado', 'Passou', 'Falhado'],
        'test_case_id': ['ECPU-220', 'ECPU-221', 'ECPU-222', 'ECPU-94', 'ECPU-95'],
        'test_case_name': ['CT01: Verificar que o banner informativo está de acordo com o figma', 'CT02: Verificar que o banner informativo não aparece para usuários que não são cliente único', 'CT03: Verificar que o banner informativo não aparece para usuários que não sincronizaram os pedidos', 'Validar exibição de parcelamento no resumo do pedido com cupom', 'Validar exibição de parcelamento no resumo do pedido com cupom'],
        'comments': ['', 'bug fixado', 'falha de ambiente', '', 'bug aberto'],
    })
    
    # KPIs totais
    total_cases = len(sample_data)
    passed_cases = len(sample_data[sample_data['status'] == 'Passou'])
    executed_cases = len(sample_data[sample_data['status'] != 'Não Executado'])
    percent_execution = (executed_cases / total_cases) * 100
    percent_success = (passed_cases / executed_cases) * 100

    kpis = {
        "Total de Casos de Teste": total_cases,
        "Casos Passados": passed_cases,
        "Casos Executados": executed_cases,
        "Percentual de Execucao": percent_execution,
        "Percentual de Sucesso": percent_success
    }

    df_status = sample_data.groupby('status').size().reset_index(name='Total').rename(columns={'status': 'Status'})
    
    exibir_dashboard({
        "df_status": df_status,
        "kpis": kpis,
        "df_stories": sample_data,
        "df_platform_stories": sample_data
    })
    
# --- Aplicação Principal ---
def main():
    """Função principal da aplicação"""
    st.title("📊 QA Dashboard - Análise de Métricas de Testes")
    st.markdown("---")
    
    genai_instance = configurar_ai()
    
    st.sidebar.header("📁 Upload de Arquivo PDF")
    uploaded_file = st.sidebar.file_uploader(
        "Selecione um arquivo PDF com métricas de QA",
        type=['pdf'],
        help="Faça upload de um arquivo PDF contendo dados de testes de QA"
    )
    
    if uploaded_file is not None:
        with st.spinner("Extraindo e processando dados do PDF..."):
            extracted_data = {}
            extracted_data["text"] = extrair_texto_do_pdf(uploaded_file)
            
            if extracted_data["text"]:
                processed_data = processar_dados_extraidos(extracted_data)
                
                if not processed_data["df_stories"].empty:
                    exibir_dashboard(processed_data, genai_instance)
                else:
                    st.error("Não foi possível agrupar os testes por história. Verifique se o arquivo segue o padrão esperado.")
            else:
                st.error("Não foi possível extrair dados válidos do PDF.")
    else:
        st.info("👈 Faça upload de um arquivo PDF para visualizar as métricas de QA")
        exibir_dashboard_exemplo()

if __name__ == "__main__":
    main()
