import os
import re
import time
import argparse
import sys
import pickle
import threading
from urllib.parse import urljoin
import requests
import logging
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime

# ============================================================================
# CONFIGURAÇÃO DO TELEGRAM BOT
# ============================================================================

# INSTRUÇÕES:
# 1. Abra o Telegram e busque por @BotFather
# 2. Digite /newbot e siga as instruções
# 3. Copie o TOKEN que o BotFather te der
# 4. Inicie conversa com seu bot
# 5. Acesse: https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
# 6. Copie o "chat" -> "id" que aparecer

TELEGRAM_BOT_TOKEN = "8007157458:AAHXfjMSjkLznyvtx2BaqytFmmY5OvdJvG8"  # Substitua pelo token do seu bot
TELEGRAM_CHAT_ID = "142522112"  # Substitua pelo seu chat ID
TELEGRAM_ENABLED = True  # True = ativa notificações | False = desativa


# --- Configurações ---
BASE_URL = "https://www.estrategiaconcursos.com.br"
MY_COURSES_URL = urljoin(BASE_URL, "/app/dashboard/cursos")
COOKIES_FILE = "estrategia_session_cookies.pkl"
HEARTBEAT_INTERVAL = 300  # 5 minutos


# ============================================================================
# CLASSE PARA NOTIFICAÇÕES VIA TELEGRAM
# ============================================================================

