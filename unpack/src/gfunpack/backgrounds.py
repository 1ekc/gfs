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


class BackgroundProcessor:
    def __init__(
        self,
        input_dir: pathlib.Path,
        output_dir: pathlib.Path,
        pngquant: bool = False,
        force: bool = False,
        max_workers: Optional[int] = None
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.pngquant = pngquant
        self.force = force
        self.max_workers = max_workers or max(1, cpu_count() - 1)
        self.progress = Manager().dict()

        # Проверка директорий
        if not self.input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {self.input_dir}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_asset_file(self, file_path: pathlib.Path) -> Dict[str, Union[Sprite, Texture2D]]:
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

    def save_image(self, args: Tuple[Tuple[str, Union[Sprite, Texture2D]], int]) -> Optional[Tuple[str, pathlib.Path]]:
        """Сохранение одного изображения с обработкой ошибок"""
        (name, image), pbar_pos = args
        try:
            output_path = self.output_dir / f"{name}.png"

            # Пропуск существующих файлов
            if not self.force and output_path.exists():
                self.progress[pbar_pos] = True
                return (name, output_path)

            # Сохранение изображения
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

    def process_all(self) -> Dict[int, Optional[pathlib.Path]]:
        """Основной метод обработки"""
        try:
            # 1. Загрузка профилей
            profile_asset = self.input_dir / 'asset_textavg.ab'
            profiles = self._load_profiles(profile_asset)

            # 2. Поиск файлов ресурсов
            resource_files = list(self.input_dir.glob('resource_avgtexture*.ab'))
            if not resource_files:
                raise FileNotFoundError("No resource files found")

            logger.info(f"Found {len(resource_files)} resource files to process")

            # 3. Многопоточная обработка файлов
            all_images = {}
            with Pool(processes=self.max_workers) as pool:
                for result in tqdm(
                    pool.imap_unordered(self.process_asset_file, resource_files),
                    total=len(resource_files),
                    desc="Processing AB files"
                ):
                    all_images.update(result)

            # 4. Многопроцессорное сохранение изображений
            saved_images = {}
            tasks = list(all_images.items())

            with Pool(processes=self.max_workers) as pool:
                results = list(tqdm(
                    pool.starmap(
                        self.save_image,
                        [((task), i) for i, task in enumerate(tasks)]
                    ),
                    total=len(tasks),
                    desc="Saving images"
                ))

            # 5. Сопоставление результатов
            saved_images = {k: v for k, v in results if v is not None}
            return self._match_profiles(profiles, saved_images)

        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            raise

    def _load_profiles(self, profile_asset: pathlib.Path) -> List[str]:
        """Загрузка профилей фонов"""
        try:
            # Ваша реализация чтения текстового ассета
            pass
        except Exception as e:
            logger.error(f"Failed to load profiles: {str(e)}")
            raise

    def _match_profiles(self, profiles: List[str], images: Dict[str, pathlib.Path]) -> Dict[int, Optional[pathlib.Path]]:
        """Сопоставление профилей с изображениями"""
        result = {}
        matched = set()

        for idx, name in enumerate(profiles):
            lower_name = name.lower()
            if lower_name in images:
                result[idx] = images[lower_name]
                matched.add(images[lower_name].resolve())
            else:
                result[idx] = None
                logger.warning(f"Profile {name} not found in images")

        # Добавление ненайденных изображений
        unmatched = [p for p in images.values() if p.resolve() not in matched]
        for path in unmatched:
            result[-len(result)] = path

        return result


def main():
    try:
        logger.info("Starting background extraction")

        processor = BackgroundProcessor(
            input_dir=pathlib.Path("downloader/output"),
            output_dir=pathlib.Path("images/background"),
            pngquant=True,
            max_workers=4  # Оптимально для GitHub Actions
        )

        results = processor.process_all()

        # Сохранение результатов
        output_file = pathlib.Path("backgrounds.json")
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(
                {k: str(v) if v else "" for k, v in results.items()},
                f,
                ensure_ascii=False,
                indent=2
            )

        logger.info(f"Successfully processed {len(results)} items")
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())