"""
Pacote de modelos de dados do AutoDownloader.

Exporta os modelos Course e Lesson.
"""

from .course import Course
from .lesson import Lesson, LessonFile, LessonStatus

__all__ = [
    'Course',
    'Lesson',
    'LessonFile',
    'LessonStatus',
]
