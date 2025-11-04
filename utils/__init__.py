"""
Pacote de utilitários do AutoDownloader.

Exporta funções auxiliares para manipulação de arquivos, tempo e validações.
"""

from .file_utils import (
    sanitize_filename,
    get_file_type,
    get_file_size,
    format_file_size,
    ensure_directory,
    is_valid_file,
    get_unique_filename,
    clean_empty_directories,
    get_extension,
    change_extension,
)

from .time_utils import (
    format_duration,
    parse_duration,
    calculate_download_time,
    estimate_remaining_time,
    format_timestamp,
    parse_timestamp,
    get_elapsed_time,
    seconds_to_minutes,
    minutes_to_seconds,
    format_date,
    is_recent,
    get_download_speed,
)

from .validators import (
    is_valid_url,
    is_valid_email,
    is_valid_path,
    is_valid_filename,
    validate_file_extension,
    validate_file_size,
    is_valid_telegram_token,
    is_valid_chat_id,
    validate_download_directory,
    sanitize_and_validate_filename,
    validate_course_url,
)

__all__ = [
    # file_utils
    'sanitize_filename',
    'get_file_type',
    'get_file_size',
    'format_file_size',
    'ensure_directory',
    'is_valid_file',
    'get_unique_filename',
    'clean_empty_directories',
    'get_extension',
    'change_extension',
    # time_utils
    'format_duration',
    'parse_duration',
    'calculate_download_time',
    'estimate_remaining_time',
    'format_timestamp',
    'parse_timestamp',
    'get_elapsed_time',
    'seconds_to_minutes',
    'minutes_to_seconds',
    'format_date',
    'is_recent',
    'get_download_speed',
    # validators
    'is_valid_url',
    'is_valid_email',
    'is_valid_path',
    'is_valid_filename',
    'validate_file_extension',
    'validate_file_size',
    'is_valid_telegram_token',
    'is_valid_chat_id',
    'validate_download_directory',
    'sanitize_and_validate_filename',
    'validate_course_url',
]
