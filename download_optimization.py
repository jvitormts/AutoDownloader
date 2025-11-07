# ============================================================================
# MÓDULO DE OTIMIZAÇÃO DE DOWNLOADS COM PARALELIZAÇÃO
# ============================================================================
# Este módulo implementa downloads simultâneos com monitoramento de progresso
# e visualização em tempo real da velocidade de download.

import os
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Tuple, Callable, Optional
import requests
import logging


# ============================================================================
# CLASSE 1: GERENCIADOR DE DOWNLOADS PARALELOS
# ============================================================================

class DownloadTask:
    """Representa uma tarefa de download com metadados."""

    def __init__(self, file_url: str, file_path: str, file_name: str,
                 file_type: str, lesson_title: str):
        self.file_url = file_url
        self.file_path = file_path
        self.file_name = file_name
        self.file_type = file_type
        self.lesson_title = lesson_title
        self.status = "pending"  # pending, downloading, completed, failed, skipped
        self.bytes_downloaded = 0
        self.total_bytes = 0
        self.start_time = None
        self.end_time = None
        self.error_message = ""

    def get_progress_percentage(self) -> float:
        """Retorna o percentual de progresso do download."""
        if self.total_bytes == 0:
            return 0
        return (self.bytes_downloaded / self.total_bytes) * 100

    def get_download_speed_mbps(self) -> float:
        """Calcula a velocidade de download em MB/s."""
        if self.start_time is None:
            return 0
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0
        mb_downloaded = self.bytes_downloaded / (1024 * 1024)
        return mb_downloaded / elapsed

    def get_eta_seconds(self) -> float:
        """Calcula o tempo estimado de conclusão em segundos."""
        speed_mbs = self.get_download_speed_mbps()
        if speed_mbs == 0:
            return 0
        remaining_mb = (self.total_bytes - self.bytes_downloaded) / (1024 * 1024)
        return remaining_mb / speed_mbs

    def to_dict(self) -> dict:
        """Converte a tarefa para dicionário."""
        return {
            "file_name": self.file_name,
            "file_type": self.file_type,
            "lesson_title": self.lesson_title,
            "status": self.status,
            "progress": self.get_progress_percentage(),
            "speed_mbps": self.get_download_speed_mbps(),
            "eta_seconds": self.get_eta_seconds(),
            "bytes_downloaded": self.bytes_downloaded,
            "total_bytes": self.total_bytes
        }


class ParallelDownloadManager:
    """Gerencia downloads simultâneos com monitoramento de progresso."""

    def __init__(self, max_workers: int = 3, logger: logging.Logger = None,
                 telegram_notifier=None):
        """
        Inicializa o gerenciador de downloads.

        Args:
            max_workers (int): Número máximo de downloads simultâneos (1-10)
            logger (logging.Logger): Logger para registrar ações
            telegram_notifier: Notificador do Telegram para alertas
        """
        self.max_workers = max(1, min(max_workers, 10))  # Limita entre 1-10
        self.logger = logger
        self.telegram_notifier = telegram_notifier
        self.tasks: List[DownloadTask] = []
        self.tasks_lock = threading.Lock()
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.skipped_tasks = 0
        self.progress_callback: Optional[Callable] = None

    def add_download_task(self, file_url: str, file_path: str, file_name: str,
                          file_type: str, lesson_title: str) -> DownloadTask:
        """
        Adiciona uma tarefa de download à fila.

        Args:
            file_url (str): URL do arquivo
            file_path (str): Caminho local onde salvar
            file_name (str): Nome do arquivo
            file_type (str): Tipo de arquivo (pdf, video, etc)
            lesson_title (str): Título da aula

        Returns:
            DownloadTask: A tarefa criada
        """
        task = DownloadTask(file_url, file_path, file_name, file_type, lesson_title)
        with self.tasks_lock:
            self.tasks.append(task)
        return task

    def set_progress_callback(self, callback: Callable):
        """Define callback para atualizações de progresso em tempo real."""
        self.progress_callback = callback

    def _download_file(self, task: DownloadTask) -> Tuple[bool, str, int]:
        """
        Baixa um arquivo individual com acompanhamento de progresso.

        Args:
            task (DownloadTask): Tarefa de download

        Returns:
            Tuple[bool, str, int]: (sucesso, mensagem_erro, bytes_baixados)
        """
        try:
            # Verifica se arquivo já existe
            if os.path.exists(task.file_path):
                task.status = "skipped"
                task.bytes_downloaded = os.path.getsize(task.file_path)
                task.total_bytes = task.bytes_downloaded
                if self.logger:
                    self.logger.info(f"Arquivo já existe (pulado): {task.file_name}")
                return True, "already_exists", 0

            # Cria diretório se não existir
            os.makedirs(os.path.dirname(task.file_path), exist_ok=True)

            task.status = "downloading"
            task.start_time = time.time()

            # Fazer requisição com stream=True
            response = requests.get(task.file_url, stream=True, timeout=30)
            response.raise_for_status()

            # Obter tamanho total do arquivo
            task.total_bytes = int(response.headers.get('content-length', 0))

            # Download com progresso
            chunk_size = 8192  # 8KB chunks
            bytes_downloaded = 0

            with open(task.file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        task.bytes_downloaded = bytes_downloaded

                        # Chamar callback de progresso
                        if self.progress_callback:
                            self.progress_callback(task)

            task.status = "completed"
            task.end_time = time.time()

            if self.logger:
                speed = task.get_download_speed_mbps()
                self.logger.info(f"✓ Concluído: {task.file_name} "
                                 f"({task.total_bytes / (1024 * 1024):.2f}MB @ {speed:.2f}MB/s)")

            return True, "", bytes_downloaded

        except os.path.exists(task.file_path):
            task.status = "skipped"
            return True, "file_exists", 0

        except requests.exceptions.Timeout:
            task.status = "failed"
            error_msg = "Timeout na conexão"
            task.error_message = error_msg
            if self.logger:
                self.logger.error(f"❌ {error_msg}: {task.file_name}")
            return False, error_msg, 0

        except requests.exceptions.ConnectionError:
            task.status = "failed"
            error_msg = "Erro de conexão"
            task.error_message = error_msg
            if self.logger:
                self.logger.error(f"❌ {error_msg}: {task.file_name}")
            return False, error_msg, 0

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            if self.logger:
                self.logger.error(f"❌ Erro ao baixar {task.file_name}: {e}")
            return False, str(e), 0

    def download_all(self) -> Dict:
        """
        Executa todos os downloads simultaneamente.

        Returns:
            Dict: Estatísticas dos downloads
        """
        if not self.tasks:
            return {"total": 0, "completed": 0, "failed": 0, "skipped": 0}

        print(f"\n{'=' * 70}")
        print(f"🚀 INICIANDO DOWNLOADS PARALELOS")
        print(f"{'=' * 70}")
        print(f"Total de arquivos: {len(self.tasks)}")
        print(f"Downloads simultâneos: {self.max_workers}\n")

        start_time = time.time()
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.skipped_tasks = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submeter todas as tarefas
            futures = {
                executor.submit(self._download_file, task): task
                for task in self.tasks
            }

            # Processar resultados conforme são completados
            for future in as_completed(futures):
                task = futures[future]
                try:
                    success, error, bytes_dl = future.result()

                    if success:
                        if task.status == "completed":
                            self.completed_tasks += 1
                        elif task.status == "skipped":
                            self.skipped_tasks += 1
                    else:
                        self.failed_tasks += 1

                except Exception as e:
                    self.failed_tasks += 1
                    if self.logger:
                        self.logger.error(f"Erro ao processar tarefa: {e}")

        elapsed = time.time() - start_time
        total_size = sum(t.total_bytes for t in self.tasks) / (1024 * 1024)
        avg_speed = total_size / elapsed if elapsed > 0 else 0

        stats = {
            "total": len(self.tasks),
            "completed": self.completed_tasks,
            "failed": self.failed_tasks,
            "skipped": self.skipped_tasks,
            "total_time": elapsed,
            "total_size_mb": round(total_size, 2),
            "average_speed_mbps": round(avg_speed, 2)
        }

        return stats

    def get_progress_summary(self) -> Dict:
        """Retorna um resumo do progresso atual."""
        with self.tasks_lock:
            tasks_copy = self.tasks.copy()

        completed = len([t for t in tasks_copy if t.status == "completed"])
        downloading = len([t for t in tasks_copy if t.status == "downloading"])
        pending = len([t for t in tasks_copy if t.status == "pending"])
        failed = len([t for t in tasks_copy if t.status == "failed"])
        skipped = len([t for t in tasks_copy if t.status == "skipped"])

        total_bytes = sum(t.total_bytes for t in tasks_copy)
        downloaded_bytes = sum(t.bytes_downloaded for t in tasks_copy)

        progress_pct = (downloaded_bytes / total_bytes * 100) if total_bytes > 0 else 0

        # Calcular velocidade média dos que estão sendo baixados
        downloading_tasks = [t for t in tasks_copy if t.status == "downloading"]
        avg_speed = sum(t.get_download_speed_mbps() for t in downloading_tasks) / len(
            downloading_tasks) if downloading_tasks else 0

        return {
            "completed": completed,
            "downloading": downloading,
            "pending": pending,
            "failed": failed,
            "skipped": skipped,
            "progress_percentage": round(progress_pct, 2),
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "downloaded_mb": round(downloaded_bytes / (1024 * 1024), 2),
            "current_speed_mbps": round(avg_speed, 2)
        }


# ============================================================================
# CLASSE 2: MONITOR DE PROGRESSO EM TEMPO REAL
# ============================================================================

class ProgressMonitor:
    """Monitora e exibe progresso de downloads em tempo real."""

    def __init__(self, update_interval: float = 1.0):
        """
        Inicializa o monitor.

        Args:
            update_interval (float): Intervalo de atualização em segundos
        """
        self.update_interval = update_interval
        self.active_tasks: Dict[str, DownloadTask] = {}
        self.tasks_lock = threading.Lock()
        self.running = False
        self.monitor_thread = None

    def add_task(self, task: DownloadTask):
        """Adiciona tarefa ao monitoramento."""
        with self.tasks_lock:
            self.active_tasks[task.file_name] = task

    def remove_task(self, file_name: str):
        """Remove tarefa do monitoramento."""
        with self.tasks_lock:
            self.active_tasks.pop(file_name, None)

    def _format_bytes(self, bytes_value: int) -> str:
        """Formata bytes para formato legível."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024:
                return f"{bytes_value:.2f}{unit}"
            bytes_value /= 1024
        return f"{bytes_value:.2f}TB"

    def _format_time(self, seconds: float) -> str:
        """Formata segundos para HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _display_progress(self):
        """Exibe progresso em tempo real."""
        while self.running:
            with self.tasks_lock:
                tasks = list(self.active_tasks.values())

            if not tasks:
                time.sleep(self.update_interval)
                continue

            # Limpar tela e exibir progresso
            os.system('cls' if os.name == 'nt' else 'clear')

            print("\n" + "=" * 80)
            print("📊 MONITORAMENTO DE DOWNLOADS EM TEMPO REAL")
            print("=" * 80 + "\n")

            for task in tasks:
                if task.status in ["downloading", "completed"]:
                    progress = task.get_progress_percentage()
                    speed = task.get_download_speed_mbps()
                    eta = task.get_eta_seconds()

                    # Barra de progresso
                    bar_length = 50
                    filled = int(bar_length * progress / 100)
                    bar = "█" * filled + "░" * (bar_length - filled)

                    print(f"📁 {task.file_name}")
                    print(f"   [{bar}] {progress:.1f}%")
                    print(f"   ↓ {self._format_bytes(task.bytes_downloaded)}/{self._format_bytes(task.total_bytes)} "
                          f"| ⚡ {speed:.2f}MB/s | ⏱ ETA: {self._format_time(eta)}")
                    print()

            time.sleep(self.update_interval)

    def start(self):
        """Inicia o monitor em thread separada."""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._display_progress, daemon=True)
            self.monitor_thread.start()

    def stop(self):
        """Para o monitor."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)


# ============================================================================
# CLASSE 3: INTERFACE DE SELEÇÃO DO NÚMERO DE THREADS
# ============================================================================

class ConcurrencySelector:
    """Interface para usuário selecionar número de downloads simultâneos."""

    @staticmethod
    def get_concurrent_downloads(max_limit: int = 10, logger: logging.Logger = None) -> int:
        """
        Solicita ao usuário quantos downloads simultâneos deseja.

        Args:
            max_limit (int): Limite máximo de downloads
            logger (logging.Logger): Logger para registrar

        Returns:
            int: Número de downloads simultâneos escolhido
        """
        print("\n" + "=" * 70)
        print("⚙️  CONFIGURAÇÃO DE DOWNLOADS SIMULTÂNEOS")
        print("=" * 70)
        print("\nQuantos arquivos deseja baixar simultaneamente?")
        print(f"(Recomendado: 3-5 | Máximo: {max_limit})\n")

        recomendacoes = {
            1: "Sequencial (mais lento, menos uso de banda)",
            2: "Duplo (lento)",
            3: "Triplo (RECOMENDADO - bom equilíbrio)",
            4: "Quádruplo (rápido)",
            5: "Quíntuplo (rápido)",
        }

        for num, desc in recomendacoes.items():
            print(f"  [{num}] {desc}")
        print(f"  [6-{max_limit}] Valores customizados")

        while True:
            try:
                user_input = input("\n👉 Digite o número (1-10): ").strip()
                num_threads = int(user_input)

                # Validar intervalo
                if 1 <= num_threads <= max_limit:
                    print(f"\n✓ Downloads simultâneos configurado para: {num_threads}")
                    if logger:
                        logger.info(f"Downloads simultâneos: {num_threads}")

                    # Mostrar recomendação
                    if num_threads <= 2:
                        print("⚠️  Aviso: Download lento com este valor.")
                    elif num_threads > 5:
                        print("⚠️  Aviso: Usar muitas conexões pode sobrecarregar a banda.")

                    return num_threads
                else:
                    print(f"❌ Número fora do intervalo (1-{max_limit}). Tente novamente.")

            except ValueError:
                print("❌ Digite um número válido (ex: 1, 2, 3...)")


# ============================================================================
# FUNÇÕES DE INTEGRAÇÃO COM CÓDIGO EXISTENTE
# ============================================================================

def create_download_manager(num_workers: int, logger: logging.Logger = None,
                            telegram_notifier=None) -> ParallelDownloadManager:
    """
    Factory para criar gerenciador de downloads.

    Args:
        num_workers (int): Número de workers (threads)
        logger (logging.Logger): Logger
        telegram_notifier: Notificador do Telegram

    Returns:
        ParallelDownloadManager: Gerenciador configurado
    """
    return ParallelDownloadManager(
        max_workers=num_workers,
        logger=logger,
        telegram_notifier=telegram_notifier
    )


def print_download_summary(stats: Dict):
    """
    Exibe resumo final dos downloads.

    Args:
        stats (Dict): Dicionário com estatísticas
    """
    print("\n" + "=" * 70)
    print("📊 RESUMO DE DOWNLOADS")
    print("=" * 70)
    print(f"✓ Completados: {stats['completed']}")
    print(f"⊘ Pulados: {stats['skipped']}")
    print(f"✗ Falhos: {stats['failed']}")
    print(f"📦 Total de dados: {stats['total_size_mb']}MB")
    print(f"⏱ Tempo total: {stats['total_time']:.2f}s")
    print(f"⚡ Velocidade média: {stats['average_speed_mbps']:.2f}MB/s")
    print("=" * 70 + "\n")
