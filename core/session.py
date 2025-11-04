"""
Gerenciamento de sessão do navegador.
"""

import time
import threading
import logging
from typing import Optional

from config import settings


class SessionKeepAlive:
    """Mantém sessão ativa com heartbeat."""

    def __init__(self, driver, logger: Optional[logging.Logger] = None):
        self.driver = driver
        self.logger = logger or logging.getLogger(__name__)
        self.running = False
        self.thread = None

    def _heartbeat(self):
        """Thread de heartbeat."""
        while self.running:
            try:
                self.driver.current_url
                self.logger.debug("Heartbeat: sessão ativa")
            except Exception as e:
                self.logger.warning(f"Heartbeat falhou: {e}")

            time.sleep(settings.HEARTBEAT_INTERVAL)

    def start(self):
        """Inicia heartbeat."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._heartbeat, daemon=True)
            self.thread.start()
            self.logger.info("SessionKeepAlive iniciado")

    def stop(self):
        """Para heartbeat."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("SessionKeepAlive parado")
