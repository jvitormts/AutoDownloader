"""
Gerenciamento de autenticação e cookies.
"""

import pickle
import os
import logging
from typing import Optional

from config import settings


def save_cookies(driver, filepath: str = None) -> bool:
    """Salva cookies da sessão."""
    filepath = filepath or settings.COOKIES_FILE
    try:
        with open(filepath, 'wb') as f:
            pickle.dump(driver.get_cookies(), f)
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar cookies: {e}")
        return False


def load_cookies(driver, filepath: str = None) -> bool:
    """Carrega cookies salvos."""
    filepath = filepath or settings.COOKIES_FILE
    if not os.path.exists(filepath):
        return False

    try:
        with open(filepath, 'rb') as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        return True
    except Exception as e:
        logging.error(f"Erro ao carregar cookies: {e}")
        return False


def is_logged_in(driver) -> bool:
    """Verifica se está logado."""
    try:
        # Implementar lógica específica da plataforma
        current_url = driver.current_url
        return 'dashboard' in current_url or 'cursos' in current_url
    except:
        return False
