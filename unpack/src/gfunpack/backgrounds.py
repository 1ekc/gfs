import json
import logging
import pathlib
import re
import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple

import UnityPy
from tqdm import tqdm
from UnityPy.classes import Sprite, Texture2D

# Настройка системы импорта
try:
    from gfunpack import utils
except ImportError:
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
    """Класс для обработки фоновых изображений с исправленной многопроцессорной обработкой"""

    CACHE_FILE = "backgrounds_cache.json"

    def __init__(self, input_path: str, output_path: str, pngquant: bool = False,
                 concurrency: int = 4, force: bool = False):
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
        self.concurrency = min(concurrency, cpu_count())
        self.force = force
        self.extracted = {}

        # Проверка и создание директорий
        utils.check_directory(self.input_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _process_single_file(args: Tuple[Path, re.Pattern]) -> Dict[str, Union[Sprite, Texture2D]]:
        """Статический метод для обработки одного файла (должен быть pickle-able)"""
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
            logging.error(f"Error processing {file_path.name}: {str(e)}")
        return results

    @staticmethod
    def _save_single_image(args: Tuple[Tuple[str, Union[Sprite, Texture2D]], Path, bool, bool]) -> Optional[Path]:
        """Статический метод для сохранения одного изображения (должен быть pickle-able)"""
        (name, image), output_dir, pngquant, force = args
        try:
            output_path = output_dir / f"{name}.png"

            # Пропускаем существующие файлы, если не force
            if not force and output_path.exists() and output_path.stat().st_size > 0:
                return output_path

            if isinstance(image, (Sprite, Texture2D)):
                image.image.save(output_path)
                if pngquant:
                    utils.run_pngquant(output_path)
                return output_path
        except Exception as e:
            logging.error(f"Failed to save {name}: {str(e)}")
        return None

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

    def _extract_bg_pics(self) -> Dict[str, Path]:
        """Основной метод извлечения изображений с поддержкой кэширования"""
        # Проверка кэша
        cache_data = self._load_cache()
        if cache_data and not self.force:
            return {k: Path(v) for k, v in cache_data.items()}

        # Обработка файлов
        resource_files = list(self.input_path.glob('resource_avgtexture*.ab'))
        all_images = {}

        # Используем статический метод для обработки
        with Pool(processes=self.concurrency) as pool:
            results = list(tqdm(
                pool.imap_unordered(
                    self._process_single_file,
                    [(f, _avgtexture_regex) for f in resource_files]
                ),
                total=len(resource_files),
                desc="Processing AB files"
            ))
            for result in results:
                all_images.update(result)

        # Сохранение изображений
        saved_images = {}
        args = [
            ((name, img), self.output_path, self.pngquant, self.force)
            for name, img in all_images.items()
        ]

        with Pool(processes=self.concurrency) as pool:
            results = list(tqdm(
                pool.imap_unordered(self._save_single_image, args),
                total=len(args),
                desc="Saving images"
            ))
            saved_images = {
                name: path
                for (name, _), path in zip(all_images.items(), results)
                if path is not None
            }

        # Обновление кэша
        if saved_images:
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