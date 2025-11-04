# AutoDownloader v2.0

Sistema automatizado de download de materiais de cursos da plataforma Estratégia Concursos.

## 📋 Características

- **Modular**: Código organizado em pacotes especializados
- **Configurável**: Configurações centralizadas via arquivo `.env`
- **Rastreável**: Sistema de manifesto para rastrear downloads
- **Notificações**: Integração com Telegram para acompanhamento
- **Logging**: Sistema de logs completo e estruturado
- **Type Hints**: Código com anotações de tipo para melhor manutenibilidade
- **Documentado**: Docstrings completas em todas as funções e classes

## 🏗️ Arquitetura

```
autodownloader/
├── config/              # Configurações e constantes
│   ├── settings.py      # Configurações do sistema
│   └── constants.py     # Constantes e mapeamentos
├── core/                # Lógica principal
│   ├── authentication.py # Gerenciamento de login
│   └── session.py       # Manutenção de sessão
├── models/              # Modelos de dados
│   ├── course.py        # Modelo de Curso
│   └── lesson.py        # Modelo de Aula
├── services/            # Serviços especializados
│   ├── file_service.py  # Download de arquivos
│   └── manifest_service.py # Gerenciamento de manifesto
├── notifications/       # Sistema de notificações
│   ├── telegram.py      # Notificações Telegram
│   └── logger.py        # Configuração de logging
├── utils/               # Utilitários
│   ├── file_utils.py    # Manipulação de arquivos
│   ├── time_utils.py    # Manipulação de tempo
│   └── validators.py    # Validações
├── detectors/           # Detectores
│   └── pending_detector.py # Detecção de pendências
├── tests/               # Testes unitários
├── main.py              # Ponto de entrada
├── requirements.txt     # Dependências
├── .env.example         # Exemplo de configuração
└── README.md            # Este arquivo
```

## 🚀 Instalação

### 1. Clonar/Baixar o Projeto

```bash
cd autodownloader
```

### 2. Criar Ambiente Virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente

```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

## ⚙️ Configuração

### Telegram (Opcional)

Para receber notificações via Telegram:

1. Abra o Telegram e busque por `@BotFather`
2. Digite `/newbot` e siga as instruções
3. Copie o **TOKEN** fornecido
4. Inicie uma conversa com seu bot
5. Acesse: `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
6. Copie o **chat_id** que aparecer
7. Configure no arquivo `.env`:

```env
TELEGRAM_ENABLED=True
TELEGRAM_BOT_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui
```

## 📖 Uso

### Modo Básico

```bash
python main.py
```

### Especificar Diretório de Download

```bash
python main.py --download-dir /caminho/para/downloads
```

### Verificar Cursos Pendentes

```bash
python main.py --check-pending
```

### Desabilitar Telegram

```bash
python main.py --no-telegram
```

### Ajustar Nível de Log

```bash
python main.py --log-level DEBUG
```

### Ver Ajuda

```bash
python main.py --help
```

## 📊 Sistema de Manifesto

O AutoDownloader mantém um arquivo `files_manifest.json` em cada curso baixado, contendo:

- Timestamp de cada download
- Nome e tamanho dos arquivos
- Tipo de arquivo (PDF, vídeo, etc.)
- Tempo de download
- Status (sucesso, erro, pulado)

Exemplo:

```json
{
  "Aula 01 - Introdução": {
    "timestamp": "2024-01-15T10:30:00",
    "total_files": 3,
    "files": [
      {
        "name": "aula01.pdf",
        "size_bytes": 1048576,
        "size_mb": 1.0,
        "type": "pdf",
        "download_time": "00:00:05",
        "status": "success",
        "added_at": "2024-01-15T10:30:05"
      }
    ],
    "completed_at": "2024-01-15T10:35:00"
  }
}
```

## 🧪 Testes

```bash
# Executar todos os testes
pytest

# Com cobertura
pytest --cov=autodownloader

# Testes específicos
pytest tests/test_utils.py
```

## 🔧 Desenvolvimento

### Estrutura de Código

O projeto segue os princípios **SOLID** e boas práticas Python:

- **Single Responsibility**: Cada módulo tem uma responsabilidade única
- **Open/Closed**: Extensível sem modificar código existente
- **Liskov Substitution**: Subtipos substituíveis
- **Interface Segregation**: Interfaces específicas
- **Dependency Inversion**: Dependência de abstrações

### Type Hints

Todo o código utiliza type hints para melhor IDE support e type checking:

```python
def download_file(url: str, path: str) -> bool:
    ...
```

### Docstrings

Todas as funções e classes possuem docstrings no formato Google:

```python
def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitiza nome de arquivo removendo caracteres inválidos.

    Args:
        filename: Nome original do arquivo
        max_length: Tamanho máximo do nome

    Returns:
        str: Nome sanitizado

    Examples:
        >>> sanitize_filename("Aula 01: Introdução")
        'Aula 01 Introdução'
    """
```

## 📝 Logging

O sistema de logging registra:

- **DEBUG**: Informações detalhadas para diagnóstico
- **INFO**: Confirmação de operações normais
- **WARNING**: Avisos sobre situações inesperadas
- **ERROR**: Erros que não impedem execução
- **CRITICAL**: Erros graves que impedem execução

Logs são salvos em:
- Console (stdout)
- Arquivo `autodownloader.log`
- Arquivo específico por curso em `<curso>/logs/`

## 🔒 Segurança

- Credenciais nunca são hardcoded
- Variáveis sensíveis em arquivo `.env` (não versionado)
- `.env.example` fornecido como template
- Cookies de sessão armazenados localmente

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto é fornecido "como está" para fins educacionais.

## 🙏 Agradecimentos

- Comunidade Python
- Selenium WebDriver
- Estratégia Concursos (plataforma)

## 📞 Suporte

Para dúvidas e suporte, consulte a documentação completa em PDF.

---

**Versão**: 1.0.0  
**Status**: Refatorado e Modular  
**Última Atualização**: 03/11/2025
