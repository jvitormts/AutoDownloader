"""
Utilitários de validação.

Funções para validação de URLs, arquivos, configurações, etc.
"""

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


def is_valid_url(url: str) -> bool:
    """
    Valida se uma string é uma URL válida.

    Args:
        url: String para validar

    Returns:
        bool: True se é uma URL válida

    Examples:
        >>> is_valid_url("https://example.com")
        True
        >>> is_valid_url("not a url")
        False
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def is_valid_email(email: str) -> bool:
    """
    Valida se uma string é um email válido.

    Args:
        email: String para validar

    Returns:
        bool: True se é um email válido

    Examples:
        >>> is_valid_email("user@example.com")
        True
        >>> is_valid_email("invalid.email")
        False
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_valid_path(path: str, must_exist: bool = False) -> bool:
    """
    Valida se um caminho é válido.

    Args:
        path: Caminho para validar
        must_exist: Se True, verifica se o caminho existe

    Returns:
        bool: True se é um caminho válido

    Examples:
        >>> is_valid_path("/home/user/file.txt")
        True
        >>> is_valid_path("/home/user/file.txt", must_exist=True)
        False  # se não existir
    """
    try:
        p = Path(path)
        if must_exist:
            return p.exists()
        return True
    except Exception:
        return False


def is_valid_filename(filename: str) -> bool:
    """
    Valida se um nome de arquivo é válido.

    Args:
        filename: Nome do arquivo

    Returns:
        bool: True se é um nome válido

    Examples:
        >>> is_valid_filename("documento.pdf")
        True
        >>> is_valid_filename("arquivo<>inválido.txt")
        False
    """
    # Caracteres inválidos em nomes de arquivo
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'

    if not filename or re.search(invalid_chars, filename):
        return False

    # Nomes reservados no Windows
    reserved_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]

    name_without_ext = Path(filename).stem.upper()
    if name_without_ext in reserved_names:
        return False

    return True


def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Valida se a extensão do arquivo está na lista permitida.

    Args:
        filename: Nome do arquivo
        allowed_extensions: Lista de extensões permitidas (com ou sem ponto)

    Returns:
        bool: True se a extensão é permitida

    Examples:
        >>> validate_file_extension("doc.pdf", [".pdf", ".doc"])
        True
        >>> validate_file_extension("video.mp4", ["pdf", "doc"])
        False
    """
    ext = Path(filename).suffix.lower()

    # Normalizar extensões (adicionar ponto se não tiver)
    normalized_exts = [
        e if e.startswith('.') else f'.{e}'
        for e in allowed_extensions
    ]

    return ext in normalized_exts


def validate_file_size(file_path: str, max_size_bytes: int) -> bool:
    """
    Valida se o tamanho do arquivo está dentro do limite.

    Args:
        file_path: Caminho do arquivo
        max_size_bytes: Tamanho máximo em bytes

    Returns:
        bool: True se o tamanho é válido

    Examples:
        >>> validate_file_size("/path/to/file.pdf", 10485760)  # 10 MB
        True
    """
    try:
        size = Path(file_path).stat().st_size
        return size <= max_size_bytes
    except Exception:
        return False


def is_valid_telegram_token(token: str) -> bool:
    """
    Valida formato de token do Telegram.

    Args:
        token: Token para validar

    Returns:
        bool: True se o formato é válido

    Examples:
        >>> is_valid_telegram_token("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
        True
        >>> is_valid_telegram_token("invalid")
        False
    """
    # Formato: número:string_alfanumérica
    pattern = r'^\d+:[A-Za-z0-9_-]+$'
    return bool(re.match(pattern, token))


def is_valid_chat_id(chat_id: str) -> bool:
    """
    Valida formato de Chat ID do Telegram.

    Args:
        chat_id: Chat ID para validar

    Returns:
        bool: True se o formato é válido

    Examples:
        >>> is_valid_chat_id("123456789")
        True
        >>> is_valid_chat_id("-100123456789")
        True
        >>> is_valid_chat_id("abc")
        False
    """
    # Chat ID pode ser número positivo ou negativo
    pattern = r'^-?\d+$'
    return bool(re.match(pattern, chat_id))


def validate_download_directory(directory: str, create_if_missing: bool = True) -> bool:
    """
    Valida diretório de download.

    Args:
        directory: Caminho do diretório
        create_if_missing: Se True, cria o diretório se não existir

    Returns:
        bool: True se o diretório é válido e acessível

    Examples:
        >>> validate_download_directory("/downloads", create_if_missing=True)
        True
    """
    try:
        path = Path(directory)

        if not path.exists():
            if create_if_missing:
                path.mkdir(parents=True, exist_ok=True)
            else:
                return False

        # Verificar se é diretório e se tem permissão de escrita
        return path.is_dir() and os.access(path, os.W_OK)

    except Exception:
        return False


def sanitize_and_validate_filename(filename: str, max_length: int = 255) -> Optional[str]:
    """
    Sanitiza e valida nome de arquivo.

    Args:
        filename: Nome original
        max_length: Tamanho máximo

    Returns:
        Optional[str]: Nome sanitizado ou None se inválido

    Examples:
        >>> sanitize_and_validate_filename("Arquivo<>Teste.pdf")
        'Arquivo Teste.pdf'
    """
    from .file_utils import sanitize_filename

    sanitized = sanitize_filename(filename, max_length)

    if is_valid_filename(sanitized):
        return sanitized

    return None


def validate_course_url(url: str, base_url: str) -> bool:
    """
    Valida se uma URL pertence à plataforma de cursos.

    Args:
        url: URL para validar
        base_url: URL base da plataforma

    Returns:
        bool: True se a URL é válida e pertence à plataforma

    Examples:
        >>> validate_course_url(
        ...     "https://example.com/curso/123",
        ...     "https://example.com"
        ... )
        True
    """
    if not is_valid_url(url):
        return False

    return url.startswith(base_url)


import os  # Adicionar import que estava faltando
