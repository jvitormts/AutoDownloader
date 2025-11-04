"""
Módulo de configuração de logging.

Configura sistema de logging com suporte a Telegram.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from config import settings, EMOJI


class TelegramLoggingHandler(logging.Handler):
    """
    Handler de logging que envia logs importantes para o Telegram.

    Integra-se com o sistema de logging do Python para enviar
    mensagens de WARNING, ERROR e CRITICAL para o Telegram.
    """

    def __init__(self, notifier):
        """
        Inicializa o handler.

        Args:
            notifier: Instância do TelegramNotifier
        """
        super().__init__()
        self.notifier = notifier
        self.emoji_map = {
            'DEBUG': '🔍',
            'INFO': EMOJI['info'],
            'WARNING': EMOJI['warning'],
            'ERROR': EMOJI['error'],
            'CRITICAL': '🚨'
        }

    def emit(self, record: logging.LogRecord) -> None:
        """
        Envia log para o Telegram.

        Apenas logs de nível WARNING ou superior são enviados.

        Args:
            record: Registro de log
        """
        try:
            if record.levelno >= logging.WARNING:
                emoji = self.emoji_map.get(record.levelname, '📝')
                message = (
                    f"{emoji} <b>{record.levelname}</b>\n\n"
                    f"{record.getMessage()}\n\n"
                    f"📁 {record.name}"
                )
                self.notifier.send(message)
        except Exception:
            self.handleError(record)


def setup_logger(
        name: str,
        log_file: Optional[str] = None,
        level: str = None,
        telegram_notifier=None
) -> logging.Logger:
    """
    Configura e retorna um logger.

    Args:
        name: Nome do logger
        log_file: Caminho do arquivo de log (opcional)
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        telegram_notifier: Instância do TelegramNotifier (opcional)

    Returns:
        logging.Logger: Logger configurado

    Examples:
        >>> logger = setup_logger('downloader', 'app.log', 'INFO')
        >>> logger.info('Aplicação iniciada')
    """
    logger = logging.getLogger(name)

    # Evitar duplicação de handlers
    if logger.handlers:
        return logger

    # Definir nível de log
    log_level = getattr(logging, (level or settings.LOG_LEVEL).upper(), logging.INFO)
    logger.setLevel(log_level)

    # Formato de log
    formatter = logging.Formatter(
        settings.LOG_FORMAT,
        datefmt=settings.LOG_DATE_FORMAT
    )

    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler para arquivo (se especificado)
    if log_file:
        # Garantir que o diretório existe
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Handler para Telegram (se fornecido)
    if telegram_notifier:
        telegram_handler = TelegramLoggingHandler(telegram_notifier)
        telegram_handler.setLevel(logging.WARNING)  # Apenas WARNING+
        logger.addHandler(telegram_handler)

    return logger


def setup_course_logger(
        course_title: str,
        download_dir: str,
        telegram_notifier=None
) -> logging.Logger:
    """
    Configura logger específico para um curso.

    Args:
        course_title: Título do curso
        download_dir: Diretório de download
        telegram_notifier: Instância do TelegramNotifier

    Returns:
        logging.Logger: Logger configurado para o curso

    Examples:
        >>> logger = setup_course_logger('Python Básico', '/downloads')
    """
    from utils import sanitize_filename

    # Sanitizar nome do curso para usar como nome de arquivo
    safe_course_name = sanitize_filename(course_title)

    # Criar diretório de logs
    log_dir = Path(download_dir) / safe_course_name / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Nome do arquivo de log com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"download_{timestamp}.log"

    # Criar logger
    logger_name = f"course.{safe_course_name}"
    logger = setup_logger(
        name=logger_name,
        log_file=str(log_file),
        telegram_notifier=telegram_notifier
    )

    logger.info(f"Logger iniciado para curso: {course_title}")
    logger.info(f"Arquivo de log: {log_file}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Obtém um logger existente ou cria um novo.

    Args:
        name: Nome do logger

    Returns:
        logging.Logger: Logger

    Examples:
        >>> logger = get_logger(__name__)
    """
    return logging.getLogger(name)


class LoggerContext:
    """
    Context manager para logging temporário.

    Examples:
        >>> with LoggerContext('temp_operation', 'temp.log') as logger:
        ...     logger.info('Operação temporária')
    """

    def __init__(self, name: str, log_file: str, level: str = 'INFO'):
        """
        Inicializa o context manager.

        Args:
            name: Nome do logger
            log_file: Arquivo de log
            level: Nível de log
        """
        self.name = name
        self.log_file = log_file
        self.level = level
        self.logger = None

    def __enter__(self) -> logging.Logger:
        """Entra no contexto."""
        self.logger = setup_logger(self.name, self.log_file, self.level)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sai do contexto."""
        if self.logger:
            # Remover handlers
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
