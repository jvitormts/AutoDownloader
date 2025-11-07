# ============================================================================
# MÓDULO DE DOWNLOADS PARALELOS DE VÍDEOS
# ============================================================================
# Extensão do sistema de downloads paralelos para suportar vídeos grandes
# com duas estratégias: múltiplos vídeos simultâneos e download segmentado.

import os
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import logging
from dataclasses import dataclass

# ============================================================================
# ESTRATÉGIA 1: MÚLTIPLOS VÍDEOS SIMULTÂNEOS (SIMPLES)
# ============================================================================

@dataclass
class VideoDownloadTask:
    """Representa uma tarefa de download de vídeo."""
    video_url: str
    video_path: str
    video_name: str
    quality: str  # 360p, 480p, 720p, 1080p
    lesson_title: str
    expected_size_mb: int = 0
    
    # Status tracking
    status: str = "pending"  # pending, downloading, completed, failed
    bytes_downloaded: int = 0
    total_bytes: int = 0
    start_time: float = None
    end_time: float = None
    error_message: str = ""


class ParallelVideoDownloader:
    """
    Gerencia downloads de múltiplos vídeos simultaneamente.
    
    Estratégia: Baixa N vídeos ao mesmo tempo (cada um completo).
    Recomendado: 2-3 vídeos simultâneos para evitar saturar banda.
    """
    
    def __init__(self, max_concurrent_videos: int = 2, 
                 chunk_size: int = 8192,
                 logger: logging.Logger = None):
        """
        Inicializa o downloader de vídeos paralelos.
        
        Args:
            max_concurrent_videos (int): Número de vídeos baixados simultaneamente (1-4)
            chunk_size (int): Tamanho do chunk para streaming (8KB padrão)
            logger (logging.Logger): Logger para registros
        """
        self.max_concurrent = max(1, min(max_concurrent_videos, 4))  # Limita 1-4
        self.chunk_size = chunk_size
        self.logger = logger
        self.tasks: List[VideoDownloadTask] = []
        self.tasks_lock = threading.Lock()
        self.completed_tasks = 0
        self.failed_tasks = 0
    
    def add_video_task(self, video_url: str, video_path: str, video_name: str,
                      quality: str, lesson_title: str) -> VideoDownloadTask:
        """Adiciona um vídeo à fila de download."""
        task = VideoDownloadTask(
            video_url=video_url,
            video_path=video_path,
            video_name=video_name,
            quality=quality,
            lesson_title=lesson_title
        )
        
        with self.tasks_lock:
            self.tasks.append(task)
        
        return task
    
    def _download_single_video(self, task: VideoDownloadTask) -> Tuple[bool, str]:
        """
        Baixa um único vídeo com progresso.
        
        Args:
            task (VideoDownloadTask): Tarefa de download
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem_erro)
        """
        try:
            # Verificar se já existe
            if os.path.exists(task.video_path):
                task.status = "completed"
                task.total_bytes = os.path.getsize(task.video_path)
                task.bytes_downloaded = task.total_bytes
                if self.logger:
                    self.logger.info(f"Vídeo já existe: {task.video_name}")
                return True, "already_exists"
            
            # Criar diretório
            os.makedirs(os.path.dirname(task.video_path), exist_ok=True)
            
            task.status = "downloading"
            task.start_time = time.time()
            
            # Headers para download
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'video/mp4,video/*,*/*'
            }
            
            # Fazer requisição com stream
            response = requests.get(task.video_url, stream=True, timeout=60, headers=headers)
            response.raise_for_status()
            
            # Obter tamanho total
            task.total_bytes = int(response.headers.get('content-length', 0))
            
            # Download com progresso
            with open(task.video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        task.bytes_downloaded += len(chunk)
                        
                        # Log de progresso a cada 10MB
                        if task.bytes_downloaded % (10 * 1024 * 1024) < self.chunk_size:
                            progress_pct = (task.bytes_downloaded / task.total_bytes * 100) if task.total_bytes > 0 else 0
                            if self.logger:
                                self.logger.debug(f"{task.video_name}: {progress_pct:.1f}%")
            
            task.status = "completed"
            task.end_time = time.time()
            
            duration = task.end_time - task.start_time
            speed_mbps = (task.total_bytes / (1024*1024)) / duration if duration > 0 else 0
            
            if self.logger:
                self.logger.info(
                    f"✓ Vídeo baixado: {task.video_name} "
                    f"({task.total_bytes / (1024*1024):.2f}MB @ {speed_mbps:.2f}MB/s)"
                )
            
            return True, ""
            
        except requests.exceptions.Timeout:
            task.status = "failed"
            error_msg = "Timeout na conexão"
            task.error_message = error_msg
            if self.logger:
                self.logger.error(f"❌ Timeout: {task.video_name}")
            return False, error_msg
            
        except requests.exceptions.ConnectionError as e:
            task.status = "failed"
            error_msg = f"Erro de conexão: {e}"
            task.error_message = error_msg
            if self.logger:
                self.logger.error(f"❌ Conexão: {task.video_name}")
            return False, error_msg
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            if self.logger:
                self.logger.error(f"❌ Erro em {task.video_name}: {e}")
            return False, str(e)
    
    def download_all_videos(self) -> Dict:
        """
        Executa download de todos os vídeos em paralelo.
        
        Returns:
            Dict: Estatísticas dos downloads
        """
        if not self.tasks:
            return {"total": 0, "completed": 0, "failed": 0}
        
        print(f"\n{'=' * 70}")
        print(f"🎬 INICIANDO DOWNLOADS PARALELOS DE VÍDEOS")
        print(f"{'=' * 70}")
        print(f"Total de vídeos: {len(self.tasks)}")
        print(f"Downloads simultâneos: {self.max_concurrent}\n")
        
        if self.logger:
            self.logger.info(f"Iniciando download de {len(self.tasks)} vídeos")
        
        start_time = time.time()
        self.completed_tasks = 0
        self.failed_tasks = 0
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submeter todas as tarefas
            futures = {
                executor.submit(self._download_single_video, task): task
                for task in self.tasks
            }
            
            # Processar resultados conforme completam
            for future in as_completed(futures):
                task = futures[future]
                try:
                    success, error = future.result()
                    
                    if success:
                        self.completed_tasks += 1
                        print(f"✓ [{self.completed_tasks}/{len(self.tasks)}] {task.video_name}")
                    else:
                        self.failed_tasks += 1
                        print(f"✗ [{self.completed_tasks + self.failed_tasks}/{len(self.tasks)}] {task.video_name}: {error}")
                
                except Exception as e:
                    self.failed_tasks += 1
                    if self.logger:
                        self.logger.error(f"Erro ao processar {task.video_name}: {e}")
        
        elapsed = time.time() - start_time
        total_size = sum(t.total_bytes for t in self.tasks) / (1024 * 1024)
        avg_speed = total_size / elapsed if elapsed > 0 else 0
        
        stats = {
            "total": len(self.tasks),
            "completed": self.completed_tasks,
            "failed": self.failed_tasks,
            "total_time_seconds": elapsed,
            "total_size_mb": round(total_size, 2),
            "average_speed_mbps": round(avg_speed, 2)
        }
        
        print(f"\n{'=' * 70}")
        print(f"📊 RESUMO DE DOWNLOADS DE VÍDEOS")
        print(f"{'=' * 70}")
        print(f"✓ Completados: {stats['completed']}")
        print(f"✗ Falhos: {stats['failed']}")
        print(f"📦 Total: {stats['total_size_mb']}MB")
        print(f"⏱ Tempo: {stats['total_time_seconds']:.2f}s")
        print(f"⚡ Velocidade média: {stats['average_speed_mbps']:.2f}MB/s")
        print(f"{'=' * 70}\n")
        
        return stats


# ============================================================================
# ESTRATÉGIA 2: DOWNLOAD SEGMENTADO (CHUNKS PARALELOS)
# ============================================================================

class SegmentedVideoDownloader:
    """
    Baixa um único vídeo dividindo-o em segmentos paralelos.
    
    Estratégia: Divide o vídeo em N partes e baixa cada parte simultaneamente.
    Recomendado: 4-8 segmentos para vídeos grandes (>500MB).
    Requisito: Servidor DEVE suportar Range requests.
    """
    
    def __init__(self, num_segments: int = 4, 
                 chunk_size: int = 8192,
                 logger: logging.Logger = None):
        """
        Inicializa o downloader segmentado.
        
        Args:
            num_segments (int): Número de segmentos paralelos (2-16)
            chunk_size (int): Tamanho do chunk para streaming
            logger (logging.Logger): Logger
        """
        self.num_segments = max(2, min(num_segments, 16))
        self.chunk_size = chunk_size
        self.logger = logger
    
    def supports_range_requests(self, url: str) -> bool:
        """
        Verifica se o servidor suporta Range requests.
        
        Args:
            url (str): URL do vídeo
            
        Returns:
            bool: True se suporta, False caso contrário
        """
        try:
            headers = {'Range': 'bytes=0-0'}
            response = requests.head(url, headers=headers, timeout=10)
            
            # Servidor aceita ranges se retornar 206 Partial Content
            if response.status_code == 206:
                if self.logger:
                    self.logger.info(f"✓ Servidor suporta Range requests")
                return True
            
            # Verificar header Accept-Ranges
            if 'Accept-Ranges' in response.headers:
                if response.headers['Accept-Ranges'] == 'bytes':
                    if self.logger:
                        self.logger.info(f"✓ Servidor aceita Range via header")
                    return True
            
            if self.logger:
                self.logger.warning(f"⚠ Servidor NÃO suporta Range requests")
            
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Erro ao verificar Range support: {e}")
            return False
    
    def _download_segment(self, url: str, start_byte: int, end_byte: int, 
                         segment_path: str) -> Tuple[bool, str]:
        """
        Baixa um segmento específico do vídeo.
        
        Args:
            url (str): URL do vídeo
            start_byte (int): Byte inicial
            end_byte (int): Byte final
            segment_path (str): Caminho para salvar segmento
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem_erro)
        """
        try:
            headers = {
                'Range': f'bytes={start_byte}-{end_byte}',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, stream=True, timeout=60)
            
            if response.status_code not in [200, 206]:
                return False, f"Status code inválido: {response.status_code}"
            
            with open(segment_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
            
            if self.logger:
                size_mb = os.path.getsize(segment_path) / (1024 * 1024)
                self.logger.debug(f"Segmento baixado: {os.path.basename(segment_path)} ({size_mb:.2f}MB)")
            
            return True, ""
            
        except Exception as e:
            error_msg = str(e)
            if self.logger:
                self.logger.error(f"Erro ao baixar segmento {start_byte}-{end_byte}: {e}")
            return False, error_msg
    
    def _merge_segments(self, segment_paths: List[str], output_path: str) -> bool:
        """
        Une todos os segmentos em um único arquivo.
        
        Args:
            segment_paths (List[str]): Lista de caminhos dos segmentos
            output_path (str): Caminho do arquivo final
            
        Returns:
            bool: True se sucesso, False caso contrário
        """
        try:
            print(f"\n🔀 Unindo {len(segment_paths)} segmentos...")
            
            with open(output_path, 'wb') as outfile:
                for i, segment_path in enumerate(segment_paths):
                    if not os.path.exists(segment_path):
                        if self.logger:
                            self.logger.error(f"Segmento ausente: {segment_path}")
                        return False
                    
                    with open(segment_path, 'rb') as infile:
                        outfile.write(infile.read())
                    
                    print(f"  Segmento {i+1}/{len(segment_paths)} unido")
            
            # Remover segmentos temporários
            for segment_path in segment_paths:
                try:
                    os.remove(segment_path)
                except:
                    pass
            
            print(f"✓ Vídeo unido com sucesso: {os.path.basename(output_path)}")
            
            if self.logger:
                self.logger.info(f"Segmentos unidos em: {output_path}")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Erro ao unir segmentos: {e}")
            return False
    
    def download_video_segmented(self, video_url: str, output_path: str) -> Tuple[bool, Dict]:
        """
        Baixa um vídeo usando download segmentado.
        
        Args:
            video_url (str): URL do vídeo
            output_path (str): Caminho de destino
            
        Returns:
            Tuple[bool, Dict]: (sucesso, estatísticas)
        """
        # Verificar se servidor suporta Range
        if not self.supports_range_requests(video_url):
            return False, {"error": "Servidor não suporta Range requests"}
        
        # Obter tamanho total do vídeo
        try:
            response = requests.head(video_url, timeout=10)
            total_size = int(response.headers.get('content-length', 0))
            
            if total_size == 0:
                return False, {"error": "Não foi possível determinar tamanho do vídeo"}
            
            print(f"\n📦 Tamanho do vídeo: {total_size / (1024*1024):.2f}MB")
            print(f"🔢 Dividindo em {self.num_segments} segmentos...")
            
        except Exception as e:
            return False, {"error": f"Erro ao obter tamanho: {e}"}
        
        # Calcular ranges para cada segmento
        segment_size = total_size // self.num_segments
        segment_paths = []
        download_tasks = []
        
        for i in range(self.num_segments):
            start_byte = i * segment_size
            end_byte = start_byte + segment_size - 1 if i < self.num_segments - 1 else total_size - 1
            
            segment_path = f"{output_path}.part{i}"
            segment_paths.append(segment_path)
            download_tasks.append((start_byte, end_byte, segment_path))
        
        # Baixar segmentos em paralelo
        start_time = time.time()
        failed_segments = []
        
        print(f"\n⬇️ Baixando {self.num_segments} segmentos em paralelo...")
        
        with ThreadPoolExecutor(max_workers=self.num_segments) as executor:
            futures = {
                executor.submit(
                    self._download_segment, 
                    video_url, 
                    start, 
                    end, 
                    path
                ): (i, start, end)
                for i, (start, end, path) in enumerate(download_tasks)
            }
            
            for future in as_completed(futures):
                segment_idx, start, end = futures[future]
                try:
                    success, error = future.result()
                    if success:
                        print(f"  ✓ Segmento {segment_idx + 1}/{self.num_segments} completo")
                    else:
                        print(f"  ✗ Segmento {segment_idx + 1}/{self.num_segments} falhou: {error}")
                        failed_segments.append(segment_idx)
                except Exception as e:
                    print(f"  ✗ Segmento {segment_idx + 1}/{self.num_segments} erro: {e}")
                    failed_segments.append(segment_idx)
        
        # Verificar se todos os segmentos foram baixados
        if failed_segments:
            error_msg = f"{len(failed_segments)} segmentos falharam: {failed_segments}"
            if self.logger:
                self.logger.error(error_msg)
            return False, {"error": error_msg}
        
        # Unir segmentos
        if not self._merge_segments(segment_paths, output_path):
            return False, {"error": "Erro ao unir segmentos"}
        
        elapsed = time.time() - start_time
        speed_mbps = (total_size / (1024*1024)) / elapsed if elapsed > 0 else 0
        
        stats = {
            "total_size_mb": round(total_size / (1024*1024), 2),
            "segments": self.num_segments,
            "time_seconds": round(elapsed, 2),
            "speed_mbps": round(speed_mbps, 2)
        }
        
        print(f"\n✓ Download segmentado concluído!")
        print(f"  Tamanho: {stats['total_size_mb']}MB")
        print(f"  Tempo: {stats['time_seconds']}s")
        print(f"  Velocidade: {stats['speed_mbps']}MB/s")
        
        return True, stats


# ============================================================================
# FUNÇÃO HELPER PARA INTEGRAÇÃO
# ============================================================================

def create_video_downloader(strategy: str = "parallel", 
                           num_concurrent: int = 2,
                           num_segments: int = 4,
                           logger: logging.Logger = None):
    """
    Factory para criar downloader de vídeos.
    
    Args:
        strategy (str): "parallel" (múltiplos vídeos) ou "segmented" (chunks paralelos)
        num_concurrent (int): Número de vídeos simultâneos (estratégia parallel)
        num_segments (int): Número de segmentos (estratégia segmented)
        logger (logging.Logger): Logger
        
    Returns:
        ParallelVideoDownloader ou SegmentedVideoDownloader
    """
    if strategy == "parallel":
        return ParallelVideoDownloader(
            max_concurrent_videos=num_concurrent,
            logger=logger
        )
    elif strategy == "segmented":
        return SegmentedVideoDownloader(
            num_segments=num_segments,
            logger=logger
        )
    else:
        raise ValueError(f"Estratégia inválida: {strategy}. Use 'parallel' ou 'segmented'")


def get_optimal_video_strategy(video_size_mb: int, connection_speed_mbps: float) -> Dict:
    """
    Sugere a melhor estratégia baseado no tamanho do vídeo e velocidade.
    
    Args:
        video_size_mb (int): Tamanho do vídeo em MB
        connection_speed_mbps (float): Velocidade de conexão em Mbps
        
    Returns:
        Dict: Recomendação de estratégia e parâmetros
    """
    # Vídeos pequenos (<200MB): Download simples
    if video_size_mb < 200:
        return {
            "strategy": "parallel",
            "num_concurrent": 3,
            "reason": "Vídeos pequenos, melhor baixar múltiplos ao mesmo tempo"
        }
    
    # Vídeos médios (200-800MB): Paralelo com poucos workers
    elif video_size_mb < 800:
        return {
            "strategy": "parallel",
            "num_concurrent": 2,
            "reason": "Vídeos médios, 2 simultâneos para evitar saturar banda"
        }
    
    # Vídeos grandes (>800MB): Considerar segmentado
    else:
        # Conexão rápida (>25Mbps): Usar segmentado
        if connection_speed_mbps > 25:
            return {
                "strategy": "segmented",
                "num_segments": 8,
                "reason": "Vídeo grande + conexão rápida = segmentado com 8 partes"
            }
        # Conexão média (10-25Mbps): Segmentado com menos partes
        elif connection_speed_mbps > 10:
            return {
                "strategy": "segmented",
                "num_segments": 4,
                "reason": "Vídeo grande + conexão média = segmentado com 4 partes"
            }
        # Conexão lenta (<10Mbps): Paralelo conservador
        else:
            return {
                "strategy": "parallel",
                "num_concurrent": 1,
                "reason": "Vídeo grande + conexão lenta = 1 por vez"
            }
