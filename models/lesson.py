"""
Modelo de dados para Aula.

Define a estrutura de dados de uma aula de um curso.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class LessonStatus(Enum):
    """Status possíveis de uma aula."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class LessonFile:
    """
    Representa um arquivo de uma aula.

    Attributes:
        name: Nome do arquivo
        url: URL do arquivo
        file_type: Tipo do arquivo (pdf, video, etc)
        size_bytes: Tamanho em bytes
        downloaded: Se o arquivo foi baixado
    """
    name: str
    url: str
    file_type: str
    size_bytes: int = 0
    downloaded: bool = False

    @property
    def size_mb(self) -> float:
        """Retorna tamanho em MB."""
        return round(self.size_bytes / (1024 * 1024), 2)

    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            'name': self.name,
            'url': self.url,
            'file_type': self.file_type,
            'size_bytes': self.size_bytes,
            'size_mb': self.size_mb,
            'downloaded': self.downloaded,
        }


@dataclass
class Lesson:
    """
    Representa uma aula de um curso.

    Attributes:
        title: Título da aula
        url: URL da aula
        lesson_id: ID único da aula (opcional)
        subtitle: Subtítulo ou descrição da aula
        order: Ordem da aula no curso
        duration: Duração da aula em minutos
        files: Lista de arquivos da aula
        status: Status atual da aula
        created_at: Data de criação
        updated_at: Data de atualização
    """

    title: str
    url: str
    lesson_id: Optional[str] = None
    subtitle: Optional[str] = None
    order: int = 0
    duration: int = 0  # em minutos
    files: List[LessonFile] = field(default_factory=list)
    status: LessonStatus = LessonStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validação após inicialização."""
        if not self.title:
            raise ValueError("Título da aula não pode ser vazio")
        if not self.url:
            raise ValueError("URL da aula não pode ser vazia")

    @property
    def total_files(self) -> int:
        """Retorna total de arquivos."""
        return len(self.files)

    @property
    def downloaded_files(self) -> int:
        """Retorna total de arquivos baixados."""
        return sum(1 for f in self.files if f.downloaded)

    @property
    def total_size_bytes(self) -> int:
        """Retorna tamanho total dos arquivos em bytes."""
        return sum(f.size_bytes for f in self.files)

    @property
    def total_size_mb(self) -> float:
        """Retorna tamanho total em MB."""
        return round(self.total_size_bytes / (1024 * 1024), 2)

    @property
    def is_complete(self) -> bool:
        """Verifica se todos os arquivos foram baixados."""
        return self.total_files > 0 and self.downloaded_files == self.total_files

    @property
    def progress_percentage(self) -> float:
        """Calcula percentual de progresso."""
        if self.total_files == 0:
            return 0.0
        return (self.downloaded_files / self.total_files) * 100

    def add_file(self, file: LessonFile) -> None:
        """
        Adiciona um arquivo à aula.

        Args:
            file: Arquivo a ser adicionado
        """
        self.files.append(file)
        self.updated_at = datetime.now()

    def mark_file_downloaded(self, file_name: str) -> bool:
        """
        Marca um arquivo como baixado.

        Args:
            file_name: Nome do arquivo

        Returns:
            bool: True se encontrou e marcou o arquivo
        """
        for file in self.files:
            if file.name == file_name:
                file.downloaded = True
                self.updated_at = datetime.now()
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            'title': self.title,
            'url': self.url,
            'lesson_id': self.lesson_id,
            'subtitle': self.subtitle,
            'order': self.order,
            'duration': self.duration,
            'files': [f.to_dict() for f in self.files],
            'status': self.status.value,
            'total_files': self.total_files,
            'downloaded_files': self.downloaded_files,
            'total_size_mb': self.total_size_mb,
            'is_complete': self.is_complete,
            'progress_percentage': self.progress_percentage,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Lesson':
        """
        Cria instância a partir de dicionário.

        Args:
            data: Dicionário com dados da aula

        Returns:
            Lesson: Instância da aula
        """
        # Converter strings para datetime
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])

        # Converter status
        if isinstance(data.get('status'), str):
            data['status'] = LessonStatus(data['status'])

        # Converter arquivos
        if 'files' in data:
            data['files'] = [
                LessonFile(**f) if isinstance(f, dict) else f
                for f in data['files']
            ]

        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def __repr__(self) -> str:
        """Representação string da aula."""
        return (
            f"Lesson(title='{self.title}', "
            f"status={self.status.value}, "
            f"files={self.downloaded_files}/{self.total_files})"
        )
