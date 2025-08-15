# Guia de Deploy - QA Dashboard no Streamlit Cloud

## 🚀 Como fazer deploy no Streamlit Cloud

### Pré-requisitos
- Conta no GitHub
- Conta no Streamlit Cloud (https://streamlit.io/cloud)

### Passo a Passo

#### 1. Preparar Repositório GitHub
```bash
# Criar novo repositório no GitHub
# Fazer upload dos arquivos do projeto:
# - streamlit_app.py
# - requirements.txt
# - README.md
# - .streamlit/config.toml (opcional)
```

#### 2. Conectar ao Streamlit Cloud
1. Acesse https://share.streamlit.io/
2. Faça login com sua conta GitHub
3. Clique em "New app"
4. Selecione seu repositório
5. Defina o arquivo principal como `streamlit_app.py`
6. Clique em "Deploy!"

#### 3. Configurar Secrets (Opcional)
Para usar a funcionalidade de IA:
1. No painel do Streamlit Cloud, vá em "Settings"
2. Clique em "Secrets"
3. Adicione:
```toml
GOOGLE_API_KEY = "sua_chave_aqui"
```

### 🔧 Estrutura de Arquivos Necessária

```
seu-repositorio/
├── streamlit_app.py      # Arquivo principal (obrigatório)
├── requirements.txt      # Dependências (obrigatório)
├── README.md            # Documentação
├── .streamlit/
│   └── config.toml      # Configurações (opcional)
└── DEPLOY_GUIDE.md      # Este guia
```

### 📋 Checklist de Deploy

- [ ] Repositório GitHub criado
- [ ] Arquivos principais commitados
- [ ] requirements.txt atualizado
- [ ] Streamlit Cloud conectado
- [ ] App deployado com sucesso
- [ ] Funcionalidades testadas
- [ ] (Opcional) Secrets configurados para IA

### 🔍 Troubleshooting

#### Erro de dependências
- Verifique se todas as dependências estão no `requirements.txt`
- Use versões específicas se necessário

#### Erro de secrets
- A aplicação funciona sem secrets (IA fica opcional)
- Verifique se a chave da API está correta

#### Erro de upload
- Limite de 200MB por arquivo
- Apenas arquivos PDF são aceitos

### 🌐 URL de Exemplo
Após o deploy, sua aplicação estará disponível em:
`https://[nome-do-app]-[hash].streamlit.app/`

### 📞 Suporte
- Documentação oficial: https://docs.streamlit.io/
- Community forum: https://discuss.streamlit.io/
- GitHub Issues: Para problemas específicos do projeto

