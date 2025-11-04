"""
Configurações do AutoDownloader.

Este módulo centraliza todas as configurações do sistema,
incluindo URLs, timeouts, e configurações de ambiente.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()


class Settings:
    """Classe de configurações do sistema."""

    # Diretórios
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DEFAULT_DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "./downloads")

    # URLs da Plataforma
    BASE_URL: str = "https://www.estrategiaconcursos.com.br"
    MY_COURSES_URL: str = f"{BASE_URL}/app/dashboard/cursos"

    # Arquivos de Sistema
    COOKIES_FILE: str = "estrategia_session_cookies.pkl"
    MANIFEST_FILENAME: str = "files_manifest.json"
    METADATA_FILENAME: str = "course_metadata.json"

    # Timeouts e Intervalos
    HEARTBEAT_INTERVAL: int = 300  # 5 minutos
    DEFAULT_TIMEOUT: int = 60  # segundos
    MIN_NOTIFICATION_INTERVAL: int = 1  # segundo entre notificações

    # Selenium
    PAGE_LOAD_TIMEOUT: int = 30
    IMPLICIT_WAIT: int = 10
    EXPLICIT_WAIT: int = 20

    # Download
    CHUNK_SIZE: int = 8192  # bytes
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5  # segundos

    # Telegram
    TELEGRAM_ENABLED: bool = os.getenv("TELEGRAM_ENABLED", "False").lower() == "true"
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    # User Agent
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @classmethod
    def validate(cls) -> bool:
        """
        Valida as configurações necessárias.

        Returns:
            bool: True se todas as configurações obrigatórias estão presentes

        Raises:
            ValueError: Se alguma configuração obrigatória estiver faltando
        """
        if cls.TELEGRAM_ENABLED:
            if not cls.TELEGRAM_BOT_TOKEN:
                raise ValueError(
                    "TELEGRAM_BOT_TOKEN é obrigatório quando TELEGRAM_ENABLED=True"
                )
            if not cls.TELEGRAM_CHAT_ID:
                raise ValueError(
                    "TELEGRAM_CHAT_ID é obrigatório quando TELEGRAM_ENABLED=True"
                )

        return True

    @classmethod
    def get_download_dir(cls) -> Path:
        """
        Retorna o diretório de download como Path object.

        Returns:
            Path: Caminho do diretório de download
        """
        download_path = Path(cls.DEFAULT_DOWNLOAD_DIR)
        download_path.mkdir(parents=True, exist_ok=True)
        return download_path


# Instância global de configurações
settings = Settings()
