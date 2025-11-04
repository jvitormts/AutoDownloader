"""
Módulo principal de download de cursos.

Contém a lógica de scraping, navegação e download de materiais.
"""

import os
import time
import logging
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException
)

from config import settings, MESSAGES
from models import Course, Lesson, LessonFile
from services import FileManifestManager, FileDownloader
from notifications import TelegramNotifier, setup_course_logger
from utils import sanitize_filename, ensure_directory


class CourseDownloader:
    """
    Gerencia o processo de download de cursos.

    Attributes:
        driver: WebDriver do Selenium
        download_dir: Diretório raiz para downloads
        telegram: Notificador do Telegram
        logger: Logger da aplicação
    """

    def __init__(
            self,
            driver: webdriver.Chrome,
            download_dir: str,
            telegram: Optional[TelegramNotifier] = None,
            logger: Optional[logging.Logger] = None
    ):
        """
        Inicializa o downloader.

        Args:
            driver: WebDriver do Selenium
            download_dir: Diretório para salvar downloads
            telegram: Notificador do Telegram (opcional)
            logger: Logger (opcional)
        """
        self.driver = driver
        self.download_dir = Path(download_dir)
        self.telegram = telegram
        self.logger = logger or logging.getLogger(__name__)
        self.file_downloader = FileDownloader(logger)

    def get_available_courses(self) -> List[Dict[str, str]]:
        """
        Obtém lista de cursos disponíveis na plataforma.

        Returns:
            List[Dict]: Lista de dicionários com 'title' e 'url'
        """
        self.logger.info("Buscando cursos disponíveis...")
        print("\n🔍 Navegando para 'Meus Cursos'...")

        self.driver.get(settings.MY_COURSES_URL)

        try:
            # Aguardar carregamento dos cursos
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "section[id^='card'] a.sc-cHGsZl")
                )
            )
            time.sleep(3)

            course_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "section[id^='card']"
            )
            courses = []

            for course_elem in course_elements:
                try:
                    link_elem = course_elem.find_element(
                        By.CSS_SELECTOR, "a.sc-cHGsZl"
                    )
                    title_elem = course_elem.find_element(
                        By.CSS_SELECTOR, "h1.sc-ksYbfQ"
                    )

                    course_href = link_elem.get_attribute('href')
                    course_title = title_elem.text

                    if course_href and course_title:
                        courses.append({
                            "title": course_title,
                            "url": course_href
                        })

                except (NoSuchElementException, StaleElementReferenceException):
                    self.logger.warning("Elemento de curso não encontrado")
                    continue

            self.logger.info(f"Encontrados {len(courses)} cursos")
            print(f"✅ Encontrados {len(courses)} cursos")

            return courses

        except TimeoutException:
            self.logger.error("Timeout ao carregar lista de cursos")
            print("❌ Erro: Tempo esgotado ao carregar cursos")
            return []

    def get_course_lessons(self, course_url: str) -> List[Dict[str, str]]:
        """
        Obtém lista de aulas de um curso.

        Args:
            course_url: URL do curso

        Returns:
            List[Dict]: Lista de dicionários com dados das aulas
        """
        self.logger.info(f"Buscando aulas do curso: {course_url}")
        print(f"\n📚 Carregando aulas do curso...")

        self.driver.get(course_url)

        try:
            # Aguardar carregamento das aulas
            WebDriverWait(self.driver, 40).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div.LessonList-item a.Collapse-header")
                )
            )
            time.sleep(3)

            lesson_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "div.LessonList-item"
            )
            lessons = []

            for lesson_elem in lesson_elements:
                try:
                    # Pular aulas desabilitadas
                    if "isDisabled" in lesson_elem.get_attribute("class"):
                        continue

                    link_elem = lesson_elem.find_element(
                        By.CSS_SELECTOR, "a.Collapse-header"
                    )
                    title_elem = lesson_elem.find_element(
                        By.CSS_SELECTOR, "h2.SectionTitle"
                    )

                    lesson_title = title_elem.text
                    lesson_subtitle = ""

                    # Tentar obter subtítulo
                    try:
                        subtitle_elem = lesson_elem.find_element(
                            By.CSS_SELECTOR, "p.sc-gZMcBi"
                        )
                        lesson_subtitle = subtitle_elem.text
                    except NoSuchElementException:
                        pass

                    lesson_href = link_elem.get_attribute('href')

                    if lesson_href and lesson_title:
                        lessons.append({
                            "title": lesson_title,
                            "subtitle": lesson_subtitle,
                            "url": lesson_href
                        })

                except (NoSuchElementException, StaleElementReferenceException):
                    self.logger.warning("Elemento de aula não encontrado")
                    continue

            self.logger.info(f"Encontradas {len(lessons)} aulas")
            print(f"✅ Encontradas {len(lessons)} aulas disponíveis")

            return lessons

        except TimeoutException:
            self.logger.error("Timeout ao carregar lista de aulas")
            print("❌ Erro: Tempo esgotado ao carregar aulas")
            return []

    def download_course(self, course: Dict[str, str]) -> bool:
        """
        Faz download de um curso completo.

        Args:
            course: Dicionário com dados do curso

        Returns:
            bool: True se sucesso
        """
        course_title = course['title']
        course_url = course['url']

        self.logger.info(f"Iniciando download do curso: {course_title}")
        print(f"\n{'=' * 70}")
        print(f"📚 CURSO: {course_title}")
        print(f"{'=' * 70}\n")

        # Criar diretório do curso
        sanitized_title = sanitize_filename(course_title)
        course_path = self.download_dir / sanitized_title
        ensure_directory(str(course_path))

        # Configurar logger do curso
        course_logger = setup_course_logger(
            course_title,
            str(self.download_dir),
            self.telegram
        )

        # Inicializar gerenciador de manifesto
        manifest = FileManifestManager(str(course_path), course_logger)

        # Obter aulas
        lessons = self.get_course_lessons(course_url)

        if not lessons:
            self.logger.warning(f"Nenhuma aula encontrada para: {course_title}")
            return False

        # Notificar início
        if self.telegram:
            self.telegram.notify_course_start(
                course_title, 1, 1, len(lessons)
            )

        # Download de cada aula
        start_time = datetime.now()

        for i, lesson_data in enumerate(lessons, 1):
            lesson_title = lesson_data['title']

            print(f"\n📖 Aula {i}/{len(lessons)}: {lesson_title}")

            # Verificar se já foi baixada
            if manifest.is_lesson_downloaded(lesson_title):
                print("   ✓ Aula já baixada (pulando)")
                course_logger.info(f"Aula já baixada: {lesson_title}")
                continue

            # Iniciar rastreamento da aula
            manifest.start_lesson(lesson_title)

            # Download dos materiais da aula
            success = self.download_lesson_materials(
                lesson_data,
                course_path,
                manifest,
                course_logger
            )

            if success:
                manifest.finish_lesson(lesson_title)
                print(f"   ✅ Aula concluída")
            else:
                print(f"   ⚠️  Aula com erros")

            # Notificar progresso
            if self.telegram:
                self.telegram.notify_lesson_progress(i, len(lessons), lesson_title)

        # Calcular duração
        duration = datetime.now() - start_time
        duration_str = str(duration).split('.')[0]

        # Notificar conclusão
        if self.telegram:
            self.telegram.notify_course_complete(
                course_title, 1, 1, duration_str
            )

        print(f"\n{'=' * 70}")
        print(f"✅ CURSO CONCLUÍDO: {course_title}")
        print(f"⏱️  Tempo total: {duration_str}")
        print(f"{'=' * 70}\n")

        return True

    def download_lesson_materials(
            self,
            lesson_data: Dict[str, str],
            course_path: Path,
            manifest: FileManifestManager,
            logger: logging.Logger
    ) -> bool:
        """
        Faz download dos materiais de uma aula.

        Args:
            lesson_data: Dados da aula
            course_path: Caminho do curso
            manifest: Gerenciador de manifesto
            logger: Logger

        Returns:
            bool: True se sucesso
        """
        lesson_title = lesson_data['title']
        lesson_url = lesson_data['url']
        lesson_subtitle = lesson_data.get('subtitle', '')

        # Criar diretório da aula
        sanitized_lesson = sanitize_filename(lesson_title)
        lesson_path = course_path / sanitized_lesson
        ensure_directory(str(lesson_path))

        # Navegar para a aula
        logger.info(f"Navegando para aula: {lesson_url}")
        self.driver.get(lesson_url)
        time.sleep(3)

        # Salvar assuntos da aula
        if lesson_subtitle:
            self._save_lesson_subjects(
                lesson_path,
                lesson_subtitle,
                manifest,
                lesson_title,
                logger
            )

        # Download de PDFs
        self._download_pdfs(
            lesson_path,
            manifest,
            lesson_title,
            logger
        )

        # Download de vídeos (implementar conforme necessário)
        # self._download_videos(...)

        return True

    def _save_lesson_subjects(
            self,
            lesson_path: Path,
            subtitle: str,
            manifest: FileManifestManager,
            lesson_title: str,
            logger: logging.Logger
    ) -> None:
        """Salva os assuntos da aula em arquivo texto."""
        subjects_file = lesson_path / "Assuntos_dessa_aula.txt"

        if subjects_file.exists():
            logger.info("Arquivo de assuntos já existe")
            return

        try:
            subjects_file.write_text(subtitle, encoding='utf-8')
            logger.info("Arquivo de assuntos criado")

            manifest.add_file(
                lesson_title=lesson_title,
                file_name="Assuntos_dessa_aula.txt",
                size_bytes=len(subtitle.encode('utf-8')),
                file_type="text",
                download_time="00:00:00",
                status="success"
            )

        except Exception as e:
            logger.error(f"Erro ao salvar assuntos: {e}")

    def _download_pdfs(
            self,
            lesson_path: Path,
            manifest: FileManifestManager,
            lesson_title: str,
            logger: logging.Logger
    ) -> None:
        """Faz download dos PDFs da aula."""
        print("   📄 Procurando PDFs...")

        try:
            pdf_links = self.driver.find_elements(
                By.XPATH,
                "//a[contains(@class, 'LessonButton') and .//i[contains(@class, 'icon-file')]]"
            )

            if not pdf_links:
                logger.info("Nenhum PDF encontrado")
                return

            for i, pdf_link in enumerate(pdf_links, 1):
                try:
                    pdf_url = pdf_link.get_attribute('href')
                    pdf_name = f"livro_eletronico_{i}.pdf"
                    pdf_path = lesson_path / pdf_name

                    if pdf_path.exists():
                        logger.info(f"PDF já existe: {pdf_name}")
                        continue

                    print(f"      ⬇️  Baixando PDF {i}...")

                    success = self.file_downloader.download(
                        pdf_url,
                        str(pdf_path),
                        referer=self.driver.current_url
                    )

                    if success:
                        size = os.path.getsize(pdf_path)
                        manifest.add_file(
                            lesson_title=lesson_title,
                            file_name=pdf_name,
                            size_bytes=size,
                            file_type="pdf",
                            download_time="00:00:05",
                            status="success"
                        )
                        print(f"      ✅ PDF {i} baixado")

                except Exception as e:
                    logger.error(f"Erro ao baixar PDF {i}: {e}")

        except Exception as e:
            logger.error(f"Erro ao buscar PDFs: {e}")

    def close(self):
        """Fecha recursos."""
        self.file_downloader.close()
        if self.driver:
            self.driver.quit()
