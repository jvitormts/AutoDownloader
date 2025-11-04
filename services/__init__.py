"""Pacote de serviços do AutoDownloader."""

from .manifest_service import FileManifestManager
from .file_service import FileDownloader

__all__ = ['FileManifestManager', 'FileDownloader']
