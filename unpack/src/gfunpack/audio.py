import argparse
import json
import logging
import os
import subprocess
import sys
import zipfile
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tqdm

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('audio_unpack.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('audio')


class AudioProcessor:
    """Класс для обработки аудиофайлов"""

    def __init__(self, input_path: str, output_path: str,
                 force: bool = False, concurrency: int = 8, clean: bool = True):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.force = force
        self.concurrency = min(concurrency, cpu_count())
        self.clean = clean
        self.extracted = {}

        # Проверка и создание директорий
        if not self.input_path.exists():
            raise FileNotFoundError(f"Директория не найдена: {self.input_path}")

        self.bgm_path = self.output_path / 'bgm'
        self.se_path = self.output_path / 'se'
        self.bgm_path.mkdir(parents=True, exist_ok=True)
        self.se_path.mkdir(parents=True, exist_ok=True)

        # Поиск ресурсных файлов
        self.resource_files = list(f for f in self.input_path.glob('*.acb.dat') if f.name != 'AVG.acb.dat')
        self.se_resource_file = self.input_path / 'AVG.acb.dat'
        if not self.se_resource_file.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {self.se_resource_file}")

        # Проверка зависимостей
        self._test_dependencies()

    def _test_dependencies(self):
        """Проверка необходимых утилит"""
        try:
            subprocess.run(['vgmstream-cli', '-V'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL).check_returncode()
            subprocess.run(['ffmpeg', '-h'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL).check_returncode()
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            raise RuntimeError(f"Требуемая утилита не найдена: {str(e)}")

    def _extract_acb(self, dat_file: Path, output_dir: Path) -> Optional[Path]:
        """Извлечение ACB файла"""
        try:
            # Распаковка ZIP
            with zipfile.ZipFile(dat_file) as z:
                extracted = z.namelist()
                if not extracted:
                    return None

                z.extractall(output_dir)
                acb_file = output_dir / extracted[0]

                # Переименование .bytes в .acb если нужно
                if acb_file.suffix == '.bytes':
                    new_path = acb_file.with_suffix('.acb')
                    acb_file.rename(new_path)
                    acb_file = new_path

                # Конвертация в WAV
                subprocess.run([
                    'vgmstream-cli',
                    acb_file,
                    '-o',
                    output_dir / '?n.wav',
                    '-S',
                    '0',
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                if self.clean:
                    acb_file.unlink()

                return acb_file
        except Exception as e:
            logger.error(f"Ошибка обработки {dat_file.name}: {str(e)}")
            return None

    def _transcode_to_m4a(self, wav_file: Path) -> Optional[Path]:
        """Конвертация WAV в M4A"""
        try:
            m4a_file = wav_file.with_suffix('.m4a')
            if not self.force and m4a_file.exists():
                return m4a_file

            subprocess.run([
                'ffmpeg',
                '-hide_banner',
                '-loglevel', 'error',
                '-i', wav_file,
                m4a_file,
            ], check=True)

            if self.clean:
                wav_file.unlink()

            return m4a_file
        except Exception as e:
            logger.error(f"Ошибка конвертации {wav_file.name}: {str(e)}")
            return None

    def process(self):
        """Основной метод обработки"""
        # Обработка SE
        logger.info("Обработка SE аудио")
        self._extract_acb(self.se_resource_file, self.se_path)
        for wav in self.se_path.glob('*.wav'):
            if m4a := self._transcode_to_m4a(wav):
                self.extracted[wav.stem] = str(m4a.relative_to(self.output_path))

        # Обработка BGM
        logger.info("Обработка BGM аудио")
        with Pool(processes=self.concurrency) as pool:
            args = [(f, self.bgm_path) for f in self.resource_files]
            for _ in tqdm.tqdm(
                    pool.imap_unordered(self._process_single_bgm, args),
                    total=len(args),
                    desc="Обработка BGM"
            ):
                pass

        # Сбор результатов BGM
        for m4a in self.bgm_path.glob('*.m4a'):
            self.extracted[m4a.stem] = str(m4a.relative_to(self.output_path))

    def _process_single_bgm(self, args: Tuple[Path, Path]):
        """Обработка одного BGM файла"""
        dat_file, output_dir = args
        if self._extract_acb(dat_file, output_dir):
            for wav in output_dir.glob('*.wav'):
                self._transcode_to_m4a(wav)

    def save(self) -> Path:
        """Сохранение результатов"""
        output_file = self.output_path / 'audio.json'
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(
                self.extracted,
                f,
                indent=2,
                ensure_ascii=False
            )
        return output_file


def main():
    parser = argparse.ArgumentParser(description='Обработка аудиофайлов игры')
    parser.add_argument('input_dir', help='Директория с ресурсами')
    parser.add_argument('output_dir', help='Целевая директория')
    parser.add_argument('--force', action='store_true', help='Принудительная перезапись')
    parser.add_argument('--concurrency', type=int, default=4,
                        help='Количество процессов')
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
    processor.process()
    result_path = processor.save()
    print(f"Обработка завершена. Результаты сохранены в: {result_path}")


if __name__ == "__main__":
    main()