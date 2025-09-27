import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import StringIO

def parse_testlink_xml(xml_file):
    """
    Analisa o conteúdo de um arquivo XML do TestLink e extrai os dados dos casos de teste.
    Retorna uma lista de dicionários, onde cada um representa um caso de teste.
    """
    try:
        # Lê o conteúdo do arquivo carregado
        xml_content = xml_file.getvalue().decode("utf-8")
        tree = ET.parse(StringIO(xml_content))
        root = tree.getroot()
    except ET.ParseError:
        st.error("Erro ao analisar o arquivo XML. Verifique se o formato está correto.")
        return None

    test_cases = []
    # TestLink pode aninhar suites, então usamos a busca recursiva './/'
    for testcase in root.findall('.//testcase'):
        name = testcase.get('name')
        
        # Encontra o status dentro da estrutura de execução
        execution = testcase.find('execution')
        status_node = execution.find('status') if execution is not None else None
        
        # O status no TestLink é um caractere ('p' para pass, 'f' para fail, 'b' para blocked)
        status_char = status_node.text if status_node is not None else 'n' # 'n' para não executado
        
        # Mapeia o caractere para um status legível
        status_map = {'p': 'Passou', 'f': 'Falhou', 'b': 'Bloqueado', 'n': 'Não Executado'}
        status = status_map.get(status_char, 'Desconhecido')
        
        test_cases.append({'Nome do Teste': name, 'Status': status})
        
    return test_cases

# --- Configuração da Página do Streamlit ---
st.set_page_config(page_title="Dashboard TestLink", layout="wide")

st.title("📊 Dashboard Gerencial de Relatórios do TestLink")
st.markdown("Faça o upload do seu relatório de teste exportado do TestLink em formato XML.")

# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Selecione o arquivo XML", type=["xml"])

if uploaded_file is not None:
    # Processa os dados do XML
    data = parse_testlink_xml(uploaded_file)
    
    if data:
        df = pd.DataFrame(data)

        st.markdown("---")

        # --- Métricas Principais ---
        st.header("Visão Geral da Execução")
        
        total_tests = len(df)
        passed_tests = len(df[df['Status'] == 'Passou'])
        failed_tests = len(df[df['Status'] == 'Falhou'])
        blocked_tests = len(df[df['Status'] == 'Bloqueado'])
        
        # Calcula a taxa de sucesso
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Testes", f"{total_tests}")
        col2.metric("✔ Passaram", f"{passed_tests}")
        col3.metric("❌ Falharam", f"{failed_tests}")
        col4.metric("🤚 Bloqueados", f"{blocked_tests}")

        st.progress(pass_rate / 100)
        st.info(f"**Taxa de Sucesso:** {pass_rate:.2f}%")
        
        st.markdown("---")
        
        # --- Visualizações ---
        col_chart, col_details = st.columns([1, 2])

        with col_chart:
            st.header("Resultados por Status")
            status_counts = df['Status'].value_counts()
            st.bar_chart(status_counts)

        with col_details:
            st.header("Detalhes dos Testes com Falha")
            failed_df = df[df['Status'] == 'Falhou']
            if not failed_df.empty:
                st.dataframe(failed_df, use_container_width=True)
            else:
                st.success("Ótima notícia! Nenhum teste falhou.")
else:
    st.info("Aguardando o upload de um arquivo de relatório XML.")
