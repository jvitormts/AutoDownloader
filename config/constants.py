"""
Constantes do sistema AutoDownloader.

Este módulo contém todas as constantes utilizadas no sistema,
incluindo mapeamentos de tipos de arquivo, mensagens padrão, etc.
"""

from typing import Dict

# Mapeamento de extensões para tipos de arquivo
FILE_TYPE_MAP: Dict[str, str] = {
    'pdf': 'pdf',
    'mp4': 'video',
    'mkv': 'video',
    'avi': 'video',
    'webm': 'video',
    'txt': 'text',
    'md': 'text',
    'doc': 'document',
    'docx': 'document',
    'png': 'image',
    'jpg': 'image',
    'jpeg': 'image',
    'gif': 'image',
    'svg': 'image',
    'zip': 'archive',
    'rar': 'archive',
    '7z': 'archive',
    'tar': 'archive',
    'gz': 'archive',
}

# Status de download
DOWNLOAD_STATUS = {
    'SUCCESS': 'success',
    'ERROR': 'error',
    'SKIPPED': 'skipped',
    'IN_PROGRESS': 'in_progress',
}

# Mensagens padrão
MESSAGES = {
    'LOGIN_SUCCESS': '✅ Login realizado com sucesso!',
    'LOGIN_REQUIRED': '⚠️ É necessário fazer login manualmente',
    'DOWNLOAD_STARTED': '🚀 Iniciando download do curso: {}',
    'DOWNLOAD_COMPLETED': '✅ Download concluído: {}',
    'DOWNLOAD_ERROR': '❌ Erro no download: {}',
    'COURSE_NOT_FOUND': '⚠️ Curso não encontrado: {}',
    'NO_LESSONS_FOUND': '⚠️ Nenhuma aula encontrada',
    'INCOMPLETE_COURSE': '📊 Curso incompleto: {} ({} de {} aulas)',
}

# Seletores CSS/XPath (podem variar conforme a plataforma)
SELECTORS = {
    'login_button': "button[type='submit']",
    'course_card': ".course-card",
    'lesson_item': ".lesson-item",
    'video_player': "video",
    'pdf_link': "a[href$='.pdf']",
}

# Headers HTTP padrão
DEFAULT_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Caracteres inválidos para nomes de arquivo (Windows/Linux)
INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

# Extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {
    'video': ['.mp4', '.mkv', '.avi', '.webm'],
    'document': ['.pdf', '.doc', '.docx', '.txt', '.md'],
    'image': ['.png', '.jpg', '.jpeg', '.gif', '.svg'],
    'archive': ['.zip', '.rar', '.7z', '.tar', '.gz'],
}

# Limites de tamanho de arquivo (em bytes)
MAX_FILE_SIZE = {
    'video': 5 * 1024 * 1024 * 1024,  # 5 GB
    'document': 500 * 1024 * 1024,     # 500 MB
    'image': 50 * 1024 * 1024,         # 50 MB
    'archive': 2 * 1024 * 1024 * 1024, # 2 GB
}

# Emojis para notificações
EMOJI = {
    'success': '✅',
    'error': '❌',
    'warning': '⚠️',
    'info': 'ℹ️',
    'download': '⬇️',
    'upload': '⬆️',
    'rocket': '🚀',
    'chart': '📊',
    'book': '📚',
    'video': '🎥',
    'document': '📄',
}
