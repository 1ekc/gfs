import argparse
import json
import logging
import pathlib
import re
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple

import UnityPy
from tqdm import tqdm
from UnityPy.classes import Sprite, Texture2D

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('background_unpack.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

_avgtexture_regex = re.compile(r'^assets/resources/dabao/avgtexture/([^/]+)\.png$')


class BackgroundCollection:
    """Класс для обработки фоновых изображений"""

    CACHE_FILE = "backgrounds_cache.json"
    CHUNK_SIZE = 5  # Обрабатывать по 5 файлов за раз

    def __init__(self, input_path: str, output_path: str, pngquant: bool = False,
                 concurrency: int = 4, force: bool = False):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.pngquant = utils.test_pngquant(pngquant)
        self.concurrency = min(concurrency, cpu_count())
        self.force = force
        self.extracted = {}

        utils.check_directory(self.input_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _process_single_file(args: Tuple[Path, re.Pattern]) -> Dict[str, Union[Sprite, Texture2D]]:
        file_path, regex = args
        results = {}
        try:
            env = UnityPy.load(str(file_path))
            for obj in env.objects:
                if obj.container and regex.match(obj.container):
                    name = regex.match(obj.container).group(1).lower()
                    data = obj.read()
                    if name not in results or isinstance(results[name], Sprite):
                        results[name] = data
        except Exception as e:
            logger.error(f"Ошибка обработки {file_path.name}: {str(e)}")
        return results

    def _process_files_in_chunks(self, files: List[Path]) -> Dict[str, Union[Sprite, Texture2D]]:
        all_images = {}
        for i in range(0, len(files), self.CHUNK_SIZE):
            chunk = files[i:i + self.CHUNK_SIZE]
            with Pool(processes=self.concurrency) as pool:
                results = list(tqdm(
                    pool.imap_unordered(
                        self._process_single_file,
                        [(f, _avgtexture_regex) for f in chunk]
                    ),
                    total=len(chunk),
                    desc=f"Обработка чанка {i // self.CHUNK_SIZE + 1}"
                ))
                for result in results:
                    all_images.update(result)
        return all_images

    @staticmethod
    def _save_single_image(args: Tuple[Tuple[str, Union[Sprite, Texture2D]], Path, bool, bool]) -> Optional[Path]:
        (name, image), output_dir, pngquant, force = args
        try:
            output_path = output_dir / f"{name}.png"
            if not force and output_path.exists() and output_path.stat().st_size > 0:
                return output_path

            if isinstance(image, (Sprite, Texture2D)):
                image.image.save(output_path)
                if pngquant:
                    utils.run_pngquant(output_path)
                return output_path
        except Exception as e:
            logger.error(f"Ошибка сохранения {name}: {str(e)}")
        return None

    def _save_images(self, all_images: Dict[str, Union[Sprite, Texture2D]]) -> Dict[str, Path]:
        saved_images = {}
        args = [
            ((name, img), self.output_path, self.pngquant, self.force)
            for name, img in all_images.items()
        ]

        with Pool(processes=self.concurrency) as pool:
            results = list(tqdm(
                pool.imap_unordered(self._save_single_image, args),
                total=len(args),
                desc="Сохранение изображений"
            ))
            saved_images = {
                name: path
                for (name, _), path in zip(all_images.items(), results)
                if path is not None
            }
        return saved_images

    def _extract_bg_profiles(self) -> List[str]:
        try:
            content = utils.read_text_asset(
                self.input_path / 'asset_textavg.ab',
                'assets/resources/dabao/avgtxt/profiles.txt'
            )
            return [line.strip() for line in content.split('\n') if line.strip()]
        except Exception as e:
            logger.error(f"Ошибка извлечения профилей: {str(e)}")
            raise

    def extract(self) -> Dict[int, Optional[Path]]:
        resource_files = list(self.input_path.glob('resource_avgtexture*.ab'))
        if not resource_files:
            raise FileNotFoundError("Не найдены файлы ресурсов resource_avgtexture*.ab")

        logger.info("Начало обработки %d файлов", len(resource_files))

        all_images = self._process_files_in_chunks(resource_files)
        saved_images = self._save_images(all_images)

        merged = {}
        for i, name in enumerate(self._extract_bg_profiles()):
            match = saved_images.get(name.lower())
            merged[i] = match
            if not match:
                logger.warning('Фон %s не найден', name)

        for path in set(p.resolve() for p in saved_images.values()):
            merged[-len(merged)] = path

        self.extracted = merged
        return merged

    def save(self) -> Path:
        if not self.extracted:
            self.extract()

        result = {
            k: "" if v is None else str(v.relative_to(self.output_path.parent))
            for k, v in self.extracted.items()
        }

        output_file = self.output_path.parent / 'backgrounds.json'
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info("Результаты сохранены в %s", output_file)
        return output_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dir', help='Директория с ресурсами игры')
    parser.add_argument('output_dir', help='Целевая директория для результатов')
    parser.add_argument('--pngquant', action='store_true', help='Использовать pngquant')
    parser.add_argument('--force', action='store_true', help='Принудительная перезапись')
    parser.add_argument('--concurrency', type=int, default=cpu_count(),
                        help='Количество процессов (по умолчанию - все ядра)')
    args = parser.parse_args()

    processor = BackgroundCollection(
        input_path=args.input_dir,
        output_path=args.output_dir,
        pngquant=args.pngquant,
        force=args.force,
        concurrency=args.concurrency
    )
    result_path = processor.save()
    print(f"Обработка завершена. Результаты: {result_path}")


if __name__ == "__main__":
    main()