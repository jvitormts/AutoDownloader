#!/usr/bin/env python3
"""
AutoDownloader - Sistema de Download Automático de Cursos

Aplicação para download automatizado de materiais de cursos da plataforma
Estratégia Concursos, incluindo vídeos, PDFs e outros materiais.

Autor: Refatorado seguindo boas práticas Python
Data: 2024
"""

import argparse
import sys
import logging
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from config import settings
from notifications import TelegramNotifier, setup_logger
from core import SessionKeepAlive, save_cookies, load_cookies, is_logged_in, CourseDownloader
from services import FileManifestManager, FileDownloader
from detectors import PendingLessonsDetector


def parse_arguments():
    """
    Processa argumentos da linha de comando.

    Returns:
        argparse.Namespace: Argumentos processados
    """
    parser = argparse.ArgumentParser(
        description='AutoDownloader - Download automático de cursos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Exemplos de uso:
  %(prog)s                          # Modo interativo
  %(prog)s --download-dir ./cursos  # Especificar diretório
  %(prog)s --check-pending          # Verificar pendências
  %(prog)s --no-telegram            # Desabilitar notificações
        '''
    )

    parser.add_argument(
        '--download-dir',
        type=str,
        default=settings.DEFAULT_DOWNLOAD_DIR,
        help='Diretório para salvar downloads (padrão: %(default)s)'
    )

    parser.add_argument(
        '--login-wait',
        type=int,
        default=60,
        help='Tempo de espera para login manual em segundos (padrão: %(default)s)'
    )

    parser.add_argument(
        '--check-pending',
        action='store_true',
        help='Verificar cursos com downloads pendentes'
    )

    parser.add_argument(
        '--no-telegram',
        action='store_true',
        help='Desabilitar notificações do Telegram'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default=settings.LOG_LEVEL,
        help='Nível de log (padrão: %(default)s)'
    )

    parser.add_argument(
        '--headless',
        action='store_true',
        help='Executar navegador em modo headless (sem interface)'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 2.0.0'
    )

    return parser.parse_args()


def validate_environment():
    """
    Valida ambiente e configurações.

    Raises:
        SystemExit: Se configurações obrigatórias estiverem faltando
    """
    try:
        settings.validate()
    except ValueError as e:
        print(f"❌ Erro de configuração: {e}")
        print("\n💡 Dica: Verifique o arquivo .env e configure as variáveis necessárias")
        sys.exit(1)


def setup_webdriver(headless: bool = False) -> webdriver.Chrome:
    """
    Configura e retorna o WebDriver do Chrome.

    Args:
        headless: Se True, executa em modo headless

    Returns:
        webdriver.Chrome: WebDriver configurado
    """
    chrome_options = Options()

    if headless:
        chrome_options.add_argument('--headless')

    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={settings.USER_AGENT}')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver


def pick_courses(courses: list) -> list:
    """
    Permite ao usuário selecionar cursos para download.

    Args:
        courses: Lista de cursos disponíveis

    Returns:
        list: Cursos selecionados
    """
    print(f"\n{'=' * 70}")
    print("📚 CURSOS DISPONÍVEIS")
    print(f"{'=' * 70}\n")

    for i, course in enumerate(courses, 1):
        print(f"{i}. {course['title']}")

    print(f"\n{len(courses) + 1}. Baixar TODOS os cursos")
    print("0. Sair")

    while True:
        try:
            choice = input("\n👉 Escolha uma opção: ").strip()

            if choice == '0':
                print("Saindo...")
                sys.exit(0)

            choice_num = int(choice)

            if choice_num == len(courses) + 1:
                return courses

            if 1 <= choice_num <= len(courses):
                return [courses[choice_num - 1]]

            print("❌ Opção inválida. Tente novamente.")

        except ValueError:
            print("❌ Digite um número válido.")
        except KeyboardInterrupt:
            print("\n\nInterrompido pelo usuário.")
            sys.exit(0)


def main():
    """
    Função principal da aplicação.

    Coordena o fluxo de execução do AutoDownloader.
    """
    # Parse argumentos
    args = parse_arguments()

    # Configurar logging
    logger = setup_logger(
        'autodownloader',
        log_file='autodownloader.log',
        level=args.log_level
    )

    logger.info("=" * 70)
    logger.info("AutoDownloader v2.0.0 - Iniciando")
    logger.info("=" * 70)

    # Validar ambiente
    validate_environment()

    # Configurar notificações
    telegram_enabled = settings.TELEGRAM_ENABLED and not args.no_telegram
    telegram = TelegramNotifier(enabled=telegram_enabled)

    if telegram_enabled:
        logger.info("Notificações Telegram: ATIVADAS")
    else:
        logger.info("Notificações Telegram: DESATIVADAS")

    # Criar diretório de download
    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Diretório de download: {download_dir}")

    print("\n" + "=" * 70)
    print("🚀 AutoDownloader v2.0.0")
    print("=" * 70)
    print(f"\n📁 Diretório: {download_dir}")
    print(f"📊 Telegram: {'✅ Ativado' if telegram_enabled else '❌ Desativado'}")
    print(f"📝 Log Level: {args.log_level}")
    print("\n" + "=" * 70)

    # Modo de verificação de pendências
    if args.check_pending:
        logger.info("Modo: Verificação de pendências")
        print("\n🔍 Verificando cursos com downloads pendentes...")

        detector = PendingLessonsDetector(str(download_dir), logger)
        courses = detector.scan_downloaded_courses()

        if not courses:
            print("\n✅ Nenhum curso encontrado no diretório de downloads")
        else:
            print(f"\n📚 Encontrados {len(courses)} curso(s):")
            for i, (name, path) in enumerate(courses.items(), 1):
                lessons = detector.get_course_downloaded_lessons(path)
                print(f"  {i}. {name} ({len(lessons)} aulas)")

        return

    # Modo normal de download
    logger.info("Modo: Download de cursos")

    # Configurar WebDriver
    print("\n🌐 Configurando navegador...")
    driver = setup_webdriver(headless=args.headless)

    try:
        # Navegar para a plataforma
        print(f"🔗 Acessando {settings.BASE_URL}...")
        driver.get(settings.BASE_URL)

        # Tentar carregar cookies
        if load_cookies(driver):
            logger.info("Cookies carregados com sucesso")
            driver.refresh()

        # Verificar login
        if not is_logged_in(driver):
            print("\n⚠️  É necessário fazer login manualmente")
            print(f"⏳ Aguardando {args.login_wait} segundos para login...")

            import time
            time.sleep(args.login_wait)

            if not is_logged_in(driver):
                print("❌ Login não detectado. Encerrando.")
                return

            # Salvar cookies
            save_cookies(driver)
            logger.info("Login realizado e cookies salvos")

        print("✅ Login verificado")

        # Inicializar downloader
        downloader = CourseDownloader(
            driver=driver,
            download_dir=str(download_dir),
            telegram=telegram,
            logger=logger
        )

        # Obter cursos disponíveis
        courses = downloader.get_available_courses()

        if not courses:
            print("\n❌ Nenhum curso encontrado")
            return

        # Selecionar cursos
        selected_courses = pick_courses(courses)

        # Notificar início
        if telegram:
            telegram.notify_start(len(selected_courses))

        # Download dos cursos
        for i, course in enumerate(selected_courses, 1):
            print(f"\n📥 Baixando curso {i}/{len(selected_courses)}")
            downloader.download_course(course)

        # Notificar conclusão
        if telegram:
            telegram.notify_complete("Concluído")

        print("\n" + "=" * 70)
        print("🎉 TODOS OS DOWNLOADS CONCLUÍDOS!")
        print("=" * 70)

    finally:
        driver.quit()
        logger.info("Aplicação finalizada")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Erro fatal: {e}", exc_info=True)
        print(f"\n❌ Erro fatal: {e}")
        sys.exit(1)
