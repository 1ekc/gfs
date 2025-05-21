import argparse
import json
import logging
import pathlib
import shutil
import subprocess
import threading
import zipfile
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tqdm

_logger = logging.getLogger('gfunpack.audio')
_info = _logger.info
_warning = _logger.warning

class AudioProcessor:
    """Класс для обработки аудиофайлов с поддержкой кэширования"""

    CACHE_FILE = "audio_cache.json"
    CHUNK_SIZE = 5  # Обрабатывать по 5 файлов за раз

    def __init__(self, input_path: str, output_path: str,
                 force: bool = False, concurrency: int = 8, clean: bool = True):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.force = force
        self.concurrency = min(concurrency, cpu_count())
        self.clean = clean
        self.extracted = {}

        # Проверка и создание директорий
        utils.check_directory(self.input_path)
        self.bgm_path = self.output_path / 'bgm'
        self.se_path = self.output_path / 'se'
        self.bgm_path.mkdir(parents=True, exist_ok=True)
        self.se_path.mkdir(parents=True, exist_ok=True)

        # Проверка зависимостей
        self._test_dependencies()

        # Поиск ресурсных файлов
        self.resource_files = list(f for f in self.input_path.glob('*.acb.dat') if f.name != 'AVG.acb.dat')
        self.se_resource_file = self.input_path / 'AVG.acb.dat'
        if not self.se_resource_file.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {self.se_resource_file}")

    def _test_dependencies(self):
        """Проверка необходимых зависимостей"""
        try:
            subprocess.run(['vgmstream-cli', '-V'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL).check_returncode()
            subprocess.run(['ffmpeg', '-h'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL).check_returncode()
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Необходимая утилита не найдена: {str(e)}")

    def process_in_chunks(self):
        """Обработка файлов чанками"""
        for i in range(0, len(self.resource_files), self.CHUNK_SIZE):
            chunk = self.resource_files[i:i + self.CHUNK_SIZE]
            self._process_chunk(chunk)

    def _process_chunk(self, files: List[Path]):
        """Обработка чанка файлов"""
        with Pool(processes=self.concurrency) as pool:
            args = [(f, self.bgm_path, self.force, self.clean) for f in files]
            with tqdm.tqdm(total=len(args), desc="Обработка BGM") as bar:
                for _ in pool.imap_unordered(self._extract_acb, args):
                    bar.update()

    def extract_and_convert(self) -> Dict[str, Path]:
        """Основной метод обработки аудио"""
        # Обработка SE файлов
        _info('Обработка SE аудио')
        self._extract_acb((self.se_resource_file, self.se_path, self.force, self.clean))
        se_files = self._transcode_files(list(self.se_path.glob('*.wav')))

        # Обработка BGM файлов чанками
        _info('Обработка BGM аудио')
        self.process_in_chunks()
        bgm_files = self._transcode_files(list(self.bgm_path.glob('*.wav')))

        # Объединение результатов
        all_files = {**se_files, **bgm_files}
        return all_files

    def save(self) -> Path:
        """Сохранение результатов в JSON"""
        if not self.extracted:
            self.extracted = self.extract_and_convert()

        output_file = self.output_path / 'audio.json'
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(
                {k: str(v) for k, v in self.extracted.items()},
                f,
                indent=2,
                ensure_ascii=False
            )
        return output_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Обработка аудиофайлов игры')
    parser.add_argument('input_dir', help='Директория с ресурсами игры')
    parser.add_argument('output_dir', help='Целевая директория для результатов')
    parser.add_argument('--force', action='store_true', help='Принудительная перезапись файлов')
    parser.add_argument('--concurrency', type=int, default=8,
                       help='Количество параллельных процессов')
    parser.add_argument('--no-clean', action='store_true',
                       help='Не удалять промежуточные файлы')
    args = parser.parse_args()

    processor = AudioProcessor(
        input_path=args.input_dir,
        output_path=args.output_dir,
        force=args.force,
        concurrency=args.concurrency,
        clean=not args.no_clean
    )
    result_path = processor.save()
    print(f"Обработка аудио завершена. Результаты сохранены в: {result_path}")