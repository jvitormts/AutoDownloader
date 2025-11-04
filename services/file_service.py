"""
Serviço de operações com arquivos.
Gerencia download e manipulação de arquivos.
"""

import os
import requests
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

from config import settings, DEFAULT_HEADERS
from utils import get_file_type, get_file_size, sanitize_filename


class FileDownloader:
    """Gerencia download de arquivos."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def download(
        self,
        url: str,
        file_path: str,
        referer: Optional[str] = None,
        timeout: int = None
    ) -> bool:
        """
        Faz download de um arquivo.

        Args:
            url: URL do arquivo
            file_path: Caminho de destino
            referer: URL de referência (opcional)
            timeout: Timeout em segundos

        Returns:
            bool: True se sucesso
        """
        headers = {}
        if referer:
            headers['Referer'] = referer

        timeout = timeout or settings.DEFAULT_TIMEOUT

        try:
            with self.session.get(url, stream=True, timeout=timeout, headers=headers) as response:
                response.raise_for_status()
                total = response.headers.get('content-length')
                total = int(total) if total else None
                downloaded = 0

                Path(file_path).parent.mkdir(parents=True, exist_ok=True)

                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=settings.CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            if total:
                                downloaded += len(chunk)
                                progress = 100 * downloaded / total
                                print(f"\r  Baixando: {os.path.basename(file_path)} [{progress:.2f}%]", end="")

                print()
                self.logger.info(f"Download concluído: {file_path}")
                return True

        except Exception as e:
            self.logger.error(f"Erro ao baixar {url}: {e}")
            return False

    def close(self):
        """Fecha a sessão."""
        self.session.close()
