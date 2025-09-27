import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
import re
import plotly.graph_objects as go
import plotly.express as px

def parse_testlink_html(html_file):
    """
    Analisa o conteúdo de um arquivo de relatório HTML do TestLink 1.9.20
    e extrai os dados dos casos de teste.
    """
    try:
        html_content = html_file.getvalue().decode("utf-8")
        soup = BeautifulSoup(html_content, 'lxml')
    except Exception as e:
        st.error(f"Erro ao ler o arquivo HTML: {e}")
        return None

    test_cases = []
    
    all_test_case_tables = soup.find_all('table', class_='tc')

    if not all_test_case_tables:
        st.warning("Nenhum caso de teste encontrado no relatório. Verifique se o arquivo HTML é um relatório de execução válido.")
        return None

    for table in all_test_case_tables:
        th = table.find('th')
        case_name = th.text.strip() if th else "Nome não encontrado"

        suite_header = table.find_previous('h3')
        suite_name = suite_header.text.replace("Suite de Testes :", "").strip() if suite_header else "Suíte Desconhecida"

        status = "Não Executado"
        notes = ""

        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if not cells:
                continue
            
            label_cell = cells[0]
            if "Resultado da Execução:" in label_cell.text:
                status_cell = cells[1] if len(cells) > 1 else None
                if status_cell and status_cell.b:
                    status = status_cell.b.text.strip()
            
            if "Notas" in label_cell.text:
                 notes_cell = cells[1] if len(cells) > 1 else None
                 if notes_cell:
                     notes = notes_cell.text.strip()
        
        defects_found = re.findall(r'(?i)(?:defeito|bug|issue)[\s:#]*([A-Z_]+-\d+|\d+)', notes)

        test_cases.append({
            'Issue (Suíte)': suite_name,
            'Nome do Teste': case_name,
            'Status': status,
            'Notas': notes,
            'Defeitos': ', '.join(defects_found)
        })
            
    return test_cases

# --- Configuração da Página do Streamlit ---
st.set_page_config(page_title="Dashboard TestLink", layout="wide")

st.title("📊 Dashboard Gerencial de Relatórios do TestLink")
st.markdown("Faça o upload do seu relatório de teste exportado do TestLink em formato **HTML**.")

uploaded_file = st.file_uploader("Selecione o arquivo HTML", type=["html", "htm"])

if uploaded_file is not None:
    data = parse_testlink_html(uploaded_file)
    
    if data:
        df = pd.DataFrame(data)
        st.markdown("---")

        # --- Paleta de Cores Padronizada ---
        STATUS_COLORS = {
            'Passou': '#28a745',        # Verde
            'Falhou': '#FF2800',        # Vermelho Ferrari
            'Bloqueado': '#FFDB58',     # Amarelo Mostarda
            'Não Executado': '#007bff'  # Azul
        }

        # --- Métricas Principais e Velocímetro ---
        st.header("Visão Geral da Execução")
        
        total_tests = len(df)
        passed_tests = len(df[df['Status'] == 'Passou'])
        failed_tests = len(df[df['Status'] == 'Falhou'])
        blocked_tests = len(df[df['Status'] == 'Bloqueado'])
        
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Total de Testes", f"{total_tests}")
            st.metric("✔ Passaram", f"{passed_tests}")
            st.metric("❌ Falharam", f"{failed_tests}")
            st.metric("🤚 Bloqueados", f"{blocked_tests}")
        
        with col2:
            # --- Gráfico de Velocímetro (Gauge) com ponteiro ---
            gauge_chart = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = pass_rate,
                title = {'text': "Taxa de Sucesso (%)"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'steps' : [
                        {'range': [0, 70], 'color': "#FF4B4B"},
                        {'range': [70, 90], 'color': "yellow"},
                        {'range': [90, 100], 'color': "#28a745"}],
                    'bar': {'color': "rgba(0,0,0,0)"}, # Deixa a barra principal transparente
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.85,
                        'value': pass_rate} # O ponteiro é a linha 'threshold'
                }
            ))
            gauge_chart.update_layout(height=350)
            st.plotly_chart(gauge_chart, use_container_width=True)


        st.markdown("---")
        
        # --- Análise por Suíte ---
        st.header("Análise de Status por Suíte")
        col_bar, col_detail = st.columns(2)

        with col_bar:
            st.subheader("Resultados Agrupados")
            suite_status = df.groupby(['Issue (Suíte)', 'Status']).size().unstack(fill_value=0)
            color_sequence = [STATUS_COLORS.get(col, '#CCCCCC') for col in suite_status.columns]
            st.bar_chart(suite_status, color=color_sequence)

        with col_detail:
            st.subheader("Detalhes por Issue")
            suite_summary = df.groupby('Issue (Suíte)').agg(
                total_casos=('Nome do Teste', 'count'),
                passaram=('Status', lambda s: (s == 'Passou').sum()),
                falharam=('Status', lambda s: (s == 'Falhou').sum())
            ).reset_index()
            st.dataframe(suite_summary, use_container_width=True, hide_index=True)

        # --- Gráfico de Pizza ---
        st.subheader("Distribuição Geral de Status (%)")
        status_counts = df['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'count']
        pie_chart = px.pie(
            status_counts,
            values='count', 
            names='Status',
            color='Status',
            color_discrete_map=STATUS_COLORS
        )
        pie_chart.update_traces(textinfo='percent+label', textfont_size=14)
        st.plotly_chart(pie_chart, use_container_width=True)

        st.markdown("---")
        st.header("Detalhes de Todos os Casos de Teste")
        st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Aguardando o upload de um arquivo de relatório HTML.")