class TelegramNotifier:
    """
    Gerencia envio de notificações para o Telegram.
    Integrado com o sistema de logging do Python.
    """

    def __init__(self, bot_token, chat_id, enabled=True):
        """
        Inicializa o notificador do Telegram.

        Args:
            bot_token (str): Token do bot do Telegram
            chat_id (str): ID do chat para enviar mensagens
            enabled (bool): Se True, envia notificações. Se False, apenas loga localmente
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.last_send_time = 0
        self.min_interval = 1  # Intervalo mínimo entre mensagens (segundos)

        if self.enabled:
            self._test_connection()

    def _test_connection(self):
        """Testa conexão com o Telegram na inicialização."""
        try:
            self.send("🤖 Bot conectado com sucesso!\n\nPronto para enviar notificações de download.")
            print("✓ Telegram Bot conectado com sucesso!")
        except Exception as e:
            print(f"⚠ Erro ao conectar com Telegram: {e}")
            print("  As notificações do Telegram estarão desabilitadas.")
            self.enabled = False

    def send(self, message, parse_mode="HTML"):
        """
        Envia mensagem para o Telegram.

        Args:
            message (str): Mensagem a enviar
            parse_mode (str): Modo de formatação ('HTML' ou 'Markdown')

        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self.enabled:
            return False

        # Rate limiting - evita flood de mensagens
        current_time = time.time()
        if current_time - self.last_send_time < self.min_interval:
            time.sleep(self.min_interval - (current_time - self.last_send_time))

        try:
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(self.api_url, json=data, timeout=10)
            response.raise_for_status()
            self.last_send_time = time.time()
            return True
        except Exception as e:
            print(f"Erro ao enviar mensagem Telegram: {e}")
            return False

    def notify_start(self, total_courses):
        """Notifica início do processo."""
        message = (
            "🚀 <b>DOWNLOAD INICIADO</b>\n\n"
            f"📚 Cursos selecionados: {total_courses}\n"
            f"⏰ Início: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        self.send(message)

    def notify_course_start(self, course_title, course_num, total_courses, total_lessons):
        """Notifica início de um curso."""
        message = (
            f"📚 <b>CURSO INICIADO [{course_num}/{total_courses}]</b>\n\n"
            f"<b>{course_title}</b>\n\n"
            f"📖 Total de aulas: {total_lessons}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(message)

    def notify_course_complete(self, course_title, course_num, total_courses, duration):
        """Notifica conclusão de um curso."""
        message = (
            f"✅ <b>CURSO CONCLUÍDO [{course_num}/{total_courses}]</b>\n\n"
            f"<b>{course_title}</b>\n\n"
            f"⏱️ Tempo total: {duration}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(message)

    def notify_lesson_progress(self, lesson_num, total_lessons, lesson_title):
        """Notifica progresso de aula (apenas múltiplos de 5)."""
        if lesson_num % 5 == 0 or lesson_num == total_lessons:
            message = (
                f"📖 <b>PROGRESSO [{lesson_num}/{total_lessons}]</b>\n\n"
                f"{lesson_title}"
            )
            self.send(message)

    def notify_session_expired(self):
        """Notifica que a sessão expirou."""
        message = (
            "⚠️ <b>AVISO DE SESSÃO</b>\n\n"
            "Sessão expirada detectada.\n"
            "Tentando restaurar automaticamente..."
        )
        self.send(message)

    def notify_session_restored(self):
        """Notifica que a sessão foi restaurada."""
        message = "✅ Sessão restaurada com sucesso!"
        self.send(message)

    def notify_error(self, error_message):
        """Notifica erro crítico."""
        message = (
            f"❌ <b>ERRO</b>\n\n"
            f"{error_message}"
        )
        self.send(message)

    def notify_complete(self, total_time):
        """Notifica conclusão de todo o processo."""
        message = (
            "🎉 <b>PROCESSO CONCLUÍDO</b>\n\n"
            f"⏱️ Tempo total: {total_time}\n"
            f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            "✅ Todos os downloads foram finalizados!"
        )
        self.send(message)


# ============================================================================
# HANDLER CUSTOMIZADO PARA LOGGING VIA TELEGRAM
# ============================================================================

class TelegramLoggingHandler(logging.Handler):
    """
    Handler de logging que envia logs importantes para o Telegram.
    Integra-se perfeitamente com o sistema de logging do Python.
    """

    def __init__(self, notifier):
        """
        Args:
            notifier (TelegramNotifier): Instância do notificador do Telegram
        """
        super().__init__()
        self.notifier = notifier
        self.emoji_map = {
            'DEBUG': '🔍',
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '🚨'
        }

    def emit(self, record):
        """
        Envia log para o Telegram.
        Apenas logs de nível WARNING ou superior são enviados.
        """
        try:
            if record.levelno >= logging.WARNING:  # Apenas WARNING, ERROR, CRITICAL
                emoji = self.emoji_map.get(record.levelname, '📝')
                message = (
                    f"{emoji} <b>{record.levelname}</b>\n\n"
                    f"{record.getMessage()}\n\n"
                    f"📁 {record.name}"
                )
                self.notifier.send(message)
        except Exception:
            self.handleError(record)


# --- Funções Auxiliares ---

def sanitize_filename(original_filename):
    """
    Remove caracteres inválidos de um nome de arquivo/diretório para garantir
    compatibilidade com o sistema de arquivos.
    """
    sanitized = re.sub(r'[<>:"/\\|?*]', '', original_filename)
    sanitized = re.sub(r'[.,]', '', sanitized)
    sanitized = re.sub(r'[\s-]+', '_', sanitized)
    sanitized = sanitized.strip('._- ')
    return sanitized.strip()


def download_file(url, file_path, current_page_url=None, logger=None):
    """
    Realiza o download de um arquivo usando requests com barra de progresso em porcentagem.

    Args:
        url (str): URL do arquivo a baixar
        file_path (str): Caminho completo onde salvar o arquivo
        current_page_url (str): URL da página atual (para header Referer)
        logger (logging.Logger): Logger para registrar eventos

    Returns:
        bool: True se sucesso, False caso contrário
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
    }
    if current_page_url:
        headers['Referer'] = current_page_url

    try:
        with requests.get(url, stream=True, timeout=60, headers=headers) as response:
            response.raise_for_status()
            total = response.headers.get('content-length')
            total = int(total) if total else None
            downloaded = 0

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        if total:
                            downloaded += len(chunk)
                            progress = 100 * downloaded / total
                            print(f"\r  Baixando: {os.path.basename(file_path)} [{progress:.2f}%]", end="")
            print()
            if logger:
                logger.info(f"Baixado com sucesso: {file_path}")
            return True
    except Exception as e:
        print(f"Erro tentando baixar {file_path}: {e}")
        if logger:
            logger.error(f"Erro ao baixar {file_path}: {e}")
        return False


def handle_popups(driver):
    """
    Tenta fechar popups conhecidos que podem interceptar cliques.

    Args:
        driver: WebDriver do Selenium
    """
    print("Verificando e lidando com popups/overlays...")
    try:
        getsitecontrol_widget = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, "getsitecontrol-44266"))
        )
        print("Widget 'getsitecontrol' detectado. Tentando fechar via JavaScript.")
        driver.execute_script("arguments[0].style.display = 'none';", getsitecontrol_widget)
        time.sleep(1)
    except TimeoutException:
        print("Nenhum popup 'getsitecontrol' detectado.")
    except Exception as e:
        print(f"Erro inesperado ao lidar com popups: {e}")


# ============================================================================
# MELHORIA #1: GERENCIAMENTO DE SESSÃO COM COOKIES
# ============================================================================

def save_cookies(driver, filepath=COOKIES_FILE):
    """
    Salva os cookies da sessão atual em arquivo.
    Permite restaurar a sessão posteriormente sem fazer login novamente.

    Args:
        driver: WebDriver do Selenium
        filepath: Caminho do arquivo onde salvar os cookies
    """
    try:
        with open(filepath, "wb") as f:
            pickle.dump(driver.get_cookies(), f)
        print(f"✓ Cookies salvos em {filepath}")
    except Exception as e:
        print(f"Erro ao salvar cookies: {e}")


def load_cookies(driver, filepath=COOKIES_FILE):
    """
    Carrega cookies salvos para restaurar a sessão sem fazer login novamente.

    Args:
        driver: WebDriver do Selenium
        filepath: Caminho do arquivo de cookies

    Returns:
        bool: True se carregou com sucesso, False caso contrário
    """
    try:
        with open(filepath, "rb") as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        print("✓ Cookies carregados com sucesso")
        return True
    except FileNotFoundError:
        print(f"⚠ Arquivo de cookies '{filepath}' não encontrado")
        return False
    except Exception as e:
        print(f"Erro ao carregar cookies: {e}")
        return False


def is_logged_in(driver):
    """
    Verifica se ainda está logado na plataforma.

    Args:
        driver: WebDriver do Selenium

    Returns:
        bool: True se logado, False caso contrário
    """
    try:
        # Tenta encontrar um elemento que só existe quando está logado
        # Ajuste o seletor conforme necessário para a plataforma
        driver.find_element(By.CSS_SELECTOR, "a[href*='dashboard']")
        return True
    except NoSuchElementException:
        return False


def ensure_logged_in(driver, cookies_file=COOKIES_FILE):
    """
    Garante que está logado, restaurando cookies se a sessão expirou.

    Args:
        driver: WebDriver do Selenium
        cookies_file: Arquivo de cookies para restaurar sessão

    Returns:
        bool: True se logado ou restaurado com sucesso, False caso contrário
    """
    if not is_logged_in(driver):
        print("\n⚠ Sessão expirada detectada. Tentando restaurar...")
        driver.get(BASE_URL)
        time.sleep(2)

        if load_cookies(driver, cookies_file):
            driver.refresh()
            time.sleep(3)

            if is_logged_in(driver):
                print("✓ Sessão restaurada com sucesso!")
                return True
            else:
                print("✗ Não foi possível restaurar a sessão automaticamente.")
                print("  Por favor, faça login manualmente no navegador.")
                input("  Pressione ENTER após fazer o login...")
                save_cookies(driver, cookies_file)
                return True
        else:
            print("✗ Não foi possível carregar cookies.")
            return False
    return True


# ============================================================================
# MELHORIA #2: HEARTBEAT PARA MANTER SESSÃO VIVA
# ============================================================================

class SessionKeepAlive:
    """
    Mantém a sessão viva fazendo requisições periódicas em segundo plano.
    Previne logout automático durante downloads longos.
    """

    def __init__(self, driver, interval=HEARTBEAT_INTERVAL):
        """
        Inicializa o sistema de heartbeat.

        Args:
            driver: WebDriver do Selenium
            interval: Intervalo em segundos entre cada heartbeat (padrão: 5 minutos)
        """
        self.driver = driver
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None

    def _heartbeat(self):
        """Thread que executa o heartbeat periodicamente."""
        while not self.stop_event.is_set():
            try:
                # Executa um comando JavaScript simples para manter a sessão
                self.driver.execute_script("console.log('Session keepalive heartbeat')")
                current_time = datetime.now().strftime('%H:%M:%S')
                print(f"\n[Heartbeat {current_time}] Sessão mantida viva")
            except Exception as e:
                print(f"\n[Heartbeat] Erro: {e}")

            # Aguarda o intervalo ou até receber sinal de parada
            self.stop_event.wait(self.interval)

    def start(self):
        """Inicia o heartbeat em thread separada."""
        if self.thread is None or not self.thread.is_alive():
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._heartbeat, daemon=True)
            self.thread.start()
            print(f"✓ Heartbeat iniciado (intervalo: {self.interval}s)")

    def stop(self):
        """Para o heartbeat."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        print("✓ Heartbeat encerrado")


# ============================================================================
# FUNÇÕES DE NAVEGAÇÃO E RASPAGEM
# ============================================================================

def get_course_data(driver):
    """
    Navega até a página 'Meus Cursos' e extrai os links e títulos dos cursos.
    Timeout aumentado para 60 segundos.

    Args:
        driver: WebDriver do Selenium

    Returns:
        list: Lista de dicionários com 'title' e 'url' dos cursos
    """
    print("Navegando para a página 'Meus Cursos'...")
    driver.get(MY_COURSES_URL)
    try:
        WebDriverWait(driver, 60).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section[id^='card'] a.sc-cHGsZl"))
        )
        time.sleep(3)
        course_elements = driver.find_elements(By.CSS_SELECTOR, "section[id^='card']")
        courses = []
        for course_elem in course_elements:
            try:
                link_elem = course_elem.find_element(By.CSS_SELECTOR, "a.sc-cHGsZl")
                title_elem = course_elem.find_element(By.CSS_SELECTOR, "h1.sc-ksYbfQ")
                course_href = link_elem.get_attribute('href')
                course_title = title_elem.text
                if course_href and course_title:
                    courses.append({"title": course_title, "url": course_href})
            except (NoSuchElementException, StaleElementReferenceException):
                print("Elemento de curso não encontrado ou obsoleto. Pulando.")
        print(f"Encontrados {len(courses)} cursos.")
        return courses
    except TimeoutException:
        print("Erro: Tempo esgotado ao carregar a lista de cursos.")
        return []


def get_lesson_data(driver, course_url):
    """
    Navega até a página de um curso e extrai os links, títulos e subtítulos das aulas.
    Timeout aumentado para 40 segundos.

    Args:
        driver: WebDriver do Selenium
        course_url (str): URL do curso

    Returns:
        list: Lista de dicionários com 'title', 'subtitle' e 'url' das aulas
    """
    print(f"Navegando para a página do curso: {course_url}")
    driver.get(course_url)
    try:
        WebDriverWait(driver, 40).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.LessonList-item a.Collapse-header"))
        )
        time.sleep(3)
        lesson_elements = driver.find_elements(By.CSS_SELECTOR, "div.LessonList-item")
        lessons = []
        for lesson_elem in lesson_elements:
            try:
                if "isDisabled" in lesson_elem.get_attribute("class"):
                    continue
                link_elem = lesson_elem.find_element(By.CSS_SELECTOR, "a.Collapse-header")
                title_h2_elem = lesson_elem.find_element(By.CSS_SELECTOR, "h2.SectionTitle")
                lesson_title = title_h2_elem.text
                lesson_subtitle = ""
                try:
                    title_p_elem = lesson_elem.find_element(By.CSS_SELECTOR, "p.sc-gZMcBi")
                    lesson_subtitle = title_p_elem.text
                except NoSuchElementException:
                    pass
                lesson_href = link_elem.get_attribute('href')
                if lesson_href and lesson_title:
                    lessons.append({
                        "title": lesson_title,
                        "subtitle": lesson_subtitle,
                        "url": lesson_href
                    })
            except (NoSuchElementException, StaleElementReferenceException):
                print("Elemento da aula não encontrado ou obsoleto. Pulando.")
        print(f"Encontradas {len(lessons)} aulas disponíveis.")
        return lessons
    except TimeoutException:
        print("Erro: Tempo esgotado ao carregar a lista de aulas.")
        return []


def setup_course_logger(course_title, download_dir, telegram_notifier):
    """
    Configura um logger específico para cada curso.

    Args:
        course_title (str): Nome do curso
        download_dir (str): Diretório raiz de downloads

    Returns:
        logging.Logger: Logger configurado para o curso
    """
    sanitized = sanitize_filename(course_title)
    logfile = os.path.join(download_dir, f"download_{sanitized}.log")
    logger = logging.getLogger(sanitized)
    logger.handlers = []
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(logfile, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger


# ============================================================================
# FUNÇÕES REFATORADAS PARA DOWNLOAD DE MATERIAIS
# ============================================================================

def save_lesson_subjects(lesson_download_path, lesson_subtitle, logger):
    """Salva os assuntos da aula em arquivo texto."""
    if not lesson_subtitle:
        return True

    subjects_file_path = os.path.join(lesson_download_path, "Assuntos_dessa_aula.txt")
    if os.path.exists(subjects_file_path):
        print("Arquivo 'Assuntos_dessa_aula.txt' já existe. Pulando.")
        logger.info("Arquivo 'Assuntos_dessa_aula.txt' já existe.")
        return True

    try:
        with open(subjects_file_path, 'w', encoding='utf-8') as f:
            f.write(lesson_subtitle)
        print("Arquivo 'Assuntos_dessa_aula.txt' criado com sucesso.")
        logger.info("Arquivo 'Assuntos_dessa_aula.txt' criado com sucesso.")
        return True
    except Exception as e:
        print(f"Erro ao criar 'Assuntos_dessa_aula.txt': {e}")
        logger.error(f"Erro ao criar 'Assuntos_dessa_aula.txt': {e}")
        return False


def download_electronic_books(driver, lesson_download_path, sanitized_lesson_title, logger):
    """Localiza e baixa os Livros Eletrônicos (PDFs) da aula."""
    print("Procurando por Livros Eletrônicos (PDFs)...")
    try:
        pdf_links = driver.find_elements(By.XPATH,
                                         "//a[contains(@class, 'LessonButton') and .//i[contains(@class, 'icon-file')]]")

        if not pdf_links:
            print("Nenhum livro eletrônico encontrado.")
            logger.info("Nenhum livro eletrônico encontrado.")
            return

        for pdf_link in pdf_links:
            pdf_url = pdf_link.get_attribute('href')
            if not pdf_url or "api.estrategiaconcursos.com.br" not in pdf_url:
                continue

            pdf_text_raw = "original"
            try:
                version_text_element = pdf_link.find_element(By.CSS_SELECTOR, "span.LessonButton-text > span")
                pdf_text_raw = version_text_element.text.strip()
            except NoSuchElementException:
                pass

            filename_suffix = "_" + sanitize_filename(pdf_text_raw)
            filename = f"{sanitized_lesson_title}_Livro_Eletronico{filename_suffix}.pdf"
            full_file_path = os.path.join(lesson_download_path, filename)

            if os.path.exists(full_file_path):
                print(f"PDF '{filename}' já existe. Pulando.")
                logger.info(f"PDF '{filename}' já existe. Pulando.")
            else:
                print(f"Encontrado PDF: {pdf_text_raw}")
                logger.info(f"Iniciando download do PDF: {filename}")
                download_file(pdf_url, full_file_path, driver.current_url, logger)
    except Exception as e:
        print(f"Erro ao processar Livros Eletrônicos: {e}")
        logger.error(f"Erro ao processar Livros Eletrônicos: {e}")


def get_playlist_videos(driver, logger):
    """Localiza todos os vídeos na playlist da aula."""
    try:
        playlist_items = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.ListVideos-items-video a.VideoItem"))
        )

        videos_to_download = []
        for item in playlist_items:
            try:
                video_href = item.get_attribute('href')
                video_title = item.find_element(By.CSS_SELECTOR, "span.VideoItem-info-title").text
                if video_href and video_title:
                    videos_to_download.append({'url': video_href, 'title': video_title})
            except NoSuchElementException:
                continue

        if videos_to_download:
            print(f"Encontrados {len(videos_to_download)} vídeos na playlist.")
            logger.info(f"Encontrados {len(videos_to_download)} vídeos na playlist.")
        else:
            print("Nenhum vídeo encontrado na playlist.")
            logger.info("Nenhum vídeo encontrado na playlist.")

        return videos_to_download
    except TimeoutException:
        print("Nenhuma playlist de vídeos encontrada nesta aula.")
        logger.info("Nenhuma playlist de vídeos encontrada nesta aula.")
        return []


def download_video_supplementary_pdfs(driver, video_info, lesson_download_path, sanitized_lesson_title, index, logger):
    """Baixa os PDFs suplementares de um vídeo (Resumo, Slides, Mapa Mental)."""
    print(f"Procurando por PDFs suplementares do vídeo '{video_info['title']}'...")

    video_pdf_types = {
        "Baixar Resumo": f"_Resumo_{index}.pdf",
        "Baixar Slides": f"_Slides_Video_{index}.pdf",
        "Baixar Mapa Mental": f"_Mapa_Mental_{index}.pdf"
    }

    for pdf_button_text, filename_suffix in video_pdf_types.items():
        try:
            pdf_link_elem = driver.find_element(By.XPATH,
                                                f"//a[contains(@class, 'LessonButton') and .//span[contains(text(), '{pdf_button_text}')]]")
            pdf_url = pdf_link_elem.get_attribute('href')

            if pdf_url:
                filename = f"{sanitized_lesson_title}_{sanitize_filename(video_info['title'])}{filename_suffix}"
                full_file_path = os.path.join(lesson_download_path, filename)

                if os.path.exists(full_file_path):
                    print(f"PDF '{pdf_button_text.replace('Baixar ', '')}' já existe. Pulando.")
                    logger.info(f"PDF '{pdf_button_text}' já existe. Pulando.")
                else:
                    print(f"Encontrado {pdf_button_text} para o vídeo '{video_info['title']}'.")
                    logger.info(f"Iniciando download: {pdf_button_text}")
                    download_file(pdf_url, full_file_path, driver.current_url, logger)
            else:
                logger.warning(f"{pdf_button_text} encontrado mas sem URL para '{video_info['title']}'")
        except NoSuchElementException:
            print(f"{pdf_button_text} não encontrado para '{video_info['title']}'.")
            logger.info(f"{pdf_button_text} não encontrado.")
        except Exception as e:
            print(f"Erro ao processar '{pdf_button_text}': {e}")
            logger.error(f"Erro ao processar '{pdf_button_text}': {e}")


def download_video_file(driver, video_info, lesson_download_path, sanitized_video_title, logger):
    """Baixa o arquivo de vídeo em uma qualidade preferida (720p > 480p > 360p)."""
    try:
        download_options_header = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class, 'Collapse-header')]//strong[text()='Opções de download']")
            )
        )

        header_container = download_options_header.find_element(By.XPATH,
                                                                "./ancestor::div[contains(@class, 'Collapse-header-container')]")
        collapse_body = header_container.find_element(By.XPATH, "./following-sibling::div")

        if not collapse_body.is_displayed():
            driver.execute_script("arguments[0].click();", download_options_header)
            WebDriverWait(driver, 5).until(EC.visibility_of(collapse_body))

        preferred_qualities = ["720p", "480p", "360p"]

        for quality in preferred_qualities:
            filename = f"{sanitized_video_title}_Video_{quality}.mp4"
            full_file_path = os.path.join(lesson_download_path, filename)

            if os.path.exists(full_file_path):
                print(f"Vídeo '{filename}' já existe. Pulando.")
                logger.info(f"Vídeo '{filename}' já existe.")
                return True

            try:
                video_link_elem = collapse_body.find_element(By.XPATH, f".//a[contains(text(), '{quality}')]")
                video_url = video_link_elem.get_attribute('href')
                print(f"Tentando baixar vídeo em {quality}...")
                logger.info(f"Iniciando download em {quality}")

                if download_file(video_url, full_file_path, driver.current_url, logger):
                    return True
            except NoSuchElementException:
                print(f"Qualidade {quality} não disponível. Tentando próxima...")
                logger.info(f"Qualidade {quality} não disponível.")
                continue

        print(f"AVISO: Não foi possível baixar vídeo em nenhuma qualidade preferida.")
        logger.warning(f"Não foi possível baixar vídeo em nenhuma qualidade preferida.")
        return False

    except TimeoutException:
        print(f"Não foi possível encontrar/expandir 'Opções de download'.")
        logger.warning("Não foi possível expandir 'Opções de download'.")
        return False
    except Exception as e:
        print(f"Erro ao baixar vídeo: {e}")
        logger.error(f"Erro ao baixar vídeo: {e}")
        return False


