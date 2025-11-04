"""Pacote core do AutoDownloader."""

from .session import SessionKeepAlive
from .authentication import save_cookies, load_cookies, is_logged_in
from .downloader import CourseDownloader

__all__ = [
    'SessionKeepAlive',
    'save_cookies',
    'load_cookies',
    'is_logged_in',
    'CourseDownloader',
]
