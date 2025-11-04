"""
Pacote de configuração do AutoDownloader.

Exporta as configurações e constantes do sistema.
"""

from .settings import settings, Settings
from .constants import (
    FILE_TYPE_MAP,
    DOWNLOAD_STATUS,
    MESSAGES,
    SELECTORS,
    DEFAULT_HEADERS,
    INVALID_FILENAME_CHARS,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    EMOJI,
)

__all__ = [
    'settings',
    'Settings',
    'FILE_TYPE_MAP',
    'DOWNLOAD_STATUS',
    'MESSAGES',
    'SELECTORS',
    'DEFAULT_HEADERS',
    'INVALID_FILENAME_CHARS',
    'ALLOWED_EXTENSIONS',
    'MAX_FILE_SIZE',
    'EMOJI',
]