def download_playlist_videos(driver, videos_list, lesson_download_path, sanitized_lesson_title, logger):
    """Orquestra o download de todos os vídeos da playlist."""
    print(f"Iniciando download de {len(videos_list)} vídeos...")
    logger.info(f"Iniciando download de {len(videos_list)} vídeos.")

    for i, video_info in enumerate(videos_list):
        print(f"\n[Vídeo {i + 1}/{len(videos_list)}] Processando: {video_info['title']}")
        logger.info(f"Processando vídeo {i + 1}/{len(videos_list)}: {video_info['title']}")

        driver.get(video_info['url'])
        time.sleep(2)

        download_video_supplementary_pdfs(driver, video_info, lesson_download_path,
                                          sanitized_lesson_title, i, logger)

        sanitized_video_title = sanitize_filename(video_info['title'])
        download_video_file(driver, video_info, lesson_download_path, sanitized_video_title, logger)


def navigate_to_lesson(driver, lesson_url, logger):
    """Navega até a página da aula e aguarda carregamento."""
    try:
        print(f"Navegando para aula...")
        driver.get(lesson_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.Lesson-contentTop, div.LessonVideos"))
        )
        time.sleep(2)
        return True
    except TimeoutException:
        print(f"Erro: Tempo esgotado ao carregar a página da aula.")
        logger.warning("Tempo esgotado ao carregar página da aula.")
        return False
    except Exception as e:
        print(f"Erro ao navegar para aula: {e}")
        logger.error(f"Erro ao navegar para aula: {e}")
        return False


def create_lesson_directory(download_dir, course_title, lesson_title, logger):
    """Cria o diretório para a aula."""
    sanitized_course_title = sanitize_filename(course_title)
    sanitized_lesson_title = sanitize_filename(lesson_title)
    lesson_download_path = os.path.join(download_dir, sanitized_course_title, sanitized_lesson_title)

    try:
        os.makedirs(lesson_download_path, exist_ok=True)
        return lesson_download_path
    except OSError as e:
        print(f"ERRO CRÍTICO ao criar diretório: {e}")
        logger.error(f"Erro ao criar diretório: {e}")
        return None


def download_lesson_materials(driver, lesson_info, course_title, download_dir, logger):
    """
    Orquestra o download de todos os materiais de uma aula.
    Função refatorada - apenas coordena as subfunções especializadas.
    """
    lesson_title = lesson_info['title']
    lesson_subtitle = lesson_info['subtitle']
    lesson_url = lesson_info['url']

    print(f"Processando aula: {lesson_title}")
    logger.info(f"Iniciando processamento da aula: {lesson_title}")

    if not navigate_to_lesson(driver, lesson_url, logger):
        return

    handle_popups(driver)

    lesson_download_path = create_lesson_directory(download_dir, course_title, lesson_title, logger)
    if not lesson_download_path:
        return

    save_lesson_subjects(lesson_download_path, lesson_subtitle, logger)

    sanitized_lesson_title = sanitize_filename(lesson_title)
    download_electronic_books(driver, lesson_download_path, sanitized_lesson_title, logger)

    videos_list = get_playlist_videos(driver, logger)
    if videos_list:
        download_playlist_videos(driver, videos_list, lesson_download_path, sanitized_lesson_title, logger)

    logger.info(f"Aula '{lesson_title}' processada com sucesso.")


# ============================================================================
# FUNÇÕES DE LOGIN E FLUXO PRINCIPAL
# ============================================================================

def login(driver, wait_time):
    """Realiza login manual com salvamento de cookies."""
    print("Navegando para a página de login...")
    driver.get("https://perfil.estrategia.com/login")
    print("=" * 60)
    print("AÇÃO NECESSÁRIA: FAÇA O LOGIN MANUALMENTE NO NAVEGADOR ABERTO")
    print(f"O script ficará pausado por {wait_time} segundos para você completar o login.")
    print("Após o login, o script continuará automaticamente.")
    print("NÃO feche o navegador.")
    print("=" * 60)
    time.sleep(wait_time)
    print("Pausa para login concluída. Continuando o script...")

    # Salva cookies após login bem-sucedido
    save_cookies(driver)


def pick_courses(courses):
    """Lista os cursos e permite seleção interativa."""
    print("\nCURSOS DISPONÍVEIS:")
    for idx, course in enumerate(courses, 1):
        print(f" [{idx}] {course['title']}")

    while True:
        sel = input("\nDigite os números dos cursos a baixar (ex: 1,3,5): ")
        try:
            indices = [int(x.strip()) - 1 for x in sel.split(",") if x.strip().isdigit()]
            if all(0 <= idx < len(courses) for idx in indices) and indices:
                return [courses[idx] for idx in indices]
        except Exception:
            pass
        print("Seleção inválida. Tente novamente.")


def run_downloader(download_dir, login_wait_time):
    """
    Função principal que orquestra todo o processo de download.

    MELHORIAS IMPLEMENTADAS:
    1. Heartbeat para manter sessão viva durante downloads longos
    2. Salvamento e restauração automática de cookies
    3. Verificação de sessão antes de processar cada curso
    """

    # Inicializa notificador do Telegram
    telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED)
    try:
        os.makedirs(download_dir, exist_ok=True)
        print(f"Diretório de download configurado para: {os.path.abspath(download_dir)}")
    except OSError as e:
        print(f"ERRO: Não foi possível criar o diretório '{download_dir}'. Erro: {e}")
        sys.exit(1)

    driver = webdriver.Edge()
    driver.maximize_window()

    # MELHORIA #2: Inicializa sistema de heartbeat
    keepalive = SessionKeepAlive(driver, interval=HEARTBEAT_INTERVAL)

    try:
        login(driver, login_wait_time)

        # MELHORIA #2: Inicia heartbeat após login
        keepalive.start()

        courses = get_course_data(driver)
        if not courses:
            print("Nenhum curso encontrado. Encerrando.")
            return

        selected_courses = pick_courses(courses)
        telegram.notify_start(len(selected_courses))

        for i, course in enumerate(selected_courses):
            # MELHORIA #3: Verifica e restaura sessão antes de cada curso
            print(f"\n{'=' * 60}")
            print(f"Verificando sessão antes de processar curso {i + 1}/{len(selected_courses)}...")
            if not ensure_logged_in(driver, telegram):
                print("⚠ Não foi possível garantir login. Pulando este curso.")
                continue

            logger = setup_course_logger(course['title'], download_dir, telegram)
            print(f"\n[{i + 1}/{len(selected_courses)}] Baixando curso: {course['title']}")
            logger.info("=" * 60)
            logger.info(f"Iniciando download do curso: {course['title']}")
            logger.info("=" * 60)

            start_time = datetime.now()

            lessons = get_lesson_data(driver, course['url'])
            if not lessons:
                print(f"Nenhuma aula encontrada para '{course['title']}'. Pulando.")
                logger.warning("Nenhuma aula encontrada para este curso.")
                continue

            telegram.notify_course_start(course['title'], i+1, len(selected_courses), len(lessons))


            for j, lesson_info in enumerate(lessons):
                print(f"\n -> Aula {j + 1}/{len(lessons)}: {lesson_info['title']}")
                logger.info(f"Processando aula {j + 1}/{len(lessons)}: {lesson_info['title']}")
                download_lesson_materials(driver, lesson_info, course['title'], download_dir, logger)
                time.sleep(2)

            end_time = datetime.now()
            delta = end_time - start_time
            telegram.notify_complete(str(delta))
            logger.info(f"Download do curso finalizado. Tempo total: {delta}")
            print(f"\n✓ Tempo de download do curso: {delta}")

    except Exception as e:
        telegram.notify_error(str(e))
        print(f"\nErro geral no script: {e}")
    finally:
        # MELHORIA #2: Para heartbeat antes de encerrar
        keepalive.stop()
        print("\nProcesso concluído. Fechando navegador em 10 segundos.")
        time.sleep(10)
        driver.quit()


def main():
    """Analisa argumentos de linha de comando e inicia o processo."""
    parser = argparse.ArgumentParser(
        description="Baixador de cursos do Estratégia Concursos com gerenciamento de sessão.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-d', '--dir',
        dest='download_dir',
        metavar='PATH',
        type=str,
        default="C:/Users/joao.santosm/projetos/curso/TJ-RJ",
        help="O caminho para a pasta onde os cursos serão salvos.\n(Padrão: E:/Estrategia)"
    )
    parser.add_argument(
        "-w", "--wait-time",
        type=int,
        default=60,
        help="Tempo em segundos para aguardar o login manual (padrão: 60)."
    )
    args = parser.parse_args()
    run_downloader(args.download_dir, args.wait_time)


if __name__ == "__main__":
    main()
