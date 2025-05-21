import json
import logging
import pathlib
import re
import sys
from multiprocessing import Pool, cpu_count, Manager
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple

import UnityPy
from tqdm import tqdm
from UnityPy.classes import Sprite, Texture2D

# Настройка системы импорта
try:
    # Попытка абсолютного импорта
    from gfunpack import utils
except ImportError:
    # Относительный импорт для прямого запуска
    import utils

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
    """Класс для обработки и извлечения фоновых изображений с поддержкой кэширования"""

    CACHE_FILE = "backgrounds_cache.json"

    def __init__(self, input_path: str, output_path: str, pngquant: bool = False, concurrency: int = 4,
                 force: bool = False):
        """
        Args:
            input_path: Путь к директории с ресурсами
            output_path: Путь для сохранения результатов
            pngquant: Использовать pngquant для оптимизации
            concurrency: Количество параллельных процессов
            force: Принудительная перезапись существующих файлов
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.pngquant = utils.test_pngquant(pngquant)
        self.concurrency = concurrency
        self.force = force
        self.extracted = {}
        self._manager = Manager()
        self.progress = self._manager.dict()

        # Проверка и создание директорий
        utils.check_directory(self.input_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> Optional[Dict]:
        """Загрузка данных из кэша"""
        cache_file = self.output_path / self.CACHE_FILE
        if cache_file.exists():
            try:
                with cache_file.open('r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache: {str(e)}")
        return None

    def _save_cache(self, data: Dict):
        """Сохранение данных в кэш"""
        cache_file = self.output_path / self.CACHE_FILE
        try:
            with cache_file.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache: {str(e)}")

    def _extract_bg_profiles(self) -> List[str]:
        """Извлечение профилей фонов"""
        try:
            content = utils.read_text_asset(
                self.input_path / 'asset_textavg.ab',
                'assets/resources/dabao/avgtxt/profiles.txt'
            )
            return [line.strip() for line in content.split('\n') if line.strip()]
        except Exception as e:
            logger.error(f"Failed to extract bg profiles: {str(e)}")
            raise

    def _process_asset_file(self, file_path: Path) -> Dict[str, Union[Sprite, Texture2D]]:
        """Обработка одного .ab файла"""
        results = {}
        try:
            env = UnityPy.load(str(file_path))
            for obj in env.objects:
                if obj.container and _avgtexture_regex.match(obj.container):
                    name = _avgtexture_regex.match(obj.container).group(1).lower()
                    data = obj.read()
                    if name not in results or isinstance(results[name], Sprite):
                        results[name] = data
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {str(e)}")
        return results

    def _save_image(self, args: Tuple[Tuple[str, Union[Sprite, Texture2D]], int]) -> Optional[Tuple[str, Path]]:
        """Сохранение одного изображения с проверкой кэша"""
        (name, image), pbar_pos = args
        try:
            output_path = self.output_path / f"{name}.png"

            # Проверка кэша и существующих файлов
            if not self.force and output_path.exists() and output_path.stat().st_size > 0:
                self.progress[pbar_pos] = True
                return (name, output_path)

            if isinstance(image, (Sprite, Texture2D)):
                image.image.save(output_path)
                if self.pngquant:
                    utils.run_pngquant(output_path)
                self.progress[pbar_pos] = True
                return (name, output_path)
        except Exception as e:
            logger.error(f"Failed to save {name}: {str(e)}")
            self.progress[pbar_pos] = False
        return None

    def _extract_bg_pics(self) -> Dict[str, Path]:
        """Основной метод извлечения изображений с поддержкой кэширования"""
        # Проверка кэша
        cache_data = self._load_cache()
        if cache_data and not self.force:
            return {k: Path(v) for k, v in cache_data.items()}

        # Извлечение данных
        resource_files = list(self.input_path.glob('resource_avgtexture*.ab'))
        all_images = {}

        with Pool(processes=self.concurrency) as pool:
            results = list(tqdm(
                pool.imap_unordered(self._process_asset_file, resource_files),
                total=len(resource_files),
                desc="Processing AB files"
            ))
            for result in results:
                all_images.update(result)

        # Сохранение изображений
        tasks = list(all_images.items())
        saved_images = {}

        with Pool(processes=self.concurrency) as pool:
            results = list(tqdm(
                pool.starmap(
                    self._save_image,
                    [((task), i) for i, task in enumerate(tasks)]
                ),
                total=len(tasks),
                desc="Saving images"
            ))
            saved_images = {k: v for k, v in results if v is not None}

        # Обновление кэша
        self._save_cache({k: str(v) for k, v in saved_images.items()})
        return saved_images

    def extract(self) -> Dict[int, Optional[Path]]:
        """Извлечение всех фонов с поддержкой кэширования"""
        bg_profiles = self._extract_bg_profiles()
        pics = self._extract_bg_pics()

        merged = {}
        matched = []

        for i, name in enumerate(bg_profiles):
            match = pics.get(name.lower())
            merged[i] = match
            if match:
                matched.append(match.resolve())
            else:
                logger.warning(f'Background {name} not found')

        # Добавление ненайденных изображений
        for path in set(p.resolve() for p in pics.values()) - set(matched):
            merged[-len(merged)] = path

        self.extracted = merged
        return merged

    def save(self) -> Path:
        """Сохранение результатов в JSON с поддержкой кэширования"""
        if not hasattr(self, 'extracted') or not self.extracted:
            self.extract()

        result = {
            k: "" if v is None else str(v.relative_to(self.output_path.parent))
            for k, v in self.extracted.items()
        }

        output_file = self.output_path.parent / 'backgrounds.json'
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return output_file


if __name__ == "__main__":
    # Пример использования с поддержкой аргументов командной строки
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input_dir', help='Input directory with game resources')
    parser.add_argument('output_dir', help='Output directory for processed files')
    parser.add_argument('--pngquant', action='store_true', help='Use pngquant optimization')
    parser.add_argument('--force', action='store_true', help='Force re-process all files')
    args = parser.parse_args()

    processor = BackgroundCollection(
        input_path=args.input_dir,
        output_path=args.output_dir,
        pngquant=args.pngquant,
        force=args.force,
        concurrency=cpu_count()
    )
    result_path = processor.save()
    print(f"Processing complete. Results saved to: {result_path}")