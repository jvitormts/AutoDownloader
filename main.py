import os
import re
import time
import argparse
import sys
import pickle
import threading
import json
from urllib.parse import urljoin
import requests
import logging
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime

from video_optimization import (
    ParallelVideoDownloader,
    SegmentedVideoDownloader,
    create_video_downloader,
    get_optimal_video_strategy
)

# ============================================================================
# IMPORTAÇÕES PARA DOWNLOADS PARALELOS (NOVO)
# ============================================================================
from download_optimization import (
    ParallelDownloadManager,
    ProgressMonitor,
    ConcurrencySelector,
    create_download_manager,
    print_download_summary
)

# ============================================================================
# CONFIGURAÇÃO DO TELEGRAM BOT
# ============================================================================
# INSTRUÇÕES:
# 1. Abra o Telegram e busque por @BotFather
# 2. Digite /newbot e siga as instruções
# 3. Copie o TOKEN que o BotFather te der
# 4. Inicie conversa com seu bot
# 5. Acesse: https://api.telegram.org/bot/getUpdates
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
# FEATURE 1: GERENCIADOR DE MANIFESTO DE ARQUIVOS
# ============================================================================

class FileManifestManager:
    """
    Gerencia o arquivo 'files_manifest.json' para rastreamento de downloads.
    Rastreia cada arquivo baixado com:
    - Timestamp de download
    - Nome do arquivo
    - Tamanho (bytes e MB)
    - Tipo de arquivo (pdf, video, txt, etc)
    - Tempo de download
    - Status (success, error, skipped)
    """

    MANIFEST_FILENAME = "files_manifest.json"

    def __init__(self, course_path: str, logger: logging.Logger = None):
        """
        Inicializa o gerenciador do manifesto.
        Args:
            course_path (str): Caminho da pasta do curso
            logger (logging.Logger): Logger para registrar ações
        """
        self.course_path = course_path
        self.manifest_path = os.path.join(course_path, self.MANIFEST_FILENAME)
        self.logger = logger
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        """Carrega o manifesto do disco ou cria um novo."""
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Erro ao carregar manifest: {e}")
                return {}
        return {}

    def _save_manifest(self):
        """Salva o manifesto no disco."""
        try:
            with open(self.manifest_path, 'w', encoding='utf-8') as f:
                json.dump(self.manifest, f, indent=2, ensure_ascii=False)
            if self.logger:
                self.logger.debug(f"Manifesto salvo: {self.manifest_path}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Erro ao salvar manifest: {e}")

    def start_lesson(self, lesson_title: str) -> None:
        """Marca o início do rastreamento de uma aula."""
        if lesson_title not in self.manifest:
            self.manifest[lesson_title] = {
                "timestamp": datetime.now().isoformat(),
                "total_files": 0,
                "files": []
            }
        if self.logger:
            self.logger.info(f"Iniciando rastreamento: {lesson_title}")

    def add_file(self, lesson_title: str, file_name: str, size_bytes: int,
                 file_type: str, download_time: str = "", status: str = "success") -> None:
        """
        Adiciona um arquivo ao rastreamento de uma aula.
        Args:
            lesson_title (str): Título da aula
            file_name (str): Nome do arquivo
            size_bytes (int): Tamanho do arquivo em bytes
            file_type (str): Tipo de arquivo (pdf, video, txt, etc)
            download_time (str): Tempo gasto no download (HH:MM:SS)
            status (str): Status do download (success, error, skipped)
        """
        if lesson_title not in self.manifest:
            self.start_lesson(lesson_title)

        file_entry = {
            "name": file_name,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "type": file_type,
            "download_time": download_time,
            "status": status,
            "added_at": datetime.now().isoformat()
        }

        self.manifest[lesson_title]["files"].append(file_entry)
        self.manifest[lesson_title]["total_files"] = len(self.manifest[lesson_title]["files"])

        if self.logger:
            self.logger.debug(f"Arquivo rastreado: {file_name} ({size_bytes} bytes)")

    def finish_lesson(self, lesson_title: str) -> None:
        """Marca a conclusão do rastreamento de uma aula."""
        if lesson_title in self.manifest:
            self.manifest[lesson_title]["completed_at"] = datetime.now().isoformat()
            self._save_manifest()

        if self.logger:
            self.logger.info(
                f"Aula concluída: {lesson_title} ({self.manifest[lesson_title]['total_files']} arquivos)")

    def get_downloaded_lessons(self) -> list:
        """Retorna lista de aulas já rastreadas/baixadas."""
        return list(self.manifest.keys())

    def get_lesson_info(self, lesson_title: str) -> dict:
        """Retorna informações de uma aula."""
        return self.manifest.get(lesson_title)

    def get_course_statistics(self) -> dict:
        """Retorna estatísticas gerais do curso."""
        total_lessons = len(self.manifest)
        total_files = sum(lesson["total_files"] for lesson in self.manifest.values())
        total_size_bytes = sum(
            file["size_bytes"]
            for lesson in self.manifest.values()
            for file in lesson.get("files", [])
        )
        return {
            "total_lessons": total_lessons,
            "total_files": total_files,
            "total_size_bytes": total_size_bytes,
            "total_size_gb": round(total_size_bytes / (1024 ** 3), 2)
        }


# ============================================================================
# FEATURE 2: DETECTOR DE PENDENTES
# ============================================================================

