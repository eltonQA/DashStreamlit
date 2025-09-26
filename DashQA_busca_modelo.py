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
import google.generativeai as genai
from google.api_core import exceptions

# Configuração da página
st.set_page_config(
    page_title="QA Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Configuração da API de IA e seleção de modelo ---
def find_available_model(genai_instance):
    """
    Busca um modelo disponível que suporta generateContent.
    Prioriza modelos mais avançados e acessíveis.
    """
    if not genai_instance:
        return None, "Erro: IA não configurada."

    # Tenta usar modelos em ordem de preferência
    preferred_models = ['gemini-1.5-pro', 'gemini-1.0-pro', 'gemini-pro']
    
    st.sidebar.info("Procurando um modelo de IA compatível com a sua chave...")
    try:
        all_models = [m.name for m in genai_instance.list_models() if 'generateContent' in m.supported_generation_methods]
        
        for model_name in preferred_models:
            # O nome do modelo retornado pela API pode ter um prefixo, ex: "models/gemini-pro"
            if any(model_name in m for m in all_models):
                st.sidebar.success(f"Modelo '{model_name}' encontrado!")
                return model_name, None
        
        return None, "Nenhum modelo compatível encontrado para a sua chave de API."

    except exceptions.FailedPrecondition as e:
        return None, f"Erro de pré-condição da API. Verifique a chave ou permissões. Detalhes: {e}"
    except Exception as e:
        return None, f"Ocorreu um erro ao listar os modelos: {e}"

# --- Funções de extração de dados (sem alterações) ---
# ... (o restante das suas funções, como extract_text_from_pdf, process_extracted_data, etc., permanecem as mesmas)
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
    
    raw_test_data = []
    
    current_story_id = "Não Identificado"
    
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
        return {
            "df_status": pd.DataFrame(),
            "kpis": {},
            "df_stories": pd.DataFrame()
        }

    df_stories = pd.DataFrame(raw_test_data)
    
    df_stories['status'] = df_stories['status'].replace('Falhou', 'Falhado')
    
    grouped_data = df_stories.groupby(['story_id', 'status']).size().reset_index(name='Total')

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

def generate_ai_text(df_stories, kpis, genai_instance, model_name):
    """Gera resumo usando IA, agora com detalhamento por história."""
    if not genai_instance or not model_name:
        return "Erro: IA não configurada ou modelo indisponível."
    
    try:
        model = genai_instance.GenerativeModel(model_name)
        
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
        stories_summary = df_stories.groupby(['story_id', 'status']).size().unstack(fill_value=0)
        
        for index, row in stories_summary.iterrows():
            story_id = index
            total_story_tests = row.sum()
            
            prompt += f"""
- **{story_id}**:
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

# --- Funções de exibição (sem alterações) ---
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
        
def display_overall_dashboard(df_status, kpis):
    """Exibe o dashboard geral com gráficos 2D e 3D."""
    st.header("📈 Dashboard Geral de Testes")
    display_kpis(kpis)
    
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
        st.plotly_chart(fig_pie, use_container_width=True)
    
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
        st.plotly_chart(fig_bar, use_container_width=True)
    st.markdown("---")


def display_dashboard(processed_data, genai_instance=None):
    """Exibe o dashboard principal com agrupamento por história."""
    df_status = processed_data["df_status"]
    df_stories = processed_data["df_stories"]
    kpis = processed_data["kpis"]

    # Seção de KPIs Gerais
    display_overall_dashboard(df_status, kpis)
    
    # Seção de Geração de Texto com IA
    if genai_instance:
        model_name, error_message = find_available_model(genai_instance)
        if error_message:
            st.error(f"Erro ao encontrar modelo de IA: {error_message}")
        else:
            st.header("🤖 Gerar Resumo para Teams com IA")
            if st.button("✨ Gerar Resumo"):
                with st.spinner("Gerando texto com IA..."):
                    ai_text = generate_ai_text(df_stories, kpis, genai_instance, model_name)
                    st.text_area(
                        "Texto gerado (copie e cole no Teams):", 
                        ai_text, 
                        height=300
                    )
            st.markdown("---")

    # Seção de Análise por História
    st.header("📋 Análise Detalhada por História")

    unique_stories = df_stories['story_id'].unique()
    
    if len(unique_stories) == 0:
        st.info("Nenhuma história de teste foi identificada no arquivo.")
        return

    for story_id in sorted(unique_stories):
        
        story_data = df_stories[df_stories['story_id'] == story_id]
        
        story_status_counts = story_data.groupby('status').sum().reset_index()

        story_kpis = {
            "Total de Casos de Teste": story_status_counts['Total'].sum(),
            "Casos Passados": story_status_counts[story_status_counts['status'] == 'Passou']['Total'].sum(),
            "Casos Executados": story_status_counts[story_status_counts['status'] != 'Não Executado']['Total'].sum()
        }
        
        story_kpis["Percentual de Execucao"] = (story_kpis["Casos Executados"] / story_kpis["Total de Casos de Teste"]) * 100 if story_kpis["Total de Casos de Teste"] > 0 else 0
        story_kpis["Percentual de Sucesso"] = (story_kpis["Casos Passados"] / story_kpis["Casos Executados"]) * 100 if story_kpis["Casos Executados"] > 0 else 0
        
        with st.expander(f"📚 {story_id}"):
            st.markdown(f"**KPIs para a História:** `{story_id}`")
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
                st.plotly_chart(fig_pie, use_container_width=True)
            
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
        'story_id': ['ECPU-213', 'ECPU-213', 'ECPU-213', 'ECPU-213', 'ECPU-213', 'ECPU-213'],
        'status': ['Passou', 'Falhado', 'Bloqueado', 'Não Executado', 'Passou', 'Bloqueado'],
        'Total': [1, 1, 1, 1, 1, 1]
    })
    
    grouped_data = sample_data.groupby(['story_id', 'status']).sum().reset_index()
    df_status = sample_data.groupby('status').sum().reset_index().rename(columns={'status': 'Status'})

    display_dashboard({
        "df_status": df_status,
        "kpis": {
            "Total de Casos de Teste": 6,
            "Casos Passados": 2,
            "Casos Executados": 4,
            "Percentual de Execucao": 66.7,
            "Percentual de Sucesso": 50.0
        },
        "df_stories": grouped_data
    })

def main():
    """Função principal da aplicação"""
    st.title("📊 QA Dashboard - Análise de Métricas de Testes")
    st.markdown("---")
    
    genai_instance = genai # Agora genai é importado diretamente se disponível
    
    st.sidebar.header("📁 Upload de Arquivo PDF")
    uploaded_file = st.sidebar.file_uploader(
        "Selecione um arquivo PDF com métricas de QA",
        type=['pdf'],
        help="Faça upload de um arquivo PDF contendo dados de testes de QA"
    )
    
    if uploaded_file is not None:
        with st.spinner("Extraindo e processando dados do PDF..."):
            extracted_data = {"text": extract_text_from_pdf(uploaded_file)}
            
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
