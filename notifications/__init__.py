"""
Pacote de notificações do AutoDownloader.

Exporta classes e funções para notificações e logging.
"""

from .telegram import TelegramNotifier
from .logger import (
    TelegramLoggingHandler,
    setup_logger,
    setup_course_logger,
    get_logger,
    LoggerContext,
)

__all__ = [
    'TelegramNotifier',
    'TelegramLoggingHandler',
    'setup_logger',
    'setup_course_logger',
    'get_logger',
    'LoggerContext',
]
