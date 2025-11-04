"""
Modelo de dados para Curso.

Define a estrutura de dados de um curso da plataforma.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Course:
    """
    Representa um curso na plataforma.

    Attributes:
        title: Título do curso
        url: URL do curso na plataforma
        course_id: ID único do curso (opcional)
        description: Descrição do curso (opcional)
        instructor: Nome do instrutor (opcional)
        total_lessons: Total de aulas no curso
        downloaded_lessons: Número de aulas já baixadas
        created_at: Data de criação do registro
        updated_at: Data de última atualização
    """

    title: str
    url: str
    course_id: Optional[str] = None
    description: Optional[str] = None
    instructor: Optional[str] = None
    total_lessons: int = 0
    downloaded_lessons: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validação após inicialização."""
        if not self.title:
            raise ValueError("Título do curso não pode ser vazio")
        if not self.url:
            raise ValueError("URL do curso não pode ser vazia")

    @property
    def progress_percentage(self) -> float:
        """
        Calcula o percentual de progresso do download.

        Returns:
            float: Percentual de conclusão (0-100)
        """
        if self.total_lessons == 0:
            return 0.0
        return (self.downloaded_lessons / self.total_lessons) * 100

    @property
    def is_complete(self) -> bool:
        """
        Verifica se o curso está completo.

        Returns:
            bool: True se todas as aulas foram baixadas
        """
        return self.downloaded_lessons >= self.total_lessons > 0

    @property
    def missing_lessons(self) -> int:
        """
        Calcula quantas aulas faltam baixar.

        Returns:
            int: Número de aulas pendentes
        """
        return max(0, self.total_lessons - self.downloaded_lessons)

    def to_dict(self) -> dict:
        """
        Converte o curso para dicionário.

        Returns:
            dict: Representação em dicionário
        """
        return {
            'title': self.title,
            'url': self.url,
            'course_id': self.course_id,
            'description': self.description,
            'instructor': self.instructor,
            'total_lessons': self.total_lessons,
            'downloaded_lessons': self.downloaded_lessons,
            'progress_percentage': self.progress_percentage,
            'is_complete': self.is_complete,
            'missing_lessons': self.missing_lessons,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Course':
        """
        Cria uma instância de Course a partir de um dicionário.

        Args:
            data: Dicionário com dados do curso

        Returns:
            Course: Instância do curso
        """
        # Converter strings ISO para datetime
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])

        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})

    def __repr__(self) -> str:
        """Representação string do curso."""
        return (
            f"Course(title='{self.title}', "
            f"progress={self.progress_percentage:.1f}%, "
            f"lessons={self.downloaded_lessons}/{self.total_lessons})"
        )
