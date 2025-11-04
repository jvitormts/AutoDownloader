"""
Utilitários para manipulação de tempo e duração.

Funções auxiliares para formatação de tempo, cálculo de duração, etc.
"""

from datetime import datetime, timedelta
from typing import Union


def format_duration(seconds: Union[int, float]) -> str:
    """
    Formata duração em segundos para formato HH:MM:SS.

    Args:
        seconds: Duração em segundos

    Returns:
        str: Duração formatada

    Examples:
        >>> format_duration(3665)
        '01:01:05'
        >>> format_duration(125.5)
        '00:02:05'
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_duration(duration_str: str) -> int:
    """
    Converte string de duração (HH:MM:SS) para segundos.

    Args:
        duration_str: String no formato HH:MM:SS ou MM:SS

    Returns:
        int: Duração em segundos

    Examples:
        >>> parse_duration("01:30:00")
        5400
        >>> parse_duration("05:30")
        330
    """
    parts = duration_str.split(':')

    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
    elif len(parts) == 2:
        hours = 0
        minutes, seconds = map(int, parts)
    else:
        return 0

    return hours * 3600 + minutes * 60 + seconds


def calculate_download_time(file_size_bytes: int, duration_seconds: float) -> str:
    """
    Calcula e formata tempo de download.

    Args:
        file_size_bytes: Tamanho do arquivo em bytes
        duration_seconds: Duração do download em segundos

    Returns:
        str: Tempo formatado (HH:MM:SS)

    Examples:
        >>> calculate_download_time(1048576, 10.5)
        '00:00:10'
    """
    return format_duration(duration_seconds)


def estimate_remaining_time(
        total_items: int,
        completed_items: int,
        elapsed_seconds: float
) -> str:
    """
    Estima tempo restante baseado no progresso atual.

    Args:
        total_items: Total de itens
        completed_items: Itens completados
        elapsed_seconds: Tempo decorrido em segundos

    Returns:
        str: Tempo estimado restante formatado

    Examples:
        >>> estimate_remaining_time(100, 25, 300)
        '00:15:00'
    """
    if completed_items == 0:
        return "Calculando..."

    avg_time_per_item = elapsed_seconds / completed_items
    remaining_items = total_items - completed_items
    estimated_seconds = avg_time_per_item * remaining_items

    return format_duration(estimated_seconds)


def format_timestamp(dt: datetime = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Formata timestamp para string.

    Args:
        dt: Datetime object (usa datetime.now() se None)
        fmt: Formato de saída

    Returns:
        str: Timestamp formatado

    Examples:
        >>> format_timestamp()
        '2024-01-15 14:30:00'
    """
    if dt is None:
        dt = datetime.now()

    return dt.strftime(fmt)


def parse_timestamp(timestamp_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    Converte string para datetime.

    Args:
        timestamp_str: String com timestamp
        fmt: Formato da string

    Returns:
        datetime: Objeto datetime

    Examples:
        >>> parse_timestamp("2024-01-15 14:30:00")
        datetime(2024, 1, 15, 14, 30, 0)
    """
    return datetime.strptime(timestamp_str, fmt)


def get_elapsed_time(start_time: datetime) -> str:
    """
    Calcula tempo decorrido desde um momento inicial.

    Args:
        start_time: Momento inicial

    Returns:
        str: Tempo decorrido formatado

    Examples:
        >>> start = datetime.now() - timedelta(seconds=3665)
        >>> get_elapsed_time(start)
        '01:01:05'
    """
    elapsed = datetime.now() - start_time
    return format_duration(elapsed.total_seconds())


def seconds_to_minutes(seconds: Union[int, float]) -> float:
    """
    Converte segundos para minutos.

    Args:
        seconds: Tempo em segundos

    Returns:
        float: Tempo em minutos

    Examples:
        >>> seconds_to_minutes(120)
        2.0
        >>> seconds_to_minutes(90)
        1.5
    """
    return seconds / 60.0


def minutes_to_seconds(minutes: Union[int, float]) -> int:
    """
    Converte minutos para segundos.

    Args:
        minutes: Tempo em minutos

    Returns:
        int: Tempo em segundos

    Examples:
        >>> minutes_to_seconds(2)
        120
        >>> minutes_to_seconds(1.5)
        90
    """
    return int(minutes * 60)


def format_date(dt: datetime = None, fmt: str = "%Y-%m-%d") -> str:
    """
    Formata data sem hora.

    Args:
        dt: Datetime object (usa datetime.now() se None)
        fmt: Formato de saída

    Returns:
        str: Data formatada

    Examples:
        >>> format_date()
        '2024-01-15'
    """
    if dt is None:
        dt = datetime.now()

    return dt.strftime(fmt)


def is_recent(dt: datetime, hours: int = 24) -> bool:
    """
    Verifica se uma data é recente.

    Args:
        dt: Datetime para verificar
        hours: Número de horas para considerar recente

    Returns:
        bool: True se a data está dentro do período

    Examples:
        >>> recent_date = datetime.now() - timedelta(hours=12)
        >>> is_recent(recent_date, hours=24)
        True
    """
    now = datetime.now()
    time_diff = now - dt
    return time_diff <= timedelta(hours=hours)


def get_download_speed(bytes_downloaded: int, seconds_elapsed: float) -> str:
    """
    Calcula velocidade de download.

    Args:
        bytes_downloaded: Bytes baixados
        seconds_elapsed: Tempo decorrido em segundos

    Returns:
        str: Velocidade formatada (ex: "1.5 MB/s")

    Examples:
        >>> get_download_speed(1048576, 1.0)
        '1.00 MB/s'
    """
    if seconds_elapsed == 0:
        return "0 B/s"

    bytes_per_second = bytes_downloaded / seconds_elapsed

    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if bytes_per_second < 1024.0:
            return f"{bytes_per_second:.2f} {unit}"
        bytes_per_second /= 1024.0

    return f"{bytes_per_second:.2f} TB/s"
