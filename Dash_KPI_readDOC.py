import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io
import re
from collections import defaultdict
import traceback

# Importa a biblioteca de IA da Google (opcional)
try:
    import google.generativeai as genai
    from google.api_core import exceptions
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None

# --- Configuração da Página ---
st.set_page_config(
    page_title="Dashboard de Qualidade Dinâmico",
    page_icon="📊",
    layout="wide"
)

# --- Estilo CSS Customizado ---
st.markdown("""
<style>
    .stMetric {
        background-color: #1F2937;
        border: 1px solid #374151;
        border-radius: 0.75rem;
        padding: 1.5rem;
    }
    .stMetric:hover {
        border-color: #556070;
    }
    .stPlotlyChart {
        background-color: #1F2937;
        border: 1px solid #374151;
        border-radius: 0.75rem;
        padding: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Cores para os Gráficos ---
CHART_COLORS = {
    'Passou': 'rgba(74, 222, 128, 0.8)',
    'Falhou': 'rgba(248, 113, 113, 0.8)',
    'Bloqueado': 'rgba(251, 146, 60, 0.8)',
    'Não Executado': 'rgba(156, 163, 175, 0.6)'
}

# --- Configuração da API de IA ---
def configure_ai():
    """Configura a API de IA se disponível"""
    if not GENAI_AVAILABLE:
        return None
    
    # Tenta obter a chave dos secrets do Streamlit de forma segura
    api_key = None
    try:
        if hasattr(st, 'secrets') and "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets.get("GOOGLE_API_KEY")
    except Exception:
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
            st.session_state['genai_configured'] = True
            return genai
        except exceptions.PermissionDenied as e:
            st.sidebar.error("Erro de permissão: A chave de API não é válida. Verifique a chave e tente novamente.")
            st.session_state['genai_configured'] = False
            return None
        except Exception as e:
            st.sidebar.error(f"Erro ao configurar IA: {e}")
            st.session_state['genai_configured'] = False
            return None
            
    st.session_state['genai_configured'] = False
    return None

# --- Funções de Extração de Dados ---

def parse_status(status_text):
    """Normaliza o texto do status."""
    if not isinstance(status_text, str):
        return None
    status_text = status_text.lower()
    if 'passou' in status_text:
        return 'Passou'
    if 'falhado' in status_text or 'falhou' in status_text:
        return 'Falhou'
    if 'bloqueado' in status_text:
        return 'Bloqueado'
    if 'não executado' in status_text:
        return 'Não Executado'
    return None

def extract_data_from_html_doc(file_buffer):
    """
    Extrai e processa dados de teste de um arquivo .doc (formato HTML).
    """
    try:
        try:
            html_content = file_buffer.getvalue().decode('utf-8')
        except UnicodeDecodeError:
            html_content = file_buffer.getvalue().decode('latin-1')

        test_data = {
            'web': defaultdict(int),
            'android': defaultdict(int),
            'ios': defaultdict(int)
        }
        bug_impact_data = defaultdict(lambda: {'description': '', 'Falhou': [], 'Bloqueado': []})
        passed_cases_data = defaultdict(list)

        platform_sections = re.split(r'(<h1 class="doclevel".*?>.*?Plataforma:.*?</h1>)', html_content, flags=re.IGNORECASE)
        
        current_platform = None
        for section in platform_sections:
            if re.search(r'Plataforma:', section, re.IGNORECASE):
                if 'mobile android' in section.lower():
                    current_platform = 'android'
                elif 'mobile ios' in section.lower():
                    current_platform = 'ios'
                elif 'web' in section.lower():
                    current_platform = 'web'
                continue

            if current_platform:
                try:
                    tables = pd.read_html(io.StringIO(section))
                except ValueError:
                    continue

                for df in tables:
                    if df.empty or df.shape[1] < 2:
                        continue
                    if 'Resultado da Execução' not in df.iloc[:, 0].to_string():
                        continue
                    
                    header_html = df.columns.get_level_values(0)[0]
                    tc_title_match = re.search(r'Caso de Teste (PH-\d+:.*?)&nbsp;', header_html)
                    tc_title = tc_title_match.group(1).strip() if tc_title_match else "Título não encontrado"

                    status_text, comment_text = None, None
                    for _, row in df.iterrows():
                        if 'Resultado da Execução' in str(row.iloc[0]):
                            status_text = row.iloc[-1]
                        if 'Comentários' in str(row.iloc[0]):
                            comment_text = row.iloc[-1]
                    
                    status = parse_status(status_text)
                    if status:
                        test_data[current_platform][status] += 1
                        if status == 'Passou':
                            passed_cases_data[current_platform].append(tc_title)
                        elif status in ['Falhou', 'Bloqueado'] and isinstance(comment_text, str):
                            bug_match = re.search(r'(PH-\d+.*?)(?=\s\s|$)', comment_text)
                            if bug_match:
                                bug_id = bug_match.group(1).strip()
                                bug_impact_data[bug_id]['description'] = comment_text.strip()
                                bug_impact_data[bug_id][status].append(tc_title)
        
        total_tcs_per_platform = 20
        for platform in test_data:
            total_parsed = sum(test_data[platform].values())
            if total_parsed < total_tcs_per_platform:
                test_data[platform]['Não Executado'] = total_tcs_per_platform - total_parsed

        return {k: dict(v) for k, v in test_data.items()}, dict(bug_impact_data), dict(passed_cases_data)
    except Exception as e:
        st.error("Ocorreu um erro inesperado ao processar o arquivo.")
        st.code(traceback.format_exc())
        return None, None, None

# --- Funções para Gerar Relatórios com IA ---

def generate_ai_report_platform(genai_instance, test_data, bug_data, passed_data, report_type='resumido'):
    """Gera um relatório detalhado ou resumido por plataforma."""
    plataformas_str = ""
    for p_key, p_value in test_data.items():
        platform_name = {"web": "WEB", "android": "Mobile Android", "ios": "MOBILE iOS"}[p_key]
        total_planned = sum(p_value.values())
        executed = total_planned - p_value.get('Não Executado', 0)
        
        plataformas_str += f"\n- **Plataforma {platform_name}**:\n"
        plataformas_str += f"  - Casos Planejados: {total_planned}\n"
        plataformas_str += f"  - Casos Executados: {executed}\n"
        plataformas_str += f"  - Passou: {p_value.get('Passou', 0)}\n"
        plataformas_str += f"  - Falhou: {p_value.get('Falhou', 0)}\n"
        plataformas_str += f"  - Bloqueado: {p_value.get('Bloqueado', 0)}\n"
        plataformas_str += f"  - Não Executado: {p_value.get('Não Executado', 0)}\n"
        
        if passed_data.get(p_key):
            plataformas_str += f"  - Casos com Sucesso: {', '.join(passed_data[p_key])}\n"

    bugs_str = ""
    if not bug_data:
        bugs_str = "Nenhum bug com impacto direto foi reportado nesta execução."
    else:
        for bug_id, info in bug_data.items():
            bugs_str += f"\n- **Bug {bug_id} ({info['description']})**:\n"
            impacto_str = []
            if info.get('Falhou'):
                impacto_str.append(f"{len(info['Falhou'])} falha(s)")
            if info.get('Bloqueado'):
                impacto_str.append(f"{len(info['Bloqueado'])} bloqueio(s)")
            bugs_str += f"  - Impacto: {', '.join(impacto_str)}\n"
            if report_type == 'detalhado':
                if info.get('Falhou'):
                    bugs_str += "  - Casos que Falharam:\n"
                    for tc in info['Falhou']:
                        bugs_str += f"    - {tc}\n"
                if info.get('Bloqueado'):
                    bugs_str += "  - Casos Bloqueados:\n"
                    for tc in info['Bloqueado']:
                        bugs_str += f"    - {tc}\n"

    prompt_template = f"""
    Você é um assistente de QA. Crie um relatório de andamento de testes para ser postado no Microsoft Teams.
    Use o seguinte formato, incluindo emojis e markdown (negrito com **).

    **Análise dos dados:**
    {plataformas_str}

    **Impactos Encontrados (Bugs):**
    {bugs_str}

    Gere um relatório {'detalhado' if report_type == 'detalhado' else 'resumido'} com base nessas informações.
    """

    model = genai_instance.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt_template)
    return response.text

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
            prompt += f"    - {row['Status']}: {row['Total']} casos\n"
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro ao gerar texto: {e}"

# --- Função Principal da UI ---
def run_dashboard(test_data, bug_impact_data, passed_cases_data, genai_instance):
    """Renderiza o dashboard completo com base nos dados fornecidos."""
    st.title("Dashboard de Qualidade")
    st.markdown("Projeto Payment Hub")
    st.markdown("---")

    total_testes = sum(sum(platform.values()) for platform in test_data.values())
    executados = sum(count for platform_data in test_data.values() for status, count in platform_data.items() if status != 'Não Executado')
    total_passou = sum(d.get('Passou', 0) for d in test_data.values())
    total_falhou = sum(d.get('Falhou', 0) for d in test_data.values())
    total_bloqueado = sum(d.get('Bloqueado', 0) for d in test_data.values())

    cobertura = (executados / total_testes) * 100 if total_testes > 0 else 0
    taxa_sucesso = (total_passou / executados) * 100 if executados > 0 else 0
    taxa_defeito = (total_falhou / executados) * 100 if executados > 0 else 0
    taxa_bloqueio = (total_bloqueado / executados) * 100 if executados > 0 else 0
    
    kpi_cols = st.columns(6)
    kpi_cols[0].metric("Total de Testes", f"{total_testes}")
    kpi_cols[1].metric("Testes Executados", f"{executados}")
    kpi_cols[2].metric("Cobertura de Teste", f"{cobertura:.1f}%")
    kpi_cols[3].metric("Taxa de Sucesso", f"{taxa_sucesso:.1f}%")
    kpi_cols[4].metric("Taxa de Defeito", f"{taxa_defeito:.1f}%")
    kpi_cols[5].metric("Taxa de Bloqueio", f"{taxa_bloqueio:.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)
    chart_cols_top = st.columns([2, 3])

    with chart_cols_top[0]:
        st.subheader("Status Geral de Execução")
        total_not_executed = sum(d.get('Não Executado', 0) for d in test_data.values())
        fig_geral = go.Figure(data=[go.Pie(
            labels=['Passou', 'Falhou', 'Bloqueado', 'Não Executado'],
            values=[total_passou, total_falhou, total_bloqueado, total_not_executed], hole=.4,
            marker_colors=[CHART_COLORS.get(s, '#CCCCCC') for s in ['Passou', 'Falhou', 'Bloqueado', 'Não Executado']],
            textinfo='percent+label'
        )])
        fig_geral.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='#1F2937', font_color='white')
        st.plotly_chart(fig_geral, use_container_width=True)

    with chart_cols_top[1]:
        st.subheader("Status por Plataforma")
        platforms = ['WEB', 'Mobile Android', 'MOBILE iOS']
        statuses = ['Passou', 'Falhou', 'Bloqueado', 'Não Executado']
        fig_plataforma = go.Figure()
        for status in statuses:
            values = [test_data.get(p_key, {}).get(status, 0) for p_key in ['web', 'android', 'ios']]
            fig_plataforma.add_trace(go.Bar(name=status, x=platforms, y=values, marker_color=CHART_COLORS.get(status, '#CCCCCC')))
        fig_plataforma.update_layout(barmode='stack', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), paper_bgcolor='#1F2937', plot_bgcolor='#1F2937', font_color='white')
        st.plotly_chart(fig_plataforma, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if bug_impact_data:
        st.subheader("Impacto de Bugs nos Casos de Teste")
        bug_labels = [f"{k} ({v['description']})" for k, v in bug_impact_data.items()]
        bug_values = [len(v['Falhou']) + len(v['Bloqueado']) for v in bug_impact_data.values()]
        fig_bugs = go.Figure(go.Bar(x=bug_values, y=bug_labels, orientation='h', marker=dict(color='rgba(239, 68, 68, 0.7)')))
        fig_bugs.update_layout(xaxis_title="Casos de Teste Impactados", yaxis=dict(autorange="reversed"), paper_bgcolor='#1F2937', plot_bgcolor='#1F2937', font_color='white')
        st.plotly_chart(fig_bugs, use_container_width=True)

    st.markdown("---")
    
    # Seção do Agente de IA
    st.subheader("🤖 Assistente de Relatórios com IA")
    if genai_instance and st.session_state.get('genai_configured'):
        report_cols = st.columns(3)
        
        # Preparação dos dados para o novo relatório
        kpis_summary = {
            "Total de Casos de Teste": total_testes,
            "Casos Passados": total_passou,
            "Percentual de Execucao": cobertura,
            "Percentual de Sucesso": taxa_sucesso
        }
        total_status_counts = defaultdict(int)
        for platform_data in test_data.values():
            for status, count in platform_data.items():
                total_status_counts[status] += count
        df_status_summary = pd.DataFrame(list(total_status_counts.items()), columns=["Status", "Total"])

        if report_cols[0].button("Gerar Resumo para Teams"):
            with st.spinner("O agente de IA está gerando o resumo..."):
                report = generate_ai_text(df_status_summary, kpis_summary, genai_instance)
                st.text_area("Resumo para Teams (pronto para copiar)", report, height=300)

        if report_cols[1].button("Gerar Relatório Resumido"):
            with st.spinner("O agente de IA está escrevendo o relatório resumido..."):
                report = generate_ai_report_platform(genai_instance, test_data, bug_impact_data, passed_cases_data, 'resumido')
                st.text_area("Relatório Resumido (pronto para copiar)", report, height=300)

        if report_cols[2].button("Gerar Relatório Detalhado"):
            with st.spinner("O agente de IA está escrevendo o relatório detalhado..."):
                report = generate_ai_report_platform(genai_instance, test_data, bug_impact_data, passed_cases_data, 'detalhado')
                st.text_area("Relatório Detalhado (pronto para copiar)", report, height=500)
    else:
        st.warning("🔑 A configuração da IA falhou ou não foi feita. Por favor, insira uma chave de API válida do Google na barra lateral para habilitar o assistente de relatórios.")

# --- Aplicação Principal ---
def main():
    st.sidebar.header("📁 Carregar Relatório")
    st.sidebar.info("Dashboard para relatórios do TestLink (.doc).")
    uploaded_file = st.sidebar.file_uploader("Selecione o arquivo de relatório", type=['doc'])
    
    # Configuração da API de IA na sidebar
    genai_instance = configure_ai()

    if uploaded_file is not None:
        file_buffer = io.BytesIO(uploaded_file.getvalue())
        test_data, bug_impact_data, passed_cases_data = extract_data_from_html_doc(file_buffer)
        
        if test_data:
            run_dashboard(test_data, bug_impact_data, passed_cases_data, genai_instance)
        else:
            st.error("Não foi possível extrair dados do arquivo.")
    else:
        st.info("👈 Carregue um arquivo de relatório para começar.")
        example_test_data = {
            'web': {'Passou': 3, 'Falhou': 3, 'Bloqueado': 8, 'Não Executado': 6},
            'android': {'Não Executado': 20}, 'ios': {'Não Executado': 20}
        }
        example_bug_data = {
            'PH-177': {'description': '[QA] Erro 500 ao finalizar pedido em QAS', 'Falhou': [], 'Bloqueado': ['PH-2', 'PH-4', 'PH-5', 'PH-6', 'PH-7', 'PH-16', 'PH-17', 'PH-20']},
        }
        example_passed_data = {'web': ['PH-13', 'PH-14', 'PH-19']}
        run_dashboard(example_test_data, example_bug_data, example_passed_data, genai_instance)

if __name__ == "__main__":
    main()

