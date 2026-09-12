# QA Dashboard - Streamlit Cloud

Dashboard interativo para análise de métricas de QA (Quality Assurance) a partir de arquivos PDF do Testlink.

## 🚀 Funcionalidades

- **Upload de PDFs**: Faça upload de relatórios de teste em formato PDF
- **Extração Automática**: Extrai dados de tabelas e texto dos PDFs
- **Visualizações Interativas**: Gráficos de pizza e barras com Plotly
- **KPIs Calculados**: Métricas automáticas de execução e sucesso
- **Exportação CSV**: Baixe os dados processados
- **IA Integrada**: Geração de resumos para Teams (opcional)

## 📊 Métricas Suportadas

- Total de Casos de Teste
- Casos Passados/Falhados/Bloqueados/Não Executados
- Percentual de Execução
- Percentual de Sucesso

## 🛠️ Tecnologias

- **Streamlit**: Interface web interativa
- **Pandas**: Processamento de dados
- **Plotly**: Visualizações interativas
- **PyPDF2 & pdfplumber**: Extração de dados de PDF
- **Google Gemini AI**: Geração de resumos (opcional)

## 🔧 Configuração

### Requisitos
- Python 3.8+
- Dependências listadas em `requirements.txt`

### Instalação Local
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### Deploy no Streamlit Cloud

1. Faça fork deste repositório
2. Conecte sua conta GitHub ao Streamlit Cloud
3. Deploy direto da interface web
4. (Opcional) Configure a chave da API do Google Gemini nos secrets

### Configuração da IA (Opcional)

Para usar a funcionalidade de geração de resumos:

1. Obtenha uma chave da API do Google Gemini em: https://aistudio.google.com/app/apikey
2. No Streamlit Cloud, adicione a chave nos secrets como `GOOGLE_API_KEY`
3. Ou insira manualmente na interface da aplicação

## 📁 Estrutura do Projeto

```
DashQA_Streamlit/
├── streamlit_app.py      # Aplicação principal
├── requirements.txt      # Dependências
└── README.md            # Este arquivo
```

## 🎯 Como Usar

1. **Acesse a aplicação** no Streamlit Cloud ou execute localmente
2. **Faça upload** de um arquivo PDF com métricas de QA
3. **Visualize** os gráficos e KPIs gerados automaticamente
4. **Exporte** os dados em CSV se necessário
5. **Gere resumos** com IA para compartilhar no Teams (opcional)

## 📋 Formatos de PDF Suportados

O dashboard suporta PDFs com:
- Tabelas estruturadas com colunas Status/Total
- Texto com dados de teste organizados
- Relatórios do TestLink e ferramentas similares

## 🔍 Exemplo de Dados

O dashboard reconhece automaticamente status como:
- Passou / Passed
- Falhou / Failed / Falhado
- Bloqueado / Blocked
- Não Executado / Not Executed

## 🤝 Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para:
- Reportar bugs
- Sugerir melhorias
- Enviar pull requests

## 📄 Licença

Este projeto é open source e está disponível sob a licença MIT.

## 🆘 Suporte

Se encontrar problemas:
1. Verifique se o PDF contém dados estruturados
2. Teste com o dashboard de exemplo primeiro
3. Abra uma issue no GitHub com detalhes do erro

---

**Desenvolvido para facilitar a análise de métricas de QA** 📊✨

