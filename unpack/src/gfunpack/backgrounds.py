import json
import logging
import pathlib
import re
import sys
from multiprocessing import Pool, cpu_count, Manager
from typing import Dict, List, Optional, Union, Tuple

import UnityPy
from tqdm import tqdm
from UnityPy.classes import Sprite, Texture2D

# Добавляем абсолютный импорт utils
try:
    from gfunpack import utils
except ImportError:
    from . import utils  # Для случаев относительного импорта

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('background_unpack.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('gfunpack.backgrounds')

_avgtexture_regex = re.compile(r'^assets/resources/dabao/avgtexture/([^/]+)\.png$')


class BackgroundCollection:
    def __init__(self, directory: str, destination: str, pngquant: bool = False):
        self.directory = pathlib.Path(directory)
        self.destination = pathlib.Path(destination)
        self.pngquant = utils.test_pngquant(pngquant)
        self.extracted = {}

        # Проверка директорий
        utils.check_directory(self.directory)
        self.destination.mkdir(parents=True, exist_ok=True)

    def _extract_bg_profiles(self) -> List[str]:
        """Извлечение профилей фонов"""
        bundle_path = self.directory / 'asset_textavg.ab'
        content = utils.read_text_asset(
            str(bundle_path),
            'assets/resources/dabao/avgtxt/profiles.txt'
        )
        if content is None:
            raise ValueError("Failed to load profiles.txt")
        return [line.strip() for line in content.split('\n') if line.strip()]

    def _extract_bg_profiles(self) -> List[str]:
        """Извлечение профилей фонов"""
        try:
            content = utils.read_text_asset(
                self.directory / 'asset_textavg.ab',
                'assets/resources/dabao/avgtxt/profiles.txt'
            )
            return [line.strip() for line in content.split('\n') if line.strip()]
        except Exception as e:
            logger.error(f"Failed to extract bg profiles: {str(e)}")
            raise

    def _process_asset_file(self, file_path: pathlib.Path) -> Dict[str, Union[Sprite, Texture2D]]:
        """Обработка одного .ab файла"""
        results = {}
        try:
            env = UnityPy.load(str(file_path))
            for obj in env.objects:
                if obj.container and _avgtexture_regex.match(obj.container):
                    name = _avgtexture_regex.match(obj.container).group(1).lower()
                    data = obj.read()
                    # Приоритет для Texture2D
                    if name not in results or isinstance(results[name], Sprite):
                        results[name] = data
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {str(e)}")
        return results

    def _save_image(self, args: Tuple[Tuple[str, Union[Sprite, Texture2D]], int]) -> Optional[Tuple[str, pathlib.Path]]:
        """Сохранение одного изображения"""
        (name, image), pbar_pos = args
        try:
            output_path = self.destination / f"{name}.png"

            if not self.force and output_path.exists():
                self.progress[pbar_pos] = True
                return (name, output_path)

            if isinstance(image, (Sprite, Texture2D)):
                image.image.save(output_path)
                if self.pngquant:
                    # Здесь должна быть ваша реализация pngquant
                    pass
                self.progress[pbar_pos] = True
                return (name, output_path)
        except Exception as e:
            logger.error(f"Failed to save {name}: {str(e)}")
            self.progress[pbar_pos] = False
        return None

    def _extract_bg_pics(self) -> Dict[str, pathlib.Path]:
        """Основной метод извлечения изображений"""
        extracted = {}
        resource_files = list(self.directory.glob('resource_avgtexture*.ab'))

        with Pool(processes=self.concurrency) as pool:
            results = list(tqdm(
                pool.imap_unordered(self._process_asset_file, resource_files),
                total=len(resource_files),
                desc="Processing AB files"
            ))

        all_images = {}
        for result in results:
            all_images.update(result)

        tasks = list(all_images.items())
        with Pool(processes=self.concurrency) as pool:
            results = list(tqdm(
                pool.starmap(
                    self._save_image,
                    [((task), i) for i, task in enumerate(tasks)]
                ),
                total=len(tasks),
                desc="Saving images"
            ))

        return {k: v for k, v in results if v is not None}

    def extract(self) -> Dict[int, Optional[pathlib.Path]]:
        """Извлечение всех фонов"""
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

        self.extracted = merged  # Сохраняем результат в атрибут
        return merged

    def save(self) -> pathlib.Path:
        """Сохранение результатов в JSON"""
        if not hasattr(self, 'extracted') or not self.extracted:
            self.extract()  # Если extracted нет, вызываем extract()

        result = {
            k: "" if v is None else str(v.relative_to(self.destination.parent))
            for k, v in self.extracted.items()
        }

        path = self.destination.parent.joinpath('backgrounds.json')
        with path.open('w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return path


if __name__ == "__main__":
    processor = BackgroundCollection(
        directory="downloader/output",
        destination="images",
        pngquant=True
    )
    processor.save()