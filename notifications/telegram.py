"""
Módulo de notificações via Telegram.

Gerencia envio de notificações para o Telegram durante o processo de download.
"""

import time
import logging
from datetime import datetime
from typing import Optional
import requests

from config import settings, EMOJI


class TelegramNotifier:
    """
    Gerencia envio de notificações para o Telegram.

    Attributes:
        bot_token: Token do bot do Telegram
        chat_id: ID do chat para enviar mensagens
        enabled: Se True, envia notificações
        api_url: URL da API do Telegram
        last_send_time: Timestamp do último envio
        min_interval: Intervalo mínimo entre mensagens
    """

    def __init__(
            self,
            bot_token: Optional[str] = None,
            chat_id: Optional[str] = None,
            enabled: bool = True
    ):
        """
        Inicializa o notificador do Telegram.

        Args:
            bot_token: Token do bot (usa settings se None)
            chat_id: ID do chat (usa settings se None)
            enabled: Se True, envia notificações
        """
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.enabled = enabled and settings.TELEGRAM_ENABLED
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.last_send_time = 0
        self.min_interval = settings.MIN_NOTIFICATION_INTERVAL
        self.logger = logging.getLogger(__name__)

        if self.enabled:
            self._test_connection()

    def _test_connection(self) -> None:
        """Testa conexão com o Telegram na inicialização."""
        try:
            self.send(
                f"{EMOJI['rocket']} Bot conectado com sucesso!\n\n"
                "Pronto para enviar notificações de download."
            )
            self.logger.info("Telegram Bot conectado com sucesso")
        except Exception as e:
            self.logger.warning(f"Erro ao conectar com Telegram: {e}")
            self.logger.warning("As notificações do Telegram estarão desabilitadas")
            self.enabled = False

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Envia mensagem para o Telegram.

        Args:
            message: Mensagem a enviar
            parse_mode: Modo de formatação ('HTML' ou 'Markdown')

        Returns:
            bool: True se enviado com sucesso
        """
        if not self.enabled:
            return False

        # Rate limiting - evita flood de mensagens
        current_time = time.time()
        time_since_last = current_time - self.last_send_time

        if time_since_last < self.min_interval:
            time.sleep(self.min_interval - time_since_last)

        try:
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(self.api_url, json=data, timeout=10)
            response.raise_for_status()
            self.last_send_time = time.time()
            return True

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro ao enviar mensagem Telegram: {e}")
            return False

    def notify_start(self, total_courses: int) -> None:
        """
        Notifica início do processo.

        Args:
            total_courses: Número total de cursos
        """
        message = (
            f"{EMOJI['rocket']} <b>DOWNLOAD INICIADO</b>\n\n"
            f"{EMOJI['book']} Cursos selecionados: {total_courses}\n"
            f"⏰ Início: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        self.send(message)

    def notify_course_start(
            self,
            course_title: str,
            course_num: int,
            total_courses: int,
            total_lessons: int
    ) -> None:
        """
        Notifica início de um curso.

        Args:
            course_title: Título do curso
            course_num: Número do curso atual
            total_courses: Total de cursos
            total_lessons: Total de aulas no curso
        """
        message = (
            f"{EMOJI['book']} <b>CURSO INICIADO [{course_num}/{total_courses}]</b>\n\n"
            f"<b>{course_title}</b>\n\n"
            f"📖 Total de aulas: {total_lessons}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(message)

    def notify_course_complete(
            self,
            course_title: str,
            course_num: int,
            total_courses: int,
            duration: str
    ) -> None:
        """
        Notifica conclusão de um curso.

        Args:
            course_title: Título do curso
            course_num: Número do curso atual
            total_courses: Total de cursos
            duration: Duração formatada
        """
        message = (
            f"{EMOJI['success']} <b>CURSO CONCLUÍDO [{course_num}/{total_courses}]</b>\n\n"
            f"<b>{course_title}</b>\n\n"
            f"⏱️ Tempo total: {duration}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send(message)

    def notify_lesson_progress(
            self,
            lesson_num: int,
            total_lessons: int,
            lesson_title: str
    ) -> None:
        """
        Notifica progresso de aula (apenas múltiplos de 5).

        Args:
            lesson_num: Número da aula atual
            total_lessons: Total de aulas
            lesson_title: Título da aula
        """
        if lesson_num % 5 == 0 or lesson_num == total_lessons:
            message = (
                f"📖 <b>PROGRESSO [{lesson_num}/{total_lessons}]</b>\n\n"
                f"{lesson_title}"
            )
            self.send(message)

    def notify_session_expired(self) -> None:
        """Notifica que a sessão expirou."""
        message = (
            f"{EMOJI['warning']} <b>AVISO DE SESSÃO</b>\n\n"
            "Sessão expirada detectada.\n"
            "Tentando restaurar automaticamente..."
        )
        self.send(message)

    def notify_session_restored(self) -> None:
        """Notifica que a sessão foi restaurada."""
        message = f"{EMOJI['success']} Sessão restaurada com sucesso!"
        self.send(message)

    def notify_error(self, error_message: str) -> None:
        """
        Notifica erro crítico.

        Args:
            error_message: Mensagem de erro
        """
        message = (
            f"{EMOJI['error']} <b>ERRO</b>\n\n"
            f"{error_message}"
        )
        self.send(message)

    def notify_complete(self, total_time: str) -> None:
        """
        Notifica conclusão de todo o processo.

        Args:
            total_time: Tempo total formatado
        """
        message = (
            "🎉 <b>PROCESSO CONCLUÍDO</b>\n\n"
            f"⏱️ Tempo total: {total_time}\n"
            f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            f"{EMOJI['success']} Todos os downloads foram finalizados!"
        )
        self.send(message)

    def notify_incomplete_courses(self, incomplete_count: int) -> None:
        """
        Notifica sobre cursos incompletos detectados.

        Args:
            incomplete_count: Número de cursos incompletos
        """
        message = (
            f"{EMOJI['chart']} <b>CURSOS INCOMPLETOS DETECTADOS</b>\n\n"
            f"Total: {incomplete_count} curso(s)\n\n"
            "Execute novamente para completar os downloads pendentes."
        )
        self.send(message)
