"""
Utilitários para manipulação de arquivos.

Funções auxiliares para sanitização de nomes, detecção de tipos, etc.
"""

import os
import re
from pathlib import Path
from typing import Optional
from config.constants import FILE_TYPE_MAP, INVALID_FILENAME_CHARS


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitiza nome de arquivo removendo caracteres inválidos.

    Args:
        filename: Nome original do arquivo
        max_length: Tamanho máximo do nome

    Returns:
        str: Nome sanitizado

    Examples:
        >>> sanitize_filename("Aula 01: Introdução/Conceitos")
        'Aula 01 Introdução Conceitos'
        >>> sanitize_filename("Arquivo<>inválido")
        'Arquivo inválido'
    """
    if not filename:
        return "unnamed_file"

    # Remover caracteres inválidos
    sanitized = re.sub(INVALID_FILENAME_CHARS, ' ', filename)

    # Remover espaços múltiplos
    sanitized = re.sub(r'\s+', ' ', sanitized)

    # Remover espaços no início e fim
    sanitized = sanitized.strip()

    # Limitar tamanho
    if len(sanitized) > max_length:
        # Preservar extensão se houver
        name, ext = os.path.splitext(sanitized)
        max_name_length = max_length - len(ext)
        sanitized = name[:max_name_length] + ext

    # Se ficou vazio, usar nome padrão
    if not sanitized:
        sanitized = "unnamed_file"

    return sanitized


def get_file_type(filename: str) -> str:
    """
    Obtém tipo de arquivo baseado na extensão.

    Args:
        filename: Nome do arquivo

    Returns:
        str: Tipo do arquivo (pdf, video, text, etc) ou 'unknown'

    Examples:
        >>> get_file_type("aula.pdf")
        'pdf'
        >>> get_file_type("video.mp4")
        'video'
        >>> get_file_type("documento.xyz")
        'unknown'
    """
    extension = Path(filename).suffix.lower().lstrip('.')

    return FILE_TYPE_MAP.get(extension, 'unknown')


def get_file_size(file_path: str) -> int:
    """
    Obtém tamanho de um arquivo em bytes.

    Args:
        file_path: Caminho do arquivo

    Returns:
        int: Tamanho em bytes, 0 se arquivo não existir

    Examples:
        >>> get_file_size("/path/to/file.pdf")
        1048576
    """
    try:
        return os.path.getsize(file_path)
    except (OSError, FileNotFoundError):
        return 0


def format_file_size(size_bytes: int) -> str:
    """
    Formata tamanho de arquivo em formato legível.

    Args:
        size_bytes: Tamanho em bytes

    Returns:
        str: Tamanho formatado (ex: "1.5 MB", "500 KB")

    Examples:
        >>> format_file_size(1048576)
        '1.00 MB'
        >>> format_file_size(1536)
        '1.50 KB'
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def ensure_directory(directory: str) -> Path:
    """
    Garante que um diretório existe, criando se necessário.

    Args:
        directory: Caminho do diretório

    Returns:
        Path: Path object do diretório

    Examples:
        >>> ensure_directory("/path/to/new/dir")
        PosixPath('/path/to/new/dir')
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_valid_file(file_path: str, min_size: int = 0) -> bool:
    """
    Verifica se um arquivo é válido.

    Args:
        file_path: Caminho do arquivo
        min_size: Tamanho mínimo em bytes

    Returns:
        bool: True se arquivo existe e tem tamanho >= min_size

    Examples:
        >>> is_valid_file("/path/to/file.pdf", min_size=100)
        True
    """
    if not os.path.isfile(file_path):
        return False

    file_size = get_file_size(file_path)
    return file_size >= min_size


def get_unique_filename(directory: str, filename: str) -> str:
    """
    Gera nome de arquivo único adicionando sufixo numérico se necessário.

    Args:
        directory: Diretório onde o arquivo será salvo
        filename: Nome desejado do arquivo

    Returns:
        str: Nome único do arquivo

    Examples:
        >>> get_unique_filename("/downloads", "aula.pdf")
        'aula.pdf'  # ou 'aula_1.pdf' se já existir
    """
    base_path = Path(directory) / filename

    if not base_path.exists():
        return filename

    # Arquivo já existe, adicionar sufixo
    name_stem = base_path.stem
    extension = base_path.suffix
    counter = 1

    while True:
        new_name = f"{name_stem}_{counter}{extension}"
        new_path = Path(directory) / new_name

        if not new_path.exists():
            return new_name

        counter += 1


def clean_empty_directories(root_dir: str) -> int:
    """
    Remove diretórios vazios recursivamente.

    Args:
        root_dir: Diretório raiz para limpeza

    Returns:
        int: Número de diretórios removidos

    Examples:
        >>> clean_empty_directories("/downloads/curso")
        3
    """
    removed_count = 0

    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # Se diretório está vazio (sem arquivos e sem subdiretórios)
        if not filenames and not dirnames:
            try:
                os.rmdir(dirpath)
                removed_count += 1
            except OSError:
                pass  # Ignorar erros de permissão

    return removed_count


def get_extension(filename: str) -> str:
    """
    Obtém extensão de um arquivo.

    Args:
        filename: Nome do arquivo

    Returns:
        str: Extensão sem o ponto (ex: 'pdf', 'mp4')

    Examples:
        >>> get_extension("documento.pdf")
        'pdf'
        >>> get_extension("video.mp4")
        'mp4'
    """
    return Path(filename).suffix.lower().lstrip('.')


def change_extension(filename: str, new_extension: str) -> str:
    """
    Altera extensão de um arquivo.

    Args:
        filename: Nome original do arquivo
        new_extension: Nova extensão (com ou sem ponto)

    Returns:
        str: Nome com nova extensão

    Examples:
        >>> change_extension("documento.txt", "pdf")
        'documento.pdf'
        >>> change_extension("video.avi", ".mp4")
        'video.mp4'
    """
    path = Path(filename)
    new_ext = new_extension if new_extension.startswith('.') else f'.{new_extension}'
    return str(path.with_suffix(new_ext))
