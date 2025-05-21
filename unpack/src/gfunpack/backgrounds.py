import json
import logging
import pathlib
import re
from multiprocessing import Pool, cpu_count
from typing import Dict, List, Optional, Union

import tqdm
import UnityPy
from UnityPy.classes import Sprite, TextAsset, Texture2D

from gfunpack import utils

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
    def __init__(
            self,
            directory: str,
            destination: str,
            pngquant: bool = False,
            force: bool = False,
            concurrency: Optional[int] = None
    ) -> None:
        """
        Инициализация с поддержкой многопроцессорной обработки

        :param directory: Директория с .ab файлами
        :param destination: Целевая директория для распаковки
        :param pngquant: Использовать pngquant для оптимизации
        :param force: Перезаписывать существующие файлы
        :param concurrency: Количество процессов (по умолчанию - количество ядер CPU)
        """
        self.directory = utils.check_directory(directory)
        self.destination = utils.check_directory(
            pathlib.Path(destination).joinpath('background'),
            create=True
        )
        self.pngquant = utils.test_pngquant(pngquant)
        self.force = force
        self.concurrency = concurrency if concurrency else cpu_count()

        logger.info(f"Initializing with concurrency={self.concurrency}")

        self.profile_asset = self.directory.joinpath('asset_textavg.ab')
        self.resource_files = list(self.directory.glob('resource_avgtexture*.ab'))
        self.extracted = self.extract()

    def _extract_bg_profiles(self) -> List[str]:
        """Извлечение профилей фонов с обработкой ошибок"""
        try:
            content = utils.read_text_asset(
                self.profile_asset,
                'assets/resources/dabao/avgtxt/profiles.txt'
            )
            return [line.strip() for line in content.split('\n') if line.strip()]
        except Exception as e:
            logger.error(f"Failed to extract bg profiles: {str(e)}")
            raise

    def _process_image(self, args: tuple) -> tuple:
        """Обработка одного изображения (для multiprocessing)"""
        name, image, image_path = args
        try:
            if self.force or not image_path.is_file():
                image.image.save(image_path)
                if self.pngquant:
                    utils.pngquant(image_path, use_pngquant=True)
            return (name, image_path)
        except Exception as e:
            logger.error(f"Failed to process {name}: {str(e)}")
            return (name, None)

    def _extract_files(self, resources: Dict[str, Union[Sprite, Texture2D]]) -> Dict[str, pathlib.Path]:
        """Многопроцессорное извлечение файлов"""
        extracted = {}
        tasks = []

        for name, image in resources.items():
            image_path = self.destination.joinpath(f'{name}.png')
            tasks.append((name, image, image_path))

        logger.info(f"Starting extraction of {len(tasks)} images")

        with Pool(processes=self.concurrency) as pool:
            results = list(tqdm.tqdm(
                pool.imap(self._process_image, tasks),
                total=len(tasks),
                desc="Extracting images"
            ))

        for name, path in results:
            if path:
                extracted[name] = path

        return extracted

    def _extract_bg_pics(self) -> Dict[str, pathlib.Path]:
        """Извлечение изображений фонов с улучшенной обработкой ошибок"""
        extracted = {}

        for file in tqdm.tqdm(self.resource_files, desc="Processing AB files"):
            try:
                files: Dict[str, Union[Sprite, Texture2D]] = {}
                asset = UnityPy.load(str(file))

                for obj in asset.objects:
                    if obj.container is None:
                        continue

                    if obj.type.name not in ('Sprite', 'Texture2D'):
                        continue

                    match = _avgtexture_regex.match(obj.container)
                    if match is None:
                        continue

                    name = match.group(1).lower()
                    data = obj.read()

                    # Приоритет для Texture2D
                    if name not in files or files[name].type.name == 'Sprite':
                        files[name] = data

                extracted.update(self._extract_files(files))

            except Exception as e:
                logger.error(f"Error processing {file.name}: {str(e)}")
                continue

        return extracted

    def extract(self) -> Dict[int, Optional[pathlib.Path]]:
        """Основной метод извлечения с улучшенной обработкой ошибок"""
        try:
            bg_profiles = self._extract_bg_profiles()
            pics = self._extract_bg_pics()

            merged: Dict[int, Optional[pathlib.Path]] = {}
            matched: List[pathlib.Path] = []

            for i, name in enumerate(bg_profiles):
                match = pics.get(name.lower())
                merged[i] = match

                if match is not None:
                    matched.append(match.resolve())
                else:
                    logger.warning(f'Background {name} not found')

            # Обработка ненайденных изображений
            unmatched = {p.resolve() for p in pics.values()} - set(matched)
            for path in unmatched:
                merged[-len(merged)] = path

            return merged

        except Exception as e:
            logger.error(f"Extraction failed: {str(e)}")
            raise

    def save(self) -> pathlib.Path:
        """Сохранение результатов с обработкой ошибок"""
        try:
            result = {
                k: "" if v is None else str(v.relative_to(self.destination.parent))
                for k, v in self.extracted.items()
            }

            path = self.destination.parent.joinpath('backgrounds.json')
            with path.open('w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            logger.info(f"Results saved to {path}")
            return path

        except Exception as e:
            logger.error(f"Failed to save results: {str(e)}")
            raise


def test_backgrounds():
    """Тестовая функция для проверки работы"""
    try:
        logger.info("Starting background extraction test")
        bg = BackgroundCollection(
            directory='downloader/output',
            destination='images',
            pngquant=True,
            concurrency=cpu_count()  # Используем все доступные ядра
        )
        bg.save()
        logger.info("Background extraction completed successfully")
    except Exception as e:
        logger.error(f"Background test failed: {str(e)}")
        raise


if __name__ == "__main__":
    test_backgrounds()