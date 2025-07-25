# Estratégia Concursos - Downloader de Cursos

Este é um script em Python para automatizar o download de materiais de cursos da plataforma Estratégia Concursos. Ele utiliza Selenium para navegar no site e `requests` para baixar os arquivos, organizando tudo em uma estrutura de pastas local.

## Funcionalidades

  - **Login Manual:** O script abre a página de login e aguarda que o usuário insira suas credenciais manualmente.
  - **Configuração Flexível:** Permite configurar o diretório de download e o tempo de espera para o login diretamente pela linha de comando.
  - **Listagem de Cursos:** Identifica e lista todos os cursos disponíveis na sua página "Meus Cursos".
  - **Extração de Aulas:** Para cada curso, o script acessa a página e extrai a lista completa de aulas disponíveis.
  - **Organização de Arquivos:** Cria uma estrutura de pastas hierárquica para os materiais baixados: `DIRETÓRIO_DE_DOWNLOAD / NOME_DO_CURSO / NOME_DA_AULA /`.
  - **Download de Materiais Diversos:**
      - **Livros Eletrônicos (PDFs):** Baixa o PDF principal da aula e suas diferentes versões (ex: para impressão, simplificado).
      - **Vídeos:** Baixa todos os vídeos da playlist da aula, priorizando a melhor qualidade disponível (720p \> 480p \> 360p).
      - **Materiais de Apoio dos Vídeos:** Baixa os materiais associados a cada vídeo, como **Resumos**, **Slides** e **Mapas Mentais**.
      - **Assuntos da Aula:** Salva o resumo dos tópicos da aula em um arquivo `Assuntos_dessa_aula.txt`.
  - **Verificação de Arquivos:** O script verifica se um arquivo já existe antes de tentar baixá-lo, evitando downloads duplicados.
  - **Sanitização de Nomes:** Remove caracteres inválidos de nomes de arquivos e pastas para garantir a compatibilidade com o sistema de arquivos.

## Pré-requisitos

  - **Python 3.x**
  - **Navegador Microsoft Edge**
  - Uma conta ativa na plataforma Estratégia Concursos com cursos adquiridos.

## Instalação

1.  **Clone ou baixe este repositório:**

    ```bash
    git clone https://github.com/DemiurgoGM/AutoDownloadEstrategiaConcurso.git
    cd AutoDownloadEstrategiaConcurso
    ```

2.  **Instale as bibliotecas Python necessárias:**
    O script requer as bibliotecas `selenium` e `requests`. Você pode instalá-las usando `pip`:

    ```bash
    pip install selenium requests
    ```

3.  **WebDriver do Edge:**
    O Selenium 4 e superior geralmente gerencia o `msedgedriver` automaticamente. Se você encontrar problemas, certifique-se de que sua versão do Microsoft Edge está atualizada.

## Configuração (Via Linha de Comando)

A configuração do script é feita de forma flexível através de argumentos na linha de comando. 

### Argumentos Disponíveis:

  - `-d, --dir PATH`

      - Define o diretório de download. Substitua `PATH` pelo caminho completo onde os cursos serão salvos.
      - **Se não for fornecido, usará o valor padrão definido no script (`E:/Estrategia`).**

  - `-w, --wait-time SECONDS`

      - Define o tempo de espera (em segundos) para que você realize o login manual.
      - **O padrão é 60 segundos.**

## Como Usar

1.  Abra um terminal (Prompt de Comando, PowerShell, ou Terminal do Linux/macOS).
2.  Navegue até o diretório onde você salvou o script.
3.  Execute o script usando `python` e os argumentos desejados.

-----

### **Exemplos de Uso:**

**1. Uso Básico (utiliza os valores padrão)**

```bash
python main.py
```

> O script salvará os arquivos em `E:/Estrategia` e aguardará `60` segundos pelo login.

**2. Definindo um Diretório de Download Específico**

```bash
# Para Windows
python main.py --dir "C:\Users\SeuNome\Downloads\CursosEstrategia"

# Para Linux/macOS (forma longa)
python main.py --dir "/home/seu-usuario/Documentos/Cursos"

# Para Linux/macOS (forma curta)
python main.py -d "/home/seu-usuario/Documentos/Cursos"
```

> **Dica:** Use aspas `""` ao redor do caminho se ele contiver espaços.

**3. Aumentando o Tempo de Espera para o Login**

```bash
# Aumenta o tempo de espera para 2 minutos (120 segundos)
python main.py --wait-time 120

# Forma curta
python main.py -w 120
```

**4. Combinando Argumentos**

```bash
# Salva os cursos em D:\Concursos e aguarda 90 segundos pelo login
python main.py -d "D:\Concursos" -w 90
```

-----

4.  Após executar o comando, uma janela do navegador Microsoft Edge será aberta na página de login do Estratégia.
5.  **Você terá o tempo configurado (padrão: 60s) para fazer o login manualmente.**
6.  Após o login, não feche o navegador. O script retomará automaticamente e começará o processo de download.
7.  Aguarde o término do processo. O progresso será exibido no terminal.

## Como Funciona

1.  **Autenticação:** O script pausa para permitir que o usuário realize o login de forma segura.
2.  **Coleta de Cursos:** Navega até a página de matrículas (`/app/dashboard/cursos`) e extrai os links e títulos de todos os cursos.
3.  **Coleta de Aulas:** Itera sobre cada curso, acessa sua página e coleta os detalhes de cada aula (título, subtítulo e URL).
4.  **Processamento da Aula:** Para cada aula, ele:
      - Cria as pastas de destino (`/Curso/Aula/`).
      - Acessa a URL da aula.
      - Procura e baixa todos os botões de download de **Livros Eletrônicos (PDFs)**.
      - Procura pela playlist de vídeos e, para cada vídeo na lista, ele:
          - Navega para a página do vídeo.
          - Procura e baixa materiais de apoio específicos (Resumos, Slides, Mapas Mentais).
          - Expande a seção "Opções de download" e baixa o arquivo de vídeo na melhor qualidade disponível.
5.  **Finalização:** Após processar todos os cursos e aulas, o script aguarda 10 segundos e fecha o navegador.

## ⚠️ Aviso Legal

  - Este script destina-se **exclusivamente para uso pessoal**, para facilitar o backup dos materiais de cursos que você **legalmente adquiriu**.
  - A redistribuição do conteúdo baixado é proibida e viola os Termos de Serviço do Estratégia Concursos.
  - O web scraping pode sobrecarregar os servidores do site. Use o script de forma consciente.
  - Este script depende da estrutura HTML e CSS do site do Estratégia Concursos. **Qualquer alteração no site pode fazer com que o script pare de funcionar.**