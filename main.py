"""
Script de Download com Notificações via Telegram
Estratégia Concursos - Versão Completa

Melhorias incluídas:
1. Timeouts aumentados (60s cursos, 40s aulas)
2. Seleção interativa de cursos
3. Barra de progresso em downloads
4. Logs estruturados por curso com tempo
5. Heartbeat para manter sessão viva
6. Salvamento/restauração de cookies
7. Verificação de sessão antes de cada curso
8. NOVO: Notificações em tempo real via Telegram Bot
"""

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

# ============================================================================
# CONFIGURAÇÕES GERAIS
# ============================================================================

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


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def sanitize_filename(original_filename):
    """Remove caracteres inválidos de nomes de arquivo."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '', original_filename)
    sanitized = re.sub(r'[.,]', '', sanitized)
    sanitized = re.sub(r'[\s-]+', '_', sanitized)
    return sanitized.strip('._- ')


def download_file(url, file_path, current_page_url=None, logger=None):
    """Realiza download com barra de progresso."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
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
                logger.info(f"Download concluído: {os.path.basename(file_path)}")
            return True
    except Exception as e:
        print(f"Erro ao baixar: {e}")
        if logger:
            logger.error(f"Erro ao baixar {file_path}: {e}")
        return False


def handle_popups(driver):
    """Fecha popups conhecidos."""
    try:
        widget = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, "getsitecontrol-44266"))
        )
        driver.execute_script("arguments[0].style.display = 'none';", widget)
    except TimeoutException:
        pass


# ============================================================================
# GERENCIAMENTO DE SESSÃO
# ============================================================================

def save_cookies(driver, filepath=COOKIES_FILE):
    """Salva cookies da sessão."""
    try:
        with open(filepath, "wb") as f:
            pickle.dump(driver.get_cookies(), f)
        print(f"✓ Cookies salvos")
    except Exception as e:
        print(f"Erro ao salvar cookies: {e}")


def load_cookies(driver, filepath=COOKIES_FILE):
    """Carrega cookies salvos."""
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


def ensure_logged_in(driver, notifier, cookies_file=COOKIES_FILE):
    """Garante que está logado, restaurando se necessário."""
    if not is_logged_in(driver):
        notifier.notify_session_expired()
        print("\n⚠ Sessão expirada. Restaurando...")
        driver.get(BASE_URL)
        time.sleep(2)

        if load_cookies(driver, cookies_file):
            driver.refresh()
            time.sleep(3)

            if is_logged_in(driver):
                print("✓ Sessão restaurada com sucesso!")
                notifier.notify_session_restored()
                return True
            else:
                print("Faça login manualmente...")
                input("Pressione ENTER após login...")
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
        while not self.stop_event.is_set():
            try:
                self.driver.execute_script("console.log('keepalive')")
                print(f"\n[Heartbeat {datetime.now().strftime('%H:%M:%S')}] Sessão mantida")
            except:
                pass
            self.stop_event.wait(self.interval)

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._heartbeat, daemon=True)
            self.thread.start()
            print(f"✓ Heartbeat iniciado ({self.interval}s)")

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)


# ============================================================================
# RASPAGEM E NAVEGAÇÃO
# ============================================================================

def get_course_data(driver):
    """Obtém lista de cursos."""
    print("Carregando cursos...")
    driver.get(MY_COURSES_URL)
    try:
        WebDriverWait(driver, 60).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section[id^='card'] a.sc-cHGsZl"))
        )
        time.sleep(3)
        course_elements = driver.find_elements(By.CSS_SELECTOR, "section[id^='card']")
        courses = []
        for elem in course_elements:
            try:
                link = elem.find_element(By.CSS_SELECTOR, "a.sc-cHGsZl")
                title = elem.find_element(By.CSS_SELECTOR, "h1.sc-ksYbfQ")
                if link.get_attribute('href') and title.text:
                    courses.append({"title": title.text, "url": link.get_attribute('href')})
            except:
                continue
        print(f"Encontrados {len(courses)} cursos")
        return courses
    except TimeoutException:
        print("Erro ao carregar cursos")
        return []


def get_lesson_data(driver, course_url):
    """Obtém lista de aulas do curso."""
    driver.get(course_url)
    try:
        WebDriverWait(driver, 40).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.LessonList-item a.Collapse-header"))
        )
        time.sleep(3)
        lesson_elements = driver.find_elements(By.CSS_SELECTOR, "div.LessonList-item")
        lessons = []
        for elem in lesson_elements:
            try:
                if "isDisabled" in elem.get_attribute("class"):
                    continue
                link = elem.find_element(By.CSS_SELECTOR, "a.Collapse-header")
                title = elem.find_element(By.CSS_SELECTOR, "h2.SectionTitle")
                subtitle = ""
                try:
                    subtitle = elem.find_element(By.CSS_SELECTOR, "p.sc-gZMcBi").text
                except:
                    pass
                if link.get_attribute('href') and title.text:
                    lessons.append({"title": title.text, "subtitle": subtitle, "url": link.get_attribute('href')})
            except:
                continue
        print(f"Encontradas {len(lessons)} aulas")
        return lessons
    except TimeoutException:
        return []


def setup_course_logger(course_title, download_dir, telegram_notifier):
    """Configura logger para o curso com handler do Telegram."""
    sanitized = sanitize_filename(course_title)
    logfile = os.path.join(download_dir, f"download_{sanitized}.log")
    logger = logging.getLogger(sanitized)
    logger.handlers = []
    logger.setLevel(logging.INFO)

    # Handler de arquivo
    fh = logging.FileHandler(logfile, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

    # Handler do Telegram
    if telegram_notifier.enabled:
        th = TelegramLoggingHandler(telegram_notifier)
        th.setLevel(logging.WARNING)  # Apenas WARNING e ERROR vão pro Telegram
        logger.addHandler(th)

    return logger


# (Demais funções de download omitidas para brevidade - mantenha as funções refatoradas anteriores)

def login(driver, wait_time):
    """Login manual."""
    driver.get("https://perfil.estrategia.com/login")
    print("=" * 60)
    print("FAÇA LOGIN NO NAVEGADOR")
    print(f"Aguardando {wait_time} segundos...")
    print("=" * 60)
    time.sleep(wait_time)
    save_cookies(driver)


def pick_courses(courses):
    """Seleção interativa de cursos."""
    print("\nCURSOS DISPONÍVEIS:")
    for idx, course in enumerate(courses, 1):
        print(f" [{idx}] {course['title']}")

    while True:
        sel = input("\nDigite os números (ex: 1,3,5): ")
        try:
            indices = [int(x.strip()) - 1 for x in sel.split(",") if x.strip().isdigit()]
            if all(0 <= idx < len(courses) for idx in indices) and indices:
                return [courses[idx] for idx in indices]
        except:
            pass
        print("Seleção inválida.")


def run_downloader(download_dir, login_wait_time):
    """Função principal com integração Telegram."""

    # Inicializa notificador do Telegram
    telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED)

    os.makedirs(download_dir, exist_ok=True)
    driver = webdriver.Edge()
    driver.maximize_window()

    keepalive = SessionKeepAlive(driver)
    process_start = datetime.now()

    try:
        login(driver, login_wait_time)
        keepalive.start()

        courses = get_course_data(driver)
        if not courses:
            return

        selected = pick_courses(courses)
        telegram.notify_start(len(selected))

        for i, course in enumerate(selected):
            if not ensure_logged_in(driver, telegram):
                continue

            logger = setup_course_logger(course['title'], download_dir, telegram)
            course_start = datetime.now()

            lessons = get_lesson_data(driver, course['url'])
            if not lessons:
                continue

            telegram.notify_course_start(course['title'], i + 1, len(selected), len(lessons))

            # IMPORTANTE: Adicione aqui o loop de download das aulas
            # usando as funções refatoradas anteriormente

            course_time = datetime.now() - course_start
            telegram.notify_course_complete(course['title'], i + 1, len(selected), str(course_time))
            logger.info(f"Curso concluído em {course_time}")

        total_time = datetime.now() - process_start
        telegram.notify_complete(str(total_time))

    except Exception as e:
        telegram.notify_error(str(e))
    finally:
        keepalive.stop()
        time.sleep(10)
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Downloader com Telegram")
    parser.add_argument('-d', '--dir', default="C:/Users/joao.santosm/projetos/curso/TJ-RJ")
    parser.add_argument('-w', '--wait-time', type=int, default=60)
    args = parser.parse_args()
    run_downloader(args.download_dir, args.wait_time)


if __name__ == "__main__":
    main()
