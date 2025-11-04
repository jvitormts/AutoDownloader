"""
Serviço de gerenciamento de manifesto de arquivos.

Rastreia e gerencia informações sobre arquivos baixados.
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from config import settings, DOWNLOAD_STATUS


class FileManifestManager:
    """
    Gerencia o arquivo 'files_manifest.json' para rastreamento de downloads.

    Rastreia cada arquivo baixado com:
    - Timestamp de download
    - Nome do arquivo
    - Tamanho (bytes e MB)
    - Tipo de arquivo (pdf, video, txt, etc)
    - Tempo de download
    - Status (success, error, skipped)

    Attributes:
        course_path: Caminho da pasta do curso
        manifest_path: Caminho do arquivo de manifesto
        logger: Logger para registrar ações
        manifest: Dicionário com dados do manifesto
    """

    def __init__(self, course_path: str, logger: Optional[logging.Logger] = None):
        """
        Inicializa o gerenciador do manifesto.

        Args:
            course_path: Caminho da pasta do curso
            logger: Logger para registrar ações
        """
        self.course_path = Path(course_path)
        self.manifest_path = self.course_path / settings.MANIFEST_FILENAME
        self.logger = logger or logging.getLogger(__name__)
        self.manifest: Dict = self._load_manifest()

    def _load_manifest(self) -> Dict:
        """
        Carrega o manifesto do disco ou cria um novo.

        Returns:
            Dict: Dicionário com dados do manifesto
        """
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                self.logger.warning(f"Erro ao carregar manifest: {e}")
                return {}
            except Exception as e:
                self.logger.error(f"Erro inesperado ao carregar manifest: {e}")
                return {}
        return {}

    def _save_manifest(self) -> None:
        """Salva o manifesto no disco."""
        try:
            # Garantir que o diretório existe
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.manifest_path, 'w', encoding='utf-8') as f:
                json.dump(self.manifest, f, indent=2, ensure_ascii=False)

            self.logger.debug(f"Manifesto salvo: {self.manifest_path}")

        except Exception as e:
            self.logger.error(f"Erro ao salvar manifest: {e}")

    def start_lesson(self, lesson_title: str) -> None:
        """
        Marca o início do rastreamento de uma aula.

        Args:
            lesson_title: Título da aula
        """
        if lesson_title not in self.manifest:
            self.manifest[lesson_title] = {
                "timestamp": datetime.now().isoformat(),
                "total_files": 0,
                "files": []
            }
            self.logger.info(f"Iniciando rastreamento: {lesson_title}")

    def add_file(
            self,
            lesson_title: str,
            file_name: str,
            size_bytes: int,
            file_type: str,
            download_time: str = "",
            status: str = DOWNLOAD_STATUS['SUCCESS']
    ) -> None:
        """
        Adiciona um arquivo ao rastreamento de uma aula.

        Args:
            lesson_title: Título da aula
            file_name: Nome do arquivo
            size_bytes: Tamanho do arquivo em bytes
            file_type: Tipo de arquivo (pdf, video, txt, etc)
            download_time: Tempo gasto no download (HH:MM:SS)
            status: Status do download (success, error, skipped)
        """
        if lesson_title not in self.manifest:
            self.start_lesson(lesson_title)

        file_entry = {
            "name": file_name,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "type": file_type,
            "download_time": download_time,
            "status": status,
            "added_at": datetime.now().isoformat()
        }

        self.manifest[lesson_title]["files"].append(file_entry)
        self.manifest[lesson_title]["total_files"] = len(
            self.manifest[lesson_title]["files"]
        )

        self.logger.debug(
            f"Arquivo rastreado: {file_name} ({size_bytes} bytes) - {status}"
        )

    def finish_lesson(self, lesson_title: str) -> None:
        """
        Marca a conclusão do rastreamento de uma aula.

        Args:
            lesson_title: Título da aula
        """
        if lesson_title in self.manifest:
            self.manifest[lesson_title]["completed_at"] = datetime.now().isoformat()
            self._save_manifest()

            total_files = self.manifest[lesson_title]['total_files']
            self.logger.info(
                f"Aula concluída: {lesson_title} ({total_files} arquivos)"
            )

    def get_downloaded_lessons(self) -> List[str]:
        """
        Retorna lista de aulas já rastreadas/baixadas.

        Returns:
            List[str]: Lista de títulos de aulas
        """
        return list(self.manifest.keys())

    def get_lesson_info(self, lesson_title: str) -> Optional[Dict]:
        """
        Retorna informações de uma aula.

        Args:
            lesson_title: Título da aula

        Returns:
            Optional[Dict]: Informações da aula ou None
        """
        return self.manifest.get(lesson_title)

    def get_course_statistics(self) -> Dict:
        """
        Retorna estatísticas gerais do curso.

        Returns:
            Dict: Estatísticas com total de aulas, arquivos e tamanho
        """
        total_lessons = len(self.manifest)
        total_files = sum(
            lesson["total_files"] for lesson in self.manifest.values()
        )
        total_size_bytes = sum(
            file["size_bytes"]
            for lesson in self.manifest.values()
            for file in lesson.get("files", [])
        )

        return {
            "total_lessons": total_lessons,
            "total_files": total_files,
            "total_size_bytes": total_size_bytes,
            "total_size_mb": round(total_size_bytes / (1024 ** 2), 2),
            "total_size_gb": round(total_size_bytes / (1024 ** 3), 2)
        }

    def is_lesson_downloaded(self, lesson_title: str) -> bool:
        """
        Verifica se uma aula já foi baixada.

        Args:
            lesson_title: Título da aula

        Returns:
            bool: True se a aula está no manifesto
        """
        return lesson_title in self.manifest

    def get_failed_files(self, lesson_title: str) -> List[Dict]:
        """
        Retorna lista de arquivos com falha em uma aula.

        Args:
            lesson_title: Título da aula

        Returns:
            List[Dict]: Lista de arquivos com status 'error'
        """
        lesson_info = self.get_lesson_info(lesson_title)
        if not lesson_info:
            return []

        return [
            file for file in lesson_info.get("files", [])
            if file.get("status") == DOWNLOAD_STATUS['ERROR']
        ]

    def clear_manifest(self) -> None:
        """Limpa o manifesto (remove todos os dados)."""
        self.manifest = {}
        self._save_manifest()
        self.logger.info("Manifesto limpo")

    def export_manifest(self, export_path: str) -> bool:
        """
        Exporta o manifesto para um arquivo específico.

        Args:
            export_path: Caminho do arquivo de exportação

        Returns:
            bool: True se exportado com sucesso
        """
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.manifest, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Manifesto exportado para: {export_path}")
            return True

        except Exception as e:
            self.logger.error(f"Erro ao exportar manifesto: {e}")
            return False

    def __repr__(self) -> str:
        """Representação string do gerenciador."""
        stats = self.get_course_statistics()
        return (
            f"FileManifestManager("
            f"lessons={stats['total_lessons']}, "
            f"files={stats['total_files']}, "
            f"size={stats['total_size_gb']:.2f}GB)"
        )
