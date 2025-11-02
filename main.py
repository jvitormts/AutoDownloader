import os
import re
import time
import argparse
import sys
from urllib.parse import urljoin
import requests
import logging
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime

# --- Configurações ---
BASE_URL = "https://www.estrategiaconcursos.com.br"
MY_COURSES_URL = urljoin(BASE_URL, "/app/dashboard/cursos")

# --- Funções Auxiliares ---

def sanitize_filename(original_filename):
    """
    Remove caracteres inválidos de um nome de arquivo/diretório para garantir
    compatibilidade com o sistema de arquivos.
    """
    sanitized = re.sub(r'[<>:"/\\|?*]', '', original_filename)
    sanitized = re.sub(r'[.,]', '', sanitized)
    sanitized = re.sub(r'[\s-]+', '_', sanitized)
    sanitized = sanitized.strip('._- ')
    return sanitized.strip()

def download_file(url, file_path, current_page_url=None, logger=None):
    """
    Realiza o download de um arquivo usando requests, exibindo uma barra de progresso em porcentagem.
    Passa o logger para registrar eventos importantes no arquivo de log do curso.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
    }
    if current_page_url:
        headers['Referer'] = current_page_url
    try:
        with requests.get(url, stream=True, timeout=60, headers=headers) as response:
            response.raise_for_status()
            total = response.headers.get('content-length')
            total = int(total) if total else None
            downloaded = 0
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        if total:
                            downloaded += len(chunk)
                            progress = 100 * downloaded / total
                            print(f"\r  Baixando: {os.path.basename(file_path)} [{progress:.2f}%]", end="")
            print()
            if logger:
                logger.info(f"Baixado com sucesso: {file_path}")
        return True
    except Exception as e:
        print(f"Erro tentando baixar {file_path}: {e}")
        if logger:
            logger.error(f"Erro ao baixar {file_path}: {e}")
        return False

def handle_popups(driver):
    """
    Tenta fechar popups conhecidos que podem interceptar cliques.
    """
    print("Verificando e lidando com popups/overlays...")
    try:
        getsitecontrol_widget = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, "getsitecontrol-44266"))
        )
        print("Widget 'getsitecontrol' detectado. Tentando fechar via JavaScript.")
        driver.execute_script("arguments[0].style.display = 'none';", getsitecontrol_widget)
        time.sleep(1)
    except TimeoutException:
        print("Nenhum popup 'getsitecontrol' detectado.")
    except Exception as e:
        print(f"Erro inesperado ao lidar com popups: {e}")

def get_course_data(driver):
    """
    Navega até a página 'Meus Cursos' e extrai os links e títulos dos cursos.
    Timeout aumentado para 60 segundos conforme melhoria solicitada.
    """
    print("Navegando para a página 'Meus Cursos'...")
    driver.get(MY_COURSES_URL)
    try:
        # Aumentando timeout para 60 segundos (melhoria #1)
        WebDriverWait(driver, 60).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section[id^='card'] a.sc-cHGsZl"))
        )
        time.sleep(3)
        course_elements = driver.find_elements(By.CSS_SELECTOR, "section[id^='card']")
        courses = []
        for course_elem in course_elements:
            try:
                link_elem = course_elem.find_element(By.CSS_SELECTOR, "a.sc-cHGsZl")
                title_elem = course_elem.find_element(By.CSS_SELECTOR, "h1.sc-ksYbfQ")
                course_href = link_elem.get_attribute('href')
                course_title = title_elem.text
                if course_href and course_title:
                    courses.append({"title": course_title, "url": course_href})
            except (NoSuchElementException, StaleElementReferenceException):
                print("Elemento de curso não encontrado ou obsoleto. Pulando.")
        print(f"Encontrados {len(courses)} cursos.")
        return courses
    except TimeoutException:
        print("Erro: Tempo esgotado ao carregar a lista de cursos.")
        return []

def get_lesson_data(driver, course_url):
    """
    Navega até a página de um curso e extrai os links, títulos e subtítulos das aulas.
    Timeout aumentado para 40 segundos conforme melhoria solicitada.
    """
    print(f"Navegando para a página do curso: {course_url}")
    driver.get(course_url)
    try:
        # Aumentando timeout para 40 segundos (melhoria #2)
        WebDriverWait(driver, 40).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.LessonList-item a.Collapse-header"))
        )
        time.sleep(3)
        lesson_elements = driver.find_elements(By.CSS_SELECTOR, "div.LessonList-item")
        lessons = []
        for lesson_elem in lesson_elements:
            try:
                # Pula aulas desabilitadas
                if "isDisabled" in lesson_elem.get_attribute("class"):
                    continue
                link_elem = lesson_elem.find_element(By.CSS_SELECTOR, "a.Collapse-header")
                title_h2_elem = lesson_elem.find_element(By.CSS_SELECTOR, "h2.SectionTitle")
                lesson_title = title_h2_elem.text
                lesson_subtitle = ""
                try:
                    title_p_elem = lesson_elem.find_element(By.CSS_SELECTOR, "p.sc-gZMcBi")
                    lesson_subtitle = title_p_elem.text
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
                print("Elemento da aula não encontrado ou obsoleto. Pulando.")
        print(f"Encontradas {len(lessons)} aulas disponíveis.")
        return lessons
    except TimeoutException:
        print("Erro: Tempo esgotado ao carregar a lista de aulas.")
        return []

def download_lesson_materials(driver, lesson_info, course_title, download_dir, logger):
    """
    Navega para a página de uma aula, salva o subtítulo e baixa os materiais.
    Agora com logs e exibição de progresso nos downloads.
    """
    lesson_title = lesson_info['title']
    lesson_subtitle = lesson_info['subtitle']
    lesson_url = lesson_info['url']

    print(f"Processando aula: {lesson_title}")
    driver.get(lesson_url)
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.Lesson-contentTop, div.LessonVideos"))
        )
        time.sleep(2)
    except TimeoutException:
        print(f"Erro: Tempo esgotado ao carregar a página da aula '{lesson_title}'. Pulando.")
        logger.warning(f"Tempo esgotado na aula '{lesson_title}'. Pulando.")
        return

    handle_popups(driver)

    sanitized_course_title = sanitize_filename(course_title)
    sanitized_lesson_title = sanitize_filename(lesson_title)
    lesson_download_path = os.path.join(download_dir, sanitized_course_title, sanitized_lesson_title)
    try:
        os.makedirs(lesson_download_path, exist_ok=True)
    except OSError as e:
        print(f"ERRO CRÍTICO ao criar diretório: {e}")
        logger.error(f"Erro ao criar diretório '{lesson_download_path}': {e}")
        return

    # Salva o subtítulo em um arquivo de texto
    if lesson_subtitle:
        subjects_file_path = os.path.join(lesson_download_path, "Assuntos_dessa_aula.txt")
        if not os.path.exists(subjects_file_path):
            try:
                with open(subjects_file_path, 'w', encoding='utf-8') as f:
                    f.write(lesson_subtitle)
                print("Arquivo 'Assuntos_dessa_aula.txt' criado.")
                logger.info("Arquivo 'Assuntos_dessa_aula.txt' criado.")
            except Exception as e:
                print(f"Erro ao criar 'Assuntos_dessa_aula.txt': {e}")
                logger.error(f"Erro ao criar 'Assuntos_dessa_aula.txt': {e}")

    # Baixa Livros Eletrônicos (PDFs)
    print("Procurando por Livros Eletrônicos (PDFs)...")
    try:
        pdf_links = driver.find_elements(By.XPATH, "//a[contains(@class, 'LessonButton') and .//i[contains(@class, 'icon-file')]]")
        for pdf_link in pdf_links:
            pdf_url = pdf_link.get_attribute('href')
            if not pdf_url or "api.estrategiaconcursos.com.br" not in pdf_url:
                continue
            pdf_text_raw = "original"
            try:
                version_text_element = pdf_link.find_element(By.CSS_SELECTOR, "span.LessonButton-text > span")
                pdf_text_raw = version_text_element.text.strip()
            except NoSuchElementException:
                pass
            filename_suffix = "_" + sanitize_filename(pdf_text_raw)
            filename = f"{sanitized_lesson_title}_Livro_Eletronico{filename_suffix}.pdf"
            full_file_path = os.path.join(lesson_download_path, filename)
            if os.path.exists(full_file_path):
                print(f"PDF '{filename}' já existe. Pulando.")
                logger.info(f"PDF '{filename}' já existe. Pulando.")
            else:
                print(f"Encontrado PDF: {pdf_text_raw}")
                logger.info(f"Iniciando download do PDF: {filename}")
                download_file(pdf_url, full_file_path, driver.current_url, logger)
    except Exception as e:
        print(f"Erro ao processar PDFs: {e}")
        logger.error(f"Erro ao processar PDFs: {e}")

    # Baixa vídeos da playlist da aula
    print("Procurando por Vídeos...")
    try:
        playlist_items = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.ListVideos-items-video a.VideoItem"))
        )
        videos_to_download = []
        for item in playlist_items:
            video_href = item.get_attribute('href')
            try:
                video_title = item.find_element(By.CSS_SELECTOR, "span.VideoItem-info-title").text
            except Exception:
                video_title = "video_sem_titulo"
            if video_href and video_title:
                videos_to_download.append({'url': video_href, 'title': video_title})

        if not videos_to_download:
            print("Nenhum vídeo encontrado na playlist.")
            return

        print(f"Encontrados {len(videos_to_download)} vídeos. Iniciando downloads...")
        for i, video_info in enumerate(videos_to_download):
            print(f"\nProcessando vídeo {i + 1}/{len(videos_to_download)}: {video_info['title']}")
            logger.info(f"Iniciando download do vídeo: {video_info['title']}")
            driver.get(video_info['url'])
            time.sleep(2)

            # Baixar PDFs específicos do vídeo (exemplo: Resumo, Slides, Mapa Mental)
            video_pdf_types = {
                "Baixar Resumo": f"_Resumo_{i}.pdf",
                "Baixar Slides": f"_Slides_Video_{i}.pdf",
                "Baixar Mapa Mental": f"_Mapa_Mental_{i}.pdf"
            }
            for pdf_button_text, filename_suffix in video_pdf_types.items():
                try:
                    pdf_link_elem = driver.find_element(By.XPATH,
                        f"//a[contains(@class, 'LessonButton') and .//span[contains(text(), '{pdf_button_text}')]]")
                    pdf_url = pdf_link_elem.get_attribute('href')
                    if pdf_url:
                        filename = f"{sanitized_lesson_title}_{sanitize_filename(video_info['title'])}{filename_suffix}"
                        full_file_path = os.path.join(lesson_download_path, filename)
                        if os.path.exists(full_file_path):
                            print(f"PDF '{pdf_button_text.replace('Baixar ', '')}' para este vídeo já existe. Pulando.")
                            logger.info(f"PDF '{pdf_button_text}' para vídeo '{video_info['title']}' já existe. Pulando.")
                        else:
                            print(f"Encontrado {pdf_button_text} para o vídeo '{video_info['title']}'.")
                            logger.info(f"Iniciando download do {pdf_button_text} para vídeo '{video_info['title']}'.")
                            download_file(pdf_url, full_file_path, driver.current_url, logger)
                    else:
                        print(f"{pdf_button_text} para o vídeo '{video_info['title']}' encontrado, mas sem URL.")
                        logger.warning(f"{pdf_button_text} sem URL para vídeo '{video_info['title']}'")
                except NoSuchElementException:
                    print(f"{pdf_button_text} não encontrado para o vídeo '{video_info['title']}'.")
                    logger.info(f"{pdf_button_text} não encontrado para vídeo '{video_info['title']}'.")
                except Exception as e:
                    print(f"Erro ao processar '{pdf_button_text}' para o vídeo '{video_info['title']}': {e}")
                    logger.error(f"Erro ao processar '{pdf_button_text}' para vídeo '{video_info['title']}': {e}")

            # Baixar o vídeo em uma das qualidades preferidas (ex: 720p, 480p, 360p)
            try:
                download_options_header = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//div[contains(@class, 'Collapse-header')]//strong[text()='Opções de download']")
                    )
                )
                header_container = download_options_header.find_element(By.XPATH,
                    "./ancestor::div[contains(@class, 'Collapse-header-container')]")
                collapse_body = header_container.find_element(By.XPATH, "./following-sibling::div")
                if not collapse_body.is_displayed():
                    driver.execute_script("arguments[0].click();", download_options_header)
                    WebDriverWait(driver, 5).until(EC.visibility_of(collapse_body))

                sanitized_video_title = sanitize_filename(video_info['title'])
                preferred_qualities = ["720p", "480p", "360p"]
                downloaded_successfully = False
                for quality in preferred_qualities:
                    filename = f"{sanitized_video_title}_Video_{quality}.mp4"
                    full_file_path = os.path.join(lesson_download_path, filename)
                    if os.path.exists(full_file_path):
                        print(f"Vídeo '{filename}' já existe. Pulando.")
                        logger.info(f"Vídeo '{filename}' já existe. Pulando.")
                        downloaded_successfully = True
                        break
                    try:
                        video_link_elem = collapse_body.find_element(By.XPATH, f".//a[contains(text(), '{quality}')]")
                        video_url = video_link_elem.get_attribute('href')
                        print(f"Tentando baixar vídeo em {quality}...")
                        logger.info(f"Tentando baixar vídeo '{filename}' em {quality}")
                        if download_file(video_url, full_file_path, driver.current_url, logger):
                            downloaded_successfully = True
                            break
                    except NoSuchElementException:
                        continue  # Tenta próxima qualidade
                if not downloaded_successfully:
                    print(f"AVISO: Não foi possível baixar nenhuma qualidade para o vídeo '{video_info['title']}'.")
                    logger.warning(f"Não foi possível baixar vídeo '{video_info['title']}' em nenhuma qualidade preferida.")
            except TimeoutException:
                print(f"Não foi possível encontrar/expandir 'Opções de download' para o vídeo '{video_info['title']}'.")
                logger.warning(f"Não foi possível expandir 'Opções de download' para vídeo '{video_info['title']}'.")
            except Exception as e:
                print(f"Erro ao baixar o vídeo '{video_info['title']}': {e}")
                logger.error(f"Erro ao baixar vídeo '{video_info['title']}': {e}")

    except TimeoutException:
        print("Nenhuma playlist de vídeos encontrada nesta aula.")
        logger.info("Nenhuma playlist de vídeos encontrada nesta aula.")
    except Exception as e:
        print(f"Erro geral ao processar a playlist de vídeos: {e}")
        logger.error(f"Erro geral na playlist de vídeos: {e}")


def setup_course_logger(course_title, download_dir):
    """
    Configura e retorna um logger para gravar logs específicos para cada curso.
    Os logs serão salvos no arquivo download_{nome_do_curso}.log dentro do diretório do download.
    """
    sanitized = sanitize_filename(course_title)
    logfile = os.path.join(download_dir, f"download_{sanitized}.log")
    logger = logging.getLogger(sanitized)
    logger.handlers = []  # Remove handlers anteriores para evitar duplicidade
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(logfile, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger

def pick_courses(courses):
    """
    Lista os cursos encontrados e espera que o usuário selecione quais deseja baixar,
    digitando os números separados por vírgula.
    """
    print("\nCURSOS DISPONÍVEIS:")
    for idx, course in enumerate(courses, 1):
        print(f" [{idx}] {course['title']}")
    while True:
        sel = input("\nDigite os números dos cursos a baixar (ex: 1,3,5): ")
        try:
            indices = [int(x.strip())-1 for x in sel.split(",") if x.strip().isdigit()]
            if all(0 <= idx < len(courses) for idx in indices) and indices:
                return [courses[idx] for idx in indices]
        except Exception:
            pass
        print("Seleção inválida. Tente novamente.")

# --- Função de Login ---
def login(driver, wait_time):
    """
    Variante simples para login manual.
    O usuário deve realizar o login no navegador aberto dentro do tempo fornecido.
    """
    print("Navegando para a página de login...")
    driver.get("https://perfil.estrategia.com/login")
    print("=" * 60)
    print("AÇÃO NECESSÁRIA: FAÇA O LOGIN MANUALMENTE NO NAVEGADOR ABERTO")
    print(f"O script ficará pausado por {wait_time} segundos para você completar o login.")
    print("Após o login, o script continuará automaticamente.")
    print("NÃO feche o navegador.")
    print("=" * 60)
    time.sleep(wait_time)
    print("Pausa para login concluída. Continuando o script...")

def run_downloader(download_dir, login_wait_time):
    """
    Função principal que orquestra o processo de login, escolha dos cursos, e download.
    Implementa maiores timeouts, listagem e seleção de cursos, logs com tempos.
    """
    try:
        os.makedirs(download_dir, exist_ok=True)
        print(f"Diretório de download configurado para: {os.path.abspath(download_dir)}")
    except OSError as e:
        print(f"ERRO: Não foi possível criar o diretório de download '{download_dir}'. Erro: {e}")
        sys.exit(1)

    driver = webdriver.Edge()
    driver.maximize_window()

    try:
        login(driver, login_wait_time)

        courses = get_course_data(driver)
        if not courses:
            print("Nenhum curso encontrado ou erro ao carregar a página. Encerrando.")
            return

        # Melhoria #3 e #4: Listagem + seleção interativa dos cursos
        selected_courses = pick_courses(courses)

        for i, course in enumerate(selected_courses):
            logger = setup_course_logger(course['title'], download_dir)
            print(f"\n[{i + 1}/{len(selected_courses)}] Baixando curso: {course['title']}")
            logger.info("Iniciando download do curso.")
            start_time = datetime.now()

            lessons = get_lesson_data(driver, course['url'])
            if not lessons:
                print(f"Nenhuma aula encontrada para o curso '{course['title']}'. Pulando.")
                logger.warning("Nenhuma aula encontrada para este curso.")
                continue

            for j, lesson_info in enumerate(lessons):
                print(f" -> Aula {j + 1}/{len(lessons)}: {lesson_info['title']}")
                logger.info(f"Início download da aula '{lesson_info['title']}'")
                download_lesson_materials(driver, lesson_info, course['title'], download_dir, logger)
                time.sleep(2)

            end_time = datetime.now()
            delta = end_time - start_time
            logger.info(f"Download do curso finalizado. Tempo total: {delta}")
            print(f"Tempo de download do curso '{course['title']}': {delta}")

    except Exception as e:
        print(f"Ocorreu um erro geral no script: {e}")
    finally:
        print("\nProcesso concluído. Fechando o navegador em 10 segundos.")
        time.sleep(10)
        driver.quit()

def main():
    """
    Analisa os argumentos da linha de comando e inicia o processo.
    """
    parser = argparse.ArgumentParser(
        description="Baixador de cursos do Estratégia Concursos.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-d', '--dir',
        dest='download_dir',
        metavar='PATH',
        type=str,
        default="C:/Users/joao.santosm/projetos/curso",
        help="O caminho para a pasta onde os cursos serão salvos.\n(Padrão: E:/Estrategia)"
    )
    parser.add_argument(
        "-w", "--wait-time",
        type=int,
        default=60,
        help="Tempo em segundos para aguardar o login manual (padrão: 60)."
    )
    args = parser.parse_args()
    run_downloader(args.download_dir, args.wait_time)

if __name__ == "__main__":
    main()