def find_incomplete_courses(driver, download_dir, available_courses, telegram, logger=None):
    """
    Detecta cursos incompletos comparando:
    - Total de aulas na PLATAFORMA
    - Total de aulas já BAIXADAS localmente

    Args:
        driver: WebDriver do Selenium
        download_dir: Diretório raiz de downloads
        available_courses: Cursos disponíveis na plataforma
        telegram: Notificador do Telegram

    Returns:
        list: Cursos incompletos com informações de progresso
        Exemplo: [
            {
                'course': {'title': '...', 'url': '...'},
                'platform_total': 17,
                'local_total': 2,
                'missing': 15,
                'progress': '11.8%'
            },
            ...
        ]
    """
    detector = PendingLessonsDetector(download_dir, logger)
    downloaded_courses = detector.scan_downloaded_courses()

    if not downloaded_courses:
        print("\n✓ Nenhum curso baixado ainda.")
        return [], {}

    print(f"\n{'=' * 70}")
    print(f"🔍 ANALISANDO PROGRESSO DOS CURSOS...")
    print(f"{'=' * 70}\n")

    incomplete = []

    # Para cada curso já baixado localmente
    for local_course_name, local_course_path in downloaded_courses.items():

        # Contar aulas baixadas localmente
        lessons_downloaded = detector.get_course_downloaded_lessons(local_course_path)
        local_total = len(lessons_downloaded)

        # Obter estatísticas do manifesto
        manifest_path = os.path.join(local_course_path, FileManifestManager.MANIFEST_FILENAME)
        if os.path.exists(manifest_path):
            stats = FileManifestManager(local_course_path).get_course_statistics()
        else:
            stats = {'total_lessons': local_total, 'total_size_gb': 0}

        # ✅ Procurar curso correspondente na plataforma
        platform_course = None
        platform_total = 0

        # Tentar obter nome original do arquivo metadata.json
        metadata_path = os.path.join(local_course_path, "course_metadata.json")
        original_course_name = local_course_name
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    original_course_name = metadata.get('original_title', local_course_name)
                    print(f"  ℹ️  Nome original encontrado: {original_course_name}")
            except Exception as e:
                pass

        for course in available_courses:
            if detector._courses_match(original_course_name, course['title'], metadata_path):
                platform_course = course
                platform_total = get_total_lessons_from_platform(driver, course['url'], telegram)
                break

        if platform_course is None:
            print(f"⚠️ Curso não encontrado na plataforma: {local_course_name}")
            continue

        if platform_total > local_total:
            missing = platform_total - local_total
            progress_pct = (local_total / platform_total) * 100
            course_info = {
                'course': platform_course,
                'platform_total': platform_total,
                'local_total': local_total,
                'missing': missing,
                'progress': f"{progress_pct:.1f}%",
                'size_gb': stats.get('total_size_gb', 0)
            }
            incomplete.append(course_info)

            # ✅ Exibir nome original se disponível
            display_name = original_course_name if os.path.exists(metadata_path) else local_course_name
            print(f" 📚 {display_name}")
            print(f" ├─ 📊 Progresso: {local_total}/{platform_total} aulas ({progress_pct:.1f}%)")
            print(f" ├─ ❌ Faltam: {missing} aulas")
            print(f" ├─ 💾 Tamanho: {stats.get('total_size_gb', 0)} GB")
            print(f" └─ 🔗 Status: INCOMPLETO\n")

            telegram.send(
                f"📚 {display_name}\n"
                f"Progresso: {local_total}/{platform_total} ({progress_pct:.1f}%)\n"
                f"Faltam: {missing} aulas"
            )
        else:
            progress_pct = 100
            print(f" 📚 {local_course_name}")
            print(f" ├─ 📊 Progresso: {local_total}/{platform_total} aulas (100%)")
            print(f" ├─ ✅ Todas as aulas baixadas!")
            print(f" └─ 🔗 Status: COMPLETO\n")

            telegram.send(
                f"✅ {local_course_name}\n"
                f"Todas as {platform_total} aulas foram baixadas!"
            )

    print(f"{'=' * 70}")
    if incomplete:
        print(f"\n⚠️ ENCONTRADOS {len(incomplete)} CURSO(S) COM AULAS FALTANDO!\n")
    else:
        print(f"\n✅ Todos os cursos estão completos!\n")

    courses_map = {course['title']: course for course in available_courses}
    return incomplete, courses_map


def get_total_lessons_from_platform(driver, course_url, telegram):
    """
    Acessa o curso na plataforma e conta o total de aulas disponíveis.

    Args:
        driver: WebDriver do Selenium
        course_url: URL do curso na plataforma
        telegram: Notificador do Telegram

    Returns:
        int: Total de aulas disponíveis no curso
    """
    try:
        print(f" ⏳ Contando aulas na plataforma... ", end="", flush=True)
        driver.get(course_url)

        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.LessonList-item"))
        )

        time.sleep(2)
        lesson_elements = driver.find_elements(By.CSS_SELECTOR, "div.LessonList-item")
        total_lessons = len(lesson_elements)

        print(f"✓ {total_lessons} aulas encontradas")
        return total_lessons

    except TimeoutException:
        print("⚠️ Timeout ao contar aulas")
        telegram.send("⚠️ Erro ao contar aulas na plataforma (timeout)")
        return 0

    except Exception as e:
        print(f"❌ Erro: {e}")
        telegram.send(f"❌ Erro ao contar aulas: {e}")
        return 0


