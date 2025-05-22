import argparse
import json
import logging
import os
import pathlib
import re
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Tuple
from multiprocessing import cpu_count
import tqdm
import UnityPy
from UnityPy.classes import Sprite, Texture2D

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('character_unpack.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

_character_file_regex = re.compile('^character_(.*)\\.ab$')
_alpha_postfixes = {
    'ar18/AR18_N_1.png': 'ar18/AR18_N_0.png',
    'ar18/AR18_N_2.png': 'ar18/AR18_N_0.png',
    'ar18/AR18_N_3.png': 'ar18/AR18_N_0.png',
    'ar18/AR18_N_4.png': 'ar18/pic_AR18.png',
    'npc-sakura/Pic_Sakura_D.png': 'npc-sakura/Pic_Sakura_D_1.png',
}


def run_pngquant(image_path: Path):
    """Запуск pngquant для оптимизации изображения"""
    try:
        subprocess.run(['pngquant', '--force', '--skip-if-larger', '--ext', '.png', str(image_path)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        logger.warning(f"Ошибка pngquant: {str(e)}")


class CharacterCollection:
    """Класс для обработки персонажей"""

    CACHE_FILE = "characters.json"
    CHUNK_SIZE = 5

    def __init__(self, input_path: str, output_path: str, pngquant: bool = False,
                 concurrency: int = 4, force: bool = False):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.pngquant = pngquant
        self.concurrency = min(concurrency, cpu_count())
        self.force = force
        self.extracted = {}
        self._semaphore = threading.Semaphore(self.concurrency)

        if not self.input_path.exists():
            raise FileNotFoundError(f"Директория не найдена: {self.input_path}")
        self.output_path.mkdir(parents=True, exist_ok=True)

    def _merge_alpha_channel(self, directory: Path, name: str, sprite: Texture2D, alpha_sprite: Texture2D):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            image_path = directory / f"{name}.png"

            if not self.force and image_path.exists():
                return image_path

            temp_files = []
            try:
                sprite_path = directory / f"{name}_temp.png"
                alpha_path = directory / f"{name}_alpha_temp.png"
                sprite.image.save(sprite_path)
                alpha_sprite.image.save(alpha_path)
                temp_files.extend([sprite_path, alpha_path])

                subprocess.run([
                    'magick', sprite_path, alpha_path,
                    '-compose', 'copy-opacity', '-composite',
                    image_path
                ], check=True)

                if self.pngquant:
                    run_pngquant(image_path)

                return image_path
            finally:
                for f in temp_files:
                    f.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Ошибка объединения {name}: {str(e)}")
            return None

    def _process_sprite_chunk(self, sprites: List[Tuple[str, int, Texture2D, Texture2D]]):
        with tqdm.tqdm(total=len(sprites), desc="Обработка спрайтов") as bar:
            for character, sprite_id, sprite, alpha in sprites:
                self._semaphore.acquire()
                threading.Thread(
                    target=self._process_single_sprite,
                    args=(character, sprite_id, sprite, alpha, bar),
                    daemon=True
                ).start()

        for _ in range(self.concurrency):
            self._semaphore.acquire()

    def _process_single_sprite(self, character: str, sprite_id: int,
                               sprite: Texture2D, alpha: Texture2D, bar: tqdm.tqdm):
        try:
            char_dir = self.output_path / character.lower()
            result = self._merge_alpha_channel(char_dir, f"{sprite_id}", sprite, alpha)
            if result:
                self.extracted[f"{character}/{sprite_id}"] = str(result.relative_to(self.output_path))
        finally:
            bar.update()
            self._semaphore.release()

    def _apply_alpha_postfixes(self):
        """Применение специальных правил для альфа-каналов"""
        for src, dst in _alpha_postfixes.items():
            src_path = self.output_path / src
            dst_path = self.output_path / dst
            if src_path.exists() and dst_path.exists():
                try:
                    src_path.unlink()
                    os.link(dst_path, src_path)
                except Exception as e:
                    logger.error(f"Ошибка применения постфикса {src}->{dst}: {str(e)}")

    def extract(self):
        """Основной метод извлечения"""
        env = UnityPy.load(str(self.input_path / 'resource_character.ab'))

        sprites = []
        for obj in env.objects:
            if obj.type.name in ('Sprite', 'Texture2D'):
                data = obj.read()
                if hasattr(data, 'name') and data.name:
                    sprites.append((data.name, obj.path_id, data))

        for i in range(0, len(sprites), self.CHUNK_SIZE):
            self._process_sprite_chunk(sprites[i:i + self.CHUNK_SIZE])

        self._apply_alpha_postfixes()

    def save(self) -> Path:
        output_path = self.output_path.parent / self.CACHE_FILE
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(self.extracted, f, ensure_ascii=False, indent=2)
        return output_path


def main():
    parser = argparse.ArgumentParser(description='Обработка персонажей игры')
    parser.add_argument('input_dir', help='Директория с ресурсами')
    parser.add_argument('output_dir', help='Целевая директория')
    parser.add_argument('--pngquant', action='store_true', help='Использовать pngquant')
    parser.add_argument('--force', action='store_true', help='Принудительная перезапись')
    parser.add_argument('--concurrency', type=int, default=4,
                        help='Количество потоков')
    args = parser.parse_args()

    processor = CharacterCollection(
        directory=args.input_dir,
        destination=args.output_dir,
        pngquant=args.pngquant,
        force=args.force,
        concurrency=args.concurrency
    )
    processor.extract()
    result_path = processor.save()
    print(f"Обработка завершена. Результаты: {result_path}")


if __name__ == "__main__":
    main()