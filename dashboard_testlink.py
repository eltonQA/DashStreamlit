import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
import re

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
    
    # Encontra todas as tabelas que representam casos de teste (pela classe 'tc')
    all_test_case_tables = soup.find_all('table', class_='tc')

    if not all_test_case_tables:
        st.warning("Nenhum caso de teste encontrado no relatório. Verifique se o arquivo HTML é um relatório de execução válido.")
        return None

    for table in all_test_case_tables:
        # 1. Extrair o Nome do Caso de Teste (está no cabeçalho <th>)
        th = table.find('th')
        case_name = th.text.strip() if th else "Nome não encontrado"

        # 2. Extrair a Suíte de Teste (está no <h3> anterior à tabela)
        suite_header = table.find_previous('h3')
        suite_name = suite_header.text.replace("Suite de Testes :", "").strip() if suite_header else "Suíte Desconhecida"

        status = "Não Executado"
        notes = ""

        # 3. Iterar pelas linhas da tabela para encontrar Status e Notas
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if not cells:
                continue

            # Procura pela célula que contém o label "Resultado da Execução:"
            label_cell = cells[0]
            if "Resultado da Execução:" in label_cell.text:
                status_cell = cells[1] if len(cells) > 1 else None
                if status_cell and status_cell.b:
                    status = status_cell.b.text.strip()
            
            # (Opcional) Procura por uma célula de Notas. 
            # Como não há no seu exemplo, essa lógica pode ser adaptada se necessário.
            if "Notas" in label_cell.text: # Supondo que haveria um label 'Notas'
                 notes_cell = cells[1] if len(cells) > 1 else None
                 if notes_cell:
                     notes = notes_cell.text.strip()
        
        # Como não há campo de notas explícito, a busca por defeitos pode não funcionar.
        # Mantemos a lógica caso o campo seja adicionado em testes falhados.
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

# --- Upload do Arquivo ---
uploaded_file = st.file_uploader("Selecione o arquivo HTML", type=["html", "htm"])

if uploaded_file is not None:
    data = parse_testlink_html(uploaded_file)
    
    if data:
        df = pd.DataFrame(data)

        st.markdown("---")

        # --- Métricas Principais ---
        st.header("Visão Geral da Execução")
        
        total_tests = len(df)
        passed_tests = len(df[df['Status'] == 'Passou'])
        failed_tests = len(df[df['Status'] == 'Falhou'])
        blocked_tests = len(df[df['Status'] == 'Bloqueado'])

        all_defects = df[df['Defeitos'] != '']['Defeitos'].str.split(', ').explode().unique()
        total_defects = len(all_defects)
        
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        defect_rate = (total_defects / total_tests * 100) if total_tests > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Testes", f"{total_tests}")
        col2.metric("✔ Passaram", f"{passed_tests}")
        col3.metric("❌ Falharam", f"{failed_tests}")
        col4.metric("Total de Defeitos", f"{total_defects}")

        st.subheader(f"Taxa de Sucesso: {pass_rate:.2f}%")
        st.progress(pass_rate / 100)
        
        if total_defects > 0:
            st.subheader(f"Taxa de Defeitos (Geral): {defect_rate:.2f}%")
            st.info(f"Calculado com base em {total_defects} defeitos únicos encontrados em {total_tests} casos de teste.")
        
        st.markdown("---")
        
        # --- Análise por Suíte ---
        col_suite_chart, col_suite_table = st.columns(2)

        with col_suite_chart:
            st.header("Resultados por Suíte")
            suite_status = df.groupby(['Issue (Suíte)', 'Status']).size().unstack(fill_value=0)
            st.bar_chart(suite_status)

        with col_suite_table:
            st.header("Detalhes por Suíte")
            suite_summary = df.groupby('Issue (Suíte)').agg(
                total_casos=('Nome do Teste', 'count'),
                passaram=('Status', lambda s: (s == 'Passou').sum()),
                falharam=('Status', lambda s: (s == 'Falhou').sum())
            ).reset_index()
            st.dataframe(suite_summary, use_container_width=True, hide_index=True)

        st.markdown("---")

        st.header("Detalhes de Todos os Casos de Teste")
        st.dataframe(df, use_container_width=True)

else:
    st.info("Aguardando o upload de um arquivo de relatório HTML.")
