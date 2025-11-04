"""
Detector de aulas e cursos pendentes.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Tuple

from config import settings


class PendingLessonsDetector:
    """Detecta aulas pendentes de download."""

    def __init__(self, download_dir: str, logger: logging.Logger = None):
        self.download_dir = Path(download_dir)
        self.logger = logger or logging.getLogger(__name__)

    def scan_downloaded_courses(self) -> Dict[str, Path]:
        """
        Escaneia cursos já baixados.

        Returns:
            Dict: Mapeamento nome -> caminho
        """
        courses = {}
        if not self.download_dir.exists():
            return courses

        for item in self.download_dir.iterdir():
            if item.is_dir():
                courses[item.name] = item

        return courses

    def get_course_downloaded_lessons(self, course_path: Path) -> List[str]:
        """
        Retorna lista de aulas baixadas de um curso.

        Args:
            course_path: Caminho do curso

        Returns:
            List[str]: Lista de nomes de aulas
        """
        lessons = []
        if not course_path.exists():
            return lessons

        for item in course_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                lessons.append(item.name)

        return lessons