class PendingLessonsDetector:
    """
    Detecta e gerencia aulas pendentes em cursos já iniciados.

    Compara:
    1. Aulas disponíveis na plataforma
    2. Aulas já baixadas localmente (via manifest.json)
    3. Identifica aulas pendentes
    """

    def __init__(self, download_base_path: str, logger: logging.Logger = None):
        """
        Inicializa o detector.

        Args:
            download_base_path (str): Caminho raiz de downloads (ex: E:/Estrategia)
            logger (logging.Logger): Logger para registrar ações
        """
        self.base_path = download_base_path
        self.logger = logger if logger else logging.getLogger(__name__)

    def scan_downloaded_courses(self) -> dict:
        """
        Varre a pasta de downloads e retorna cursos encontrados.

        Returns:
            dict: Dicionário {nome_curso: caminho_curso}
        """
        courses = {}
        if not os.path.exists(self.base_path):
            return courses

        try:
            for item in os.listdir(self.base_path):
                item_path = os.path.join(self.base_path, item)
                if os.path.isdir(item_path):
                    courses[item] = item_path

            if self.logger:
                self.logger.info(f"Encontrados {len(courses)} cursos já baixados")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Erro ao scanear cursos: {e}")

        return courses

    def get_course_downloaded_lessons(self, course_path: str) -> list:
        """
        Obtém lista de aulas já baixadas de um curso (via manifest).

        Args:
            course_path (str): Caminho da pasta do curso

        Returns:
            list: Lista de títulos de aulas baixadas
        """
        manifest_path = os.path.join(course_path, FileManifestManager.MANIFEST_FILENAME)
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                    return list(manifest.keys())
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Erro ao ler manifest: {e}")

        try:
            lessons = []
            for item in os.listdir(course_path):
                item_path = os.path.join(course_path, item)
                if os.path.isdir(item_path) and item != "__pycache__":
                    lessons.append(item)
            return lessons

        except Exception as e:
            if self.logger:
                self.logger.error(f"Erro ao listar aulas: {e}")
            return []

    def _courses_match(self, course_name_1: str, course_name_2: str, metadata_path: str = None) -> bool:
        """Verifica se dois nomes de curso referem-se ao mesmo curso."""
        name1_lower = course_name_1.lower().strip()
        name2_lower = course_name_2.lower().strip()

        if metadata_path and os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    original_title = metadata.get('original_title', '').lower().strip()
                    if original_title == name2_lower:
                        if self.logger:
                            self.logger.debug(f"Match via metadata: {original_title} == {name2_lower}")
                        return True
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Erro ao ler metadata: {e}")

        if name1_lower == name2_lower:
            return True

        name1_normalized = re.sub(r'[^a-z0-9\s]', '', name1_lower)
        name2_normalized = re.sub(r'[^a-z0-9\s]', '', name2_lower)

        if name1_normalized == name2_normalized:
            if self.logger:
                self.logger.debug(f"Match fuzzy: '{name1_lower}' ≈ '{name2_lower}'")
            return True

        if name1_lower in name2_lower or name2_lower in name1_lower:
            return True

        return False


# ============================================================================
# HELPER FUNCTIONS PARA RASTREAMENTO
# ============================================================================

def calculate_file_download_time(file_size_bytes: int, duration_seconds: float) -> str:
    """Calcula o tempo de download formatado."""
    hours = int(duration_seconds // 3600)
    minutes = int((duration_seconds % 3600) // 60)
    seconds = int(duration_seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_file_type(filename: str) -> str:
    """Obtém tipo de arquivo baseado na extensão."""
    extension = os.path.splitext(filename)[1].lower().lstrip('.')
    type_map = {
        'pdf': 'pdf',
        'mp4': 'video',
        'mkv': 'video',
        'avi': 'video',
        'txt': 'text',
        'md': 'text',
        'png': 'image',
        'jpg': 'image',
        'jpeg': 'image',
        'gif': 'image',
        'zip': 'archive',
        'rar': 'archive',
        '7z': 'archive'
    }
    return type_map.get(extension, 'unknown')


def download_file_with_tracking(url: str, file_path: str, manifest_manager: FileManifestManager,
                                lesson_title: str, current_page_url: str = None,
                                logger: logging.Logger = None) -> bool:
    """
    Versão modificada de download_file com rastreamento automático.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    if current_page_url:
        headers['Referer'] = current_page_url

    download_start = datetime.now()

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
                            print(f"\r Baixando: {os.path.basename(file_path)} [{progress:.2f}%]", end="")

            print()

            # Rastrear arquivo no manifesto
            download_duration = (datetime.now() - download_start).total_seconds()
            download_time_str = calculate_file_download_time(total or 0, download_duration)
            file_type = get_file_type(file_path)

            manifest_manager.add_file(
                lesson_title=lesson_title,
                file_name=os.path.basename(file_path),
                size_bytes=total or os.path.getsize(file_path),
                file_type=file_type,
                download_time=download_time_str,
                status="success"
            )

            if logger:
                logger.info(f"Arquivo rastreado: {os.path.basename(file_path)}")

            return True

    except Exception as e:
        print(f"Erro ao baixar: {e}")

        # Registrar erro no manifesto
        manifest_manager.add_file(
            lesson_title=lesson_title,
            file_name=os.path.basename(file_path),
            size_bytes=0,
            file_type=get_file_type(file_path),
            download_time="00:00:00",
            status="error"
        )

        if logger:
            logger.error(f"Erro ao baixar {file_path}: {e}")

        return False


# ============================================================================
# CLASSE PARA NOTIFICAÇÕES VIA TELEGRAM
# ============================================================================

class TelegramNotifier:
    """Gerencia envio de notificações para o Telegram."""

    def __init__(self, bot_token, chat_id, enabled=True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.last_send_time = 0
        self.min_interval = 1

        if self.enabled:
            self._test_connection()

    def _test_connection(self):
        """Testa conexão com o Telegram na inicialização."""
        try:
            self.send("🤖 Bot conectado com sucesso!\n\nPronto para enviar notificações de download.")
            print("✓ Telegram Bot conectado com sucesso!")
        except Exception as e:
            print(f"⚠ Erro ao conectar com Telegram: {e}")
            print(" As notificações do Telegram estarão desabilitadas.")
            self.enabled = False

    def send(self, message, parse_mode="HTML"):
        """Envia mensagem para o Telegram."""
        if not self.enabled:
            return False

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
            "🚀 DOWNLOAD INICIADO\n\n"
            f"📚 Cursos selecionados: {total_courses}\n"
            f"⏰ Início: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        self.send(message)

    def notify_course_start(self, course_title, course_num, total_courses, total_lessons):
        """Notifica início de um curso."""
        message = (
            f"📚 CURSO INICIADO [{course_num}/{total_courses}]\n\n"
            f"{course_title}\n\n"
            f"📖 Total de aulas: {total_lessons}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(message)

    def notify_course_complete(self, course_title, course_num, total_courses, duration):
        """Notifica conclusão de um curso."""
        message = (
            f"✅ CURSO CONCLUÍDO [{course_num}/{total_courses}]\n\n"
            f"{course_title}\n\n"
            f"⏱️ Tempo total: {duration}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(message)

    def notify_lesson_progress(self, lesson_num, total_lessons, lesson_title):
        """Notifica progresso de aula (apenas múltiplos de 5)."""
        if lesson_num % 5 == 0 or lesson_num == total_lessons:
            message = (
                f"📖 PROGRESSO [{lesson_num}/{total_lessons}]\n\n"
                f"{lesson_title}"
            )
            self.send(message)

    def notify_session_expired(self):
        """Notifica que a sessão expirou."""
        message = (
            "⚠️ AVISO DE SESSÃO\n\n"
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
            f"❌ ERRO\n\n"
            f"{error_message}"
        )
        self.send(message)

    def notify_complete(self, total_time):
        """Notifica conclusão de todo o processo."""
        message = (
            "🎉 PROCESSO CONCLUÍDO\n\n"
            f"⏱️ Tempo total: {total_time}\n"
            f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            "✅ Todos os downloads foram finalizados!"
        )
        self.send(message)


# ============================================================================
# HANDLER CUSTOMIZADO PARA LOGGING VIA TELEGRAM
# ============================================================================

class TelegramLoggingHandler(logging.Handler):
    """Handler de logging que envia logs importantes para o Telegram."""

    def __init__(self, notifier):
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
        """Envia log para o Telegram."""
        try:
            if record.levelno >= logging.WARNING:
                emoji = self.emoji_map.get(record.levelname, '📝')
                message = (
                    f"{emoji} {record.levelname}\n\n"
                    f"{record.getMessage()}\n\n"
                    f"📁 {record.name}"
                )
                self.notifier.send(message)
        except Exception:
            self.handleError(record)


# --- Funções Auxiliares ---

def sanitize_filename(original_filename):
    """Remove caracteres inválidos de um nome de arquivo/diretório."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '', original_filename)
    sanitized = re.sub(r'[.,]', '', sanitized)
    sanitized = re.sub(r'[\s-]+', '_', sanitized)
    sanitized = sanitized.strip('._- ')
    return sanitized.strip()


def download_file(url, file_path, current_page_url=None, logger=None):
    """Realiza o download de um arquivo usando requests com barra de progresso."""
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
                            print(f"\r Baixando: {os.path.basename(file_path)} [{progress:.2f}%]", end="")

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
    """Tenta fechar popups conhecidos que podem interceptar cliques."""
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
    """Salva os cookies da sessão atual em arquivo."""
    try:
        with open(filepath, "wb") as f:
            pickle.dump(driver.get_cookies(), f)
        print(f"✓ Cookies salvos em {filepath}")
    except Exception as e:
        print(f"Erro ao salvar cookies: {e}")


def load_cookies(driver, filepath=COOKIES_FILE):
    """Carrega cookies salvos para restaurar a sessão."""
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
    """Verifica se ainda está logado na plataforma."""
    try:
        driver.find_element(By.CSS_SELECTOR, "a[href*='dashboard']")
        return True
    except NoSuchElementException:
        return False


def ensure_logged_in(driver, telegram, cookies_file=COOKIES_FILE):
    """Garante que está logado, restaurando cookies se a sessão expirou."""
    if not is_logged_in(driver):
        telegram.notify_session_expired()
        print("\n⚠ Sessão expirada detectada. Tentando restaurar...")

        driver.get(BASE_URL)
        time.sleep(2)

        if load_cookies(driver, cookies_file):
            driver.refresh()
            time.sleep(3)

            if is_logged_in(driver):
                telegram.notify_session_restored()
                print("✓ Sessão restaurada com sucesso!")
                return True
            else:
                print("✗ Não foi possível restaurar a sessão automaticamente.")
                print(" Por favor, faça login manualmente no navegador.")
                input(" Pressione ENTER após fazer o login...")
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
    """Mantém a sessão viva fazendo requisições periódicas em segundo plano."""

    def __init__(self, driver, interval=HEARTBEAT_INTERVAL):
        self.driver = driver
        self.interval = interval
        self.stop_event = threading.Event()
        self.thread = None

    def _heartbeat(self):
        """Thread que executa o heartbeat periodicamente."""
        while not self.stop_event.is_set():
            try:
                self.driver.execute_script("console.log('Session keepalive heartbeat')")
                current_time = datetime.now().strftime('%H:%M:%S')
                print(f"\n[Heartbeat {current_time}] Sessão mantida viva")
            except Exception as e:
                print(f"\n[Heartbeat] Erro: {e}")

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
    """Navega até a página 'Meus Cursos' e extrai os links e títulos dos cursos."""
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
    """Navega até a página de um curso e extrai os links, títulos e subtítulos das aulas."""
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
    """Configura um logger específico para cada curso."""
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

def save_lesson_subjects(lesson_download_path, lesson_subtitle, logger, manifest_manager=None, lesson_title=""):
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

        if manifest_manager:
            manifest_manager.add_file(
                lesson_title=lesson_title,
                file_name="Assuntos_dessa_aula.txt",
                size_bytes=len(lesson_subtitle.encode('utf-8')),
                file_type="text",
                download_time="00:00:00",
                status="success"
            )

        return True

    except Exception as e:
        print(f"Erro ao criar 'Assuntos_dessa_aula.txt': {e}")
        logger.error(f"Erro ao criar 'Assuntos_dessa_aula.txt': {e}")
        return False


def download_electronic_books(driver, lesson_download_path, sanitized_lesson_title, logger, manifest_manager,
                              lesson_title):
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
                download_file_with_tracking(pdf_url, full_file_path, manifest_manager, lesson_title, driver.current_url,
                                            logger)

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


def download_video_supplementary_pdfs(driver, video_info, lesson_download_path, sanitized_lesson_title, index, logger,
                                      manifest_manager, lesson_title):
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
                    download_file_with_tracking(pdf_url, full_file_path, manifest_manager, lesson_title,
                                                driver.current_url, logger)

            else:
                logger.warning(f"{pdf_button_text} encontrado mas sem URL para '{video_info['title']}'")

        except NoSuchElementException:
            print(f"{pdf_button_text} não encontrado para '{video_info['title']}'.")
            logger.info(f"{pdf_button_text} não encontrado.")

        except Exception as e:
            print(f"Erro ao processar '{pdf_button_text}': {e}")
            logger.error(f"Erro ao processar '{pdf_button_text}': {e}")


def download_video_file(driver, video_info, lesson_download_path, sanitized_video_title, logger, manifest_manager,
                        lesson_title):
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

                if download_file_with_tracking(video_url, full_file_path, manifest_manager, lesson_title,
                                               driver.current_url, logger):
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


def download_playlist_videos(driver, videos_list, lesson_download_path,
                             sanitized_lesson_title, logger, manifest_manager,
                             lesson_title, num_concurrent_videos: int = 2):
    """
    Orquestra o download de todos os vídeos da playlist.

    MODIFICADO: Agora usa ParallelVideoDownloader para downloads simultâneos.

    Args:
        driver: WebDriver do Selenium
        videos_list: Lista de dicionários com 'url' e 'title' dos vídeos
        lesson_download_path: Caminho para salvar vídeos
        sanitized_lesson_title: Título sanitizado da aula
        logger: Logger
        manifest_manager: Gerenciador de manifesto
        lesson_title: Título original da aula
        num_concurrent_videos: Número de vídeos a baixar simultaneamente (1-4)
    """
    from video_optimization import ParallelVideoDownloader

    if not videos_list:
        print("Nenhum vídeo encontrado na playlist.")
        logger.info("Nenhum vídeo encontrado na playlist.")
        return

    print(f"\n🎬 Processando {len(videos_list)} vídeos da playlist...")
    logger.info(f"Processando {len(videos_list)} vídeos da playlist.")

    # ========== FASE 1: COLETAR INFORMAÇÕES DOS VÍDEOS ==========

    video_download_tasks = []

    for i, video_info in enumerate(videos_list):
        print(f"\n[Vídeo {i + 1}/{len(videos_list)}] Preparando: {video_info['title']}")
        logger.info(f"Preparando vídeo {i + 1}/{len(videos_list)}: {video_info['title']}")

        try:
            # Navegar para página do vídeo
            driver.get(video_info['url'])
            time.sleep(2)

            # Baixar PDFs suplementares (mantém sequencial, são poucos arquivos)
            download_video_supplementary_pdfs(
                driver, video_info, lesson_download_path,
                sanitized_lesson_title, i, logger, manifest_manager, lesson_title
            )

            # ========== OBTER URL DE DOWNLOAD DO VÍDEO ==========
            video_url, quality = extract_video_download_url(driver, logger)

            if video_url:
                sanitized_video_title = sanitize_filename(video_info['title'])
                video_filename = f"{sanitized_video_title}_Video_{quality}.mp4"
                video_path = os.path.join(lesson_download_path, video_filename)

                # Adicionar à lista de tarefas
                video_download_tasks.append({
                    'url': video_url,
                    'path': video_path,
                    'name': video_filename,
                    'quality': quality,
                    'lesson_title': lesson_title,
                    'video_info': video_info  # Para referência
                })

                print(f"  ✓ URL de download obtida ({quality})")
                logger.info(f"URL de vídeo obtida: {video_filename} ({quality})")
            else:
                print(f"  ⚠️ Não foi possível obter URL de download")
                logger.warning(f"URL de vídeo não encontrada: {video_info['title']}")

        except Exception as e:
            print(f"  ❌ Erro ao preparar vídeo: {e}")
            logger.error(f"Erro ao preparar vídeo {video_info['title']}: {e}")
            continue

    # ========== FASE 2: DOWNLOADS PARALELOS DE VÍDEOS ==========

    if not video_download_tasks:
        print("\n⚠️ Nenhum vídeo para download (URLs não encontradas)")
        logger.warning("Nenhuma URL de vídeo foi obtida para download")
        return

    print(f"\n{'=' * 70}")
    print(f"⚡ INICIANDO DOWNLOADS PARALELOS DE {len(video_download_tasks)} VÍDEOS")
    print(f"{'=' * 70}")
    print(f"Downloads simultâneos: {num_concurrent_videos}\n")

    # Criar downloader paralelo
    video_downloader = ParallelVideoDownloader(
        max_concurrent_videos=num_concurrent_videos,
        logger=logger
    )

    # Adicionar todas as tarefas
    for task_info in video_download_tasks:
        video_downloader.add_video_task(
            video_url=task_info['url'],
            video_path=task_info['path'],
            video_name=task_info['name'],
            quality=task_info['quality'],
            lesson_title=task_info['lesson_title']
        )

    # Executar downloads em paralelo
    stats = video_downloader.download_all_videos()

    # ========== FASE 3: REGISTRAR NO MANIFESTO ==========

    print(f"\n📝 Registrando vídeos no manifesto...")

    for task in video_downloader.tasks:
        try:
            download_time = ""
            if task.start_time and task.end_time:
                duration = task.end_time - task.start_time
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)
                seconds = int(duration % 60)
                download_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            manifest_manager.add_file(
                lesson_title=task.lesson_title,
                file_name=task.video_name,
                size_bytes=task.total_bytes,
                file_type="video",
                download_time=download_time,
                status="success" if task.status == "completed" else task.status
            )

            if task.status == "completed":
                logger.info(f"Vídeo registrado no manifesto: {task.video_name}")
            else:
                logger.warning(f"Vídeo com status '{task.status}': {task.video_name}")

        except Exception as e:
            logger.error(f"Erro ao registrar vídeo no manifesto: {e}")

    print(f"\n✓ Downloads de vídeos concluídos!")
    print(f"  Completados: {stats['completed']}/{stats['total']}")
    print(f"  Falhos: {stats['failed']}/{stats['total']}")
    print(f"  Velocidade média: {stats['average_speed_mbps']:.2f}MB/s\n")

    logger.info(f"Downloads de vídeos finalizados: {stats['completed']} completados, {stats['failed']} falhos")

##
def extract_video_download_url(driver, logger, preferred_qualities=None):
    """
    Extrai URL de download do vídeo em qualidade preferida.

    Esta função SUBSTITUI a lógica antiga de download_video_file() que
    baixava imediatamente. Agora apenas coleta a URL para download posterior.

    Args:
        driver: WebDriver do Selenium
        logger: Logger
        preferred_qualities: Lista de qualidades preferidas (padrão: ['720p', '480p', '360p'])

    Returns:
        Tuple[str, str]: (video_url, quality) ou (None, None) se não encontrou
    """
    if preferred_qualities is None:
        preferred_qualities = ['720p', '480p', '360p']

    try:
        # Expandir "Opções de download"
        download_options_header = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class, 'Collapse-header')]//strong[text()='Opções de download']")
            )
        )

        header_container = download_options_header.find_element(By.XPATH,
                                                                "./ancestor::div[contains(@class, 'Collapse-header-container')]")

        collapse_body = header_container.find_element(By.XPATH, "./following-sibling::div")

        # Expandir se não estiver visível
        if not collapse_body.is_displayed():
            driver.execute_script("arguments[0].click();", download_options_header)
            WebDriverWait(driver, 5).until(EC.visibility_of(collapse_body))

        # Buscar URL da qualidade preferida
        for quality in preferred_qualities:
            try:
                video_link_elem = collapse_body.find_element(By.XPATH, f".//a[contains(text(), '{quality}')]")
                video_url = video_link_elem.get_attribute('href')

                if video_url:
                    logger.info(f"URL de download encontrada: {quality}")
                    return video_url, quality

            except NoSuchElementException:
                logger.debug(f"Qualidade {quality} não disponível")
                continue

        # Nenhuma qualidade preferida encontrada
        logger.warning("Nenhuma URL de download encontrada nas qualidades preferidas")
        return None, None

    except TimeoutException:
        logger.warning("Não foi possível encontrar/expandir 'Opções de download'")
        return None, None

    except Exception as e:
        logger.error(f"Erro ao extrair URL de vídeo: {e}")
        return None, None
##
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


def save_course_metadata(course_path, original_title, logger=None):
    """Salva metadados do curso em JSON para facilitar matching posterior."""
    metadata_path = os.path.join(course_path, "course_metadata.json")

    if os.path.exists(metadata_path):
        return

    try:
        metadata = {
            "original_title": original_title,
            "download_date": datetime.now().isoformat(),
            "sanitized_title": os.path.basename(course_path)
        }

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        if logger:
            logger.info(f"Metadados do curso salvos: {original_title}")

    except Exception as e:
        if logger:
            logger.warning(f"Erro ao salvar metadados: {e}")


def create_lesson_directory(download_dir, course_title, lesson_title, logger):
    """Cria o diretório para a aula."""
    sanitized_course_title = sanitize_filename(course_title)
    sanitized_lesson_title = sanitize_filename(lesson_title)
    lesson_download_path = os.path.join(download_dir, sanitized_course_title, sanitized_lesson_title)

    try:
        os.makedirs(lesson_download_path, exist_ok=True)

        save_course_metadata(
            os.path.join(download_dir, sanitized_course_title),
            course_title,
            logger
        )

        return lesson_download_path

    except OSError as e:
        print(f"ERRO CRÍTICO ao criar diretório: {e}")
        logger.error(f"Erro ao criar diretório: {e}")
        return None


# ============================================================================
# MODIFICAÇÃO PRINCIPAL: FUNÇÃO DE DOWNLOAD COM PARALELIZAÇÃO (NOVO)
# ============================================================================

def download_lesson_materials(driver, lesson_info, course_title, download_dir, logger,
                              manifest_manager, num_concurrent_downloads: int = 3,  num_concurrent_videos: int = 3):
    """
    Orquestra o download de todos os materiais de uma aula.

    MODIFICAÇÃO: Integrado com paralelização de downloads.
    Downloads não-vídeo (PDFs, etc) são baixados em paralelo usando ThreadPoolExecutor.
    Vídeos continuam sequenciais por restrições de rede.
    """
    lesson_title = lesson_info['title']
    lesson_subtitle = lesson_info['subtitle']
    lesson_url = lesson_info['url']

    print(f"Processando aula: {lesson_title}")
    logger.info(f"Iniciando processamento da aula: {lesson_title}")

    # Inicia rastreamento da aula
    manifest_manager.start_lesson(lesson_title)

    if not navigate_to_lesson(driver, lesson_url, logger):
        return

    handle_popups(driver)

    lesson_download_path = create_lesson_directory(download_dir, course_title, lesson_title, logger)

    if not lesson_download_path:
        return

    save_lesson_subjects(lesson_download_path, lesson_subtitle, logger, manifest_manager, lesson_title)

    sanitized_lesson_title = sanitize_filename(lesson_title)

    # ========== NOVO: DOWNLOADS PARALELOS PARA PDFs ==========

    # Criar gerenciador de downloads paralelos para PDFs
    download_manager = create_download_manager(
        num_workers=num_concurrent_downloads,
        logger=logger
    )

    # Iniciar monitor de progresso visual
    monitor = ProgressMonitor(update_interval=1.0)
    monitor.start()

    # Configurar callback de progresso
    def progress_callback(task):
        monitor.add_task(task)

    download_manager.set_progress_callback(progress_callback)

    # ========== COLETANDO PDFs para download paralelo ==========

    try:
        print("Coletando PDFs para download paralelo...")

        # Encontrar PDFs eletrônicos
        pdf_links = driver.find_elements(By.XPATH,
                                         "//a[contains(@class, 'LessonButton') and .//i[contains(@class, 'icon-file')]]")

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

            if not os.path.exists(full_file_path):
                # Adicionar ao gerenciador para download paralelo
                task = download_manager.add_download_task(
                    file_url=pdf_url,
                    file_path=full_file_path,
                    file_name=filename,
                    file_type="pdf",
                    lesson_title=lesson_title
                )

                manifest_manager.start_lesson(lesson_title)

    except Exception as e:
        print(f"Erro ao coletar PDFs: {e}")
        logger.error(f"Erro ao coletar PDFs: {e}")

    # ========== EXECUTAR DOWNLOADS PARALELOS DE PDFs ==========

    if download_manager.tasks:
        print(f"\n📊 Iniciando download paralelo de {len(download_manager.tasks)} PDF(s)...")
        stats = download_manager.download_all()
        monitor.stop()
        print_download_summary(stats)

        # Registrar no manifesto
        for task in download_manager.tasks:
            if task.status != "pending":
                download_time = ""
                if task.start_time and task.end_time:
                    download_time = f"{int(task.end_time - task.start_time)}s"

                manifest_manager.add_file(
                    lesson_title=task.lesson_title,
                    file_name=task.file_name,
                    size_bytes=task.total_bytes,
                    file_type=task.file_type,
                    download_time=download_time,
                    status=task.status
                )
    else:
        monitor.stop()
        print("Nenhum PDF para download paralelo.")

    # ========== VÍDEOS (mantém lógica original, sequencial) ==========
    videos_list = get_playlist_videos(driver, logger)

    if videos_list:
        download_playlist_videos(
            driver,
            videos_list,
            lesson_download_path,
            sanitized_lesson_title,
            logger,
            manifest_manager,
            lesson_title,
            num_concurrent_videos=num_concurrent_videos  # ← PASSAR AQUI
        )

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

    save_cookies(driver)


def pick_courses(courses):
    """Lista os cursos e permite seleção interativa."""
    if not courses:
        print("❌ Nenhum curso disponível para seleção.")
        return []

    print("\nCURSOS DISPONÍVEIS:")
    for idx, course in enumerate(courses, 1):
        print(f" [{idx}] {course['title']}")

    while True:
        try:
            sel = input("\nDigite os números dos cursos a baixar (ex: 1,3,5): ").strip()

            if not sel:
                print("⚠️ Por favor, digite pelo menos um número.")
                continue

            indices = []
            for x in sel.split(","):
                x = x.strip()
                if x.isdigit():
                    idx = int(x) - 1
                    if 0 <= idx < len(courses):
                        indices.append(idx)
                    else:
                        print(f"⚠️ Número {int(x)} fora do intervalo [1-{len(courses)}]")

            if indices:
                selected = [courses[idx] for idx in indices]
                print(f"\n✓ Selecionados {len(selected)} curso(s)")
                return selected

            else:
                print("⚠️ Nenhum número válido foi selecionado. Tente novamente.")

        except Exception as e:
            print(f"⚠️ Erro ao processar entrada: {e}")
            print(" Tente novamente (ex: 1,3,5)")


def ask_concurrent_downloads(logger=None) -> int:
    """
    Solicita ao usuário quantos downloads simultâneos deseja.
    MODIFICADO: Usa nova interface do ConcurrencySelector.
    """
    return ConcurrencySelector.get_concurrent_downloads(max_limit=10, logger=logger)
##
def ask_video_concurrent_downloads(logger=None) -> int:
    """
    Solicita ao usuário quantos vídeos baixar simultaneamente.
    """
    print("\n" + "=" * 70)
    print("🎬 CONFIGURAÇÃO DE DOWNLOADS DE VÍDEOS")
    print("=" * 70)
    print("\nQuantos vídeos deseja baixar simultaneamente?")
    print("(Recomendado: 2-3 | Máximo: 4)\n")

    recomendacoes = {
        1: "Sequencial (mais lento, conexão fraca)",
        2: "Duplo (RECOMENDADO - bom equilíbrio)",
        3: "Triplo (rápido, requer >10Mbps)",
        4: "Quádruplo (muito rápido, requer >20Mbps)"
    }

    for num, desc in recomendacoes.items():
        print(f"  [{num}] {desc}")

    while True:
        try:
            user_input = input("\n👉 Digite o número (1-4): ").strip()
            num_videos = int(user_input)

            if 1 <= num_videos <= 4:
                print(f"\n✓ Downloads simultâneos de vídeos: {num_videos}")
                if logger:
                    logger.info(f"Downloads simultâneos de vídeos: {num_videos}")
                return num_videos
            else:
                print(f"❌ Número fora do intervalo (1-4). Tente novamente.")

        except ValueError:
            print("❌ Digite um número válido (ex: 1, 2, 3...)")
##
def run_downloader(download_dir, login_wait_time):
    """
    II - Função principal que orquestra todo o processo de download.
    MELHORIAS IMPLEMENTADAS:
    1. Heartbeat para manter sessão viva durante downloads longos
    2. Salvamento e restauração automática de cookies
    3. Verificação de sessão antes de processar cada curso
    4. Rastreamento de arquivos baixados em JSON (Feature #1)
    5. Detecção de cursos com aulas pendentes (Feature #2)
    6. Downloads paralelos com interface interativa (Feature #3)
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

    # Inicializa sistema de heartbeat
    keepalive = SessionKeepAlive(driver, interval=HEARTBEAT_INTERVAL)

    try:
        login(driver, login_wait_time)

        # Inicia heartbeat após login
        keepalive.start()

        courses = get_course_data(driver)

        if not courses:
            print("Nenhum curso encontrado. Encerrando.")
            return

        # FEATURE #2 MELHORADA: Verificar cursos já baixados e detectar aulas FALTANTES
        try:
            incomplete_courses, courses_map = find_incomplete_courses(
                driver, download_dir, courses, telegram
            )

        except ValueError as e:
            print(f"Erro ao detectar cursos incompletos: {e}")
            telegram.send(f"❌ Erro ao detectar cursos: {e}")
            incomplete_courses = []
            courses_map = {}

        # Se houver cursos incompletos, oferecer ao usuário completá-los PRIMEIRO
        if incomplete_courses and len(incomplete_courses) > 0:
            print(f"\n{'=' * 70}")
            print(f"⚠️ ENCONTRADOS {len(incomplete_courses)} CURSO(S) COM AULAS FALTANDO!")
            print(f"{'=' * 70}\n")

            print("Cursos a serem completados:\n")
            for idx, info in enumerate(incomplete_courses, 1):
                course = info['course']
                print(f" [{idx}] {course['title']}")
                print(f" ├─ Aulas locais: {info['local_total']}/{info['platform_total']}")
                print(f" ├─ Faltam: {info['missing']} aulas")
                print(f" └─ Progresso: {info['progress']}\n")

            print()

            choice = input("Deseja COMPLETAR esses cursos agora? (s/n): ").strip().lower()

            if choice == 's':
                print("\n✓ Iniciando download de aulas PENDENTES...")
                selected_courses = [info['course'] for info in incomplete_courses]

                telegram.send(
                    f"🔄 COMPLETANDO CURSOS INCOMPLETOS\n"
                    f"Total de cursos: {len(incomplete_courses)}\n"
                    f"Aulas faltando: {sum(info['missing'] for info in incomplete_courses)}"
                )

            else:
                print("\n▶️ Oferecendo novo download de cursos...")
                selected_courses = pick_courses(courses)

        else:
            print("\n✓ Nenhum curso com aulas faltando. Oferecendo novo download...\n")
            selected_courses = pick_courses(courses)

        # ✅ Validar se há cursos selecionados
        if not selected_courses:
            print("❌ Nenhum curso foi selecionado.")
            print("Encerrando execução.")
            telegram.send("⚠️ Nenhum curso foi selecionado. Execução encerrada.")
            return

        # ✅ NOVO: Solicitar número de downloads simultâneos AQUI
        num_concurrent = ask_concurrent_downloads(logger=None)
        num_concurrent_videos = ask_video_concurrent_downloads(logger=None)

        telegram.notify_start(len(selected_courses))

        for i, course in enumerate(selected_courses):
            # Verifica e restaura sessão antes de cada curso
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

            # FEATURE #1: Inicializar gerenciador de manifesto para este curso
            course_download_path = os.path.join(download_dir, sanitize_filename(course['title']))
            os.makedirs(course_download_path, exist_ok=True)

            manifest_manager = FileManifestManager(course_download_path, logger)

            start_time = datetime.now()

            lessons = get_lesson_data(driver, course['url'])

            if not lessons:
                print(f"Nenhuma aula encontrada para '{course['title']}'. Pulando.")
                logger.warning("Nenhuma aula encontrada para este curso.")
                continue

            telegram.notify_course_start(course['title'], i + 1, len(selected_courses), len(lessons))

            for j, lesson_info in enumerate(lessons):
                print(f"\n -> Aula {j + 1}/{len(lessons)}: {lesson_info['title']}")
                logger.info(f"Processando aula {j + 1}/{len(lessons)}: {lesson_info['title']}")

                # ✅ MODIFICAÇÃO: Passar num_concurrent_downloads para download_lesson_materials
                download_lesson_materials(
                    driver,
                    lesson_info,
                    course['title'],
                    download_dir,
                    logger,
                    manifest_manager,
                    num_concurrent_downloads=num_concurrent, # ← PDF
                    num_concurrent_videos = num_concurrent_videos  # ← Vídeos
                )

                telegram.notify_lesson_progress(j + 1, len(lessons), lesson_info['title'])

                time.sleep(2)

            end_time = datetime.now()
            delta = end_time - start_time

            # FEATURE #1: Exibir estatísticas do manifesto
            stats = manifest_manager.get_course_statistics()

            print(f"\n📊 Estatísticas do Curso:")
            print(f" ├─ Aulas processadas: {stats['total_lessons']}")
            print(f" ├─ Arquivos baixados: {stats['total_files']}")
            print(f" └─ Tamanho total: {stats['total_size_gb']} GB")

            telegram.notify_course_complete(course['title'], i + 1, len(selected_courses), str(delta))

            logger.info(f"Download do curso finalizado. Tempo total: {delta}")

            print(f"\n✓ Tempo de download do curso: {delta}")

        total_time = datetime.now() - (datetime.now() - (end_time - start_time) * len(selected_courses))

        telegram.notify_complete(str(delta))

    except Exception as e:
        telegram.notify_error(str(e))
        print(f"\nErro geral no script: {e}")

    finally:
        # Para heartbeat antes de encerrar
        keepalive.stop()

        print("\nProcesso concluído. Fechando navegador em 10 segundos.")
        time.sleep(10)

        driver.quit()


def main():
    """I - Analisa argumentos de linha de comando e inicia o processo."""
    parser = argparse.ArgumentParser(
        description="Baixador de cursos do Estratégia Concursos com gerenciamento de sessão e rastreamento.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        '-d', '--dir',
        dest='download_dir',
        metavar='PATH',
        type=str,
        default="C:/Users/joao.santosm/projetos/curso/SERPRO (Analista - Desenvolvimento de Sistemas) Pacote",
        help="O caminho para a pasta onde os cursos serão salvos.\n(Padrão: C:/Users/joao.santosm/projetos/curso/)"
    )

    parser.add_argument(
        "-w", "--wait-time",
        dest='wait_time',
        type=int,
        default=60,
        help="Tempo em segundos para aguardar o login manual (padrão: 60)."
    )

    args = parser.parse_args()

    run_downloader(args.download_dir, args.wait_time)


if __name__ == "__main__":
    main()
