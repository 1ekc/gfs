#!/usr/bin/env python3
"""
Backgrounds processor for GFL assets
"""

import os
import subprocess
import argparse
import json
import logging
import re
import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple

# Добавляем путь к проекту в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import UnityPy
    from tqdm import tqdm
    from UnityPy.classes import Sprite, Texture2D, TextAsset
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "UnityPy", "tqdm"])
    import UnityPy
    from tqdm import tqdm
    from UnityPy.classes import Sprite, Texture2D, TextAsset

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


def setup_environment():
    """Установка необходимых зависимостей"""
    try:
        import UnityPy
        from tqdm import tqdm
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "UnityPy", "tqdm"])


def find_txt_files(base_path: Path) -> Dict[str, Path]:
    """Находит все txt файлы в указанной директории"""
    txt_files = {}
    for txt_path in base_path.glob('**/*.txt'):
        txt_files[txt_path.stem.lower()] = txt_path
    return txt_files


def read_text_asset(ab_path: Path, txt_files: Dict[str, Path] = None) -> str:
    """Извлекает текстовые ассеты из asset bundle или локальных файлов"""
    # Сначала пробуем найти в локальных файлах
    if txt_files:
        stem = ab_path.stem.lower()
        if stem in txt_files:
            with open(txt_files[stem], 'r', encoding='utf-8') as f:
                return f.read()

    # Если не нашли в файлах, пробуем извлечь из asset bundle
    try:
        env = UnityPy.load(str(ab_path))
        for obj in env.objects:
            if obj.type.name == "TextAsset":
                data = obj.read()
                if hasattr(data, 'm_Script'):
                    script = data.m_Script
                    if isinstance(script, bytes):
                        return script.decode('utf-8')
                    return str(script)
        raise ValueError(f"No TextAsset found in {ab_path.name}")
    except Exception as e:
        logger.error(f"Error reading {ab_path}: {str(e)}")
        raise


class BackgroundCollection:  # Было BackgroundProcessor
    """Обработчик фоновых изображений"""

    def __init__(self, input_dir: str, output_dir: str, pngquant: bool = False, concurrency: int = 4):
        self.input_path = Path(input_dir)
        self.output_path = Path(output_dir)
        self.pngquant = pngquant
        self.concurrency = concurrency
        self.output_path.mkdir(parents=True, exist_ok=True)

    def save(self):
        """Основной процесс обработки"""
        try:
            resource_files = list(self.input_path.glob('resource_avgtexture*.ab'))
            if not resource_files:
                raise FileNotFoundError("No resource_avgtexture*.ab files found")

            backgrounds = self._extract_backgrounds(resource_files)
            result_file = self.output_path / 'backgrounds.json'
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(backgrounds, f, ensure_ascii=False, indent=2)
            return result_file

        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            sys.exit(1)

    def _extract_backgrounds(self, resource_files: List[Path]) -> Dict:
        """Извлечение фонов из файлов ресурсов"""
        # Получаем профили из asset_textavg.ab или локальных файлов
        profiles = self._get_profiles()

        # Обрабатываем фоновые изображения
        backgrounds = {}
        with Pool(cpu_count()) as pool:
            results = pool.map(self._process_file, resource_files)

        for result in results:
            backgrounds.update(result)

        # Сопоставляем с профилями
        return {i: backgrounds.get(name.lower()) for i, name in enumerate(profiles)}

    def _get_profiles(self) -> List[str]:
        """Получает список профилей из файла или asset bundle"""
        profiles_path = self.input_path / 'asset_textavg.ab'
        if not profiles_path.exists() and self.txt_files:
            # Пробуем найти в txt файлах
            if 'profiles' in self.txt_files:
                with open(self.txt_files['profiles'], 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                raise FileNotFoundError("Profiles file not found")
        else:
            content = read_text_asset(profiles_path, self.txt_files)

        # Обработка содержимого
        if content.startswith('{') and content.endswith('}'):  # JSON
            data = json.loads(content)
            return data.get('profiles', []) if isinstance(data, dict) else data
        return [line.strip() for line in content.split('\n') if line.strip()]

    def _process_file(self, file_path: Path) -> Dict:
        """Обработка одного файла ресурсов"""
        try:
            env = UnityPy.load(str(file_path))
            file_results = {}

            for obj in env.objects:
                if obj.container and _avgtexture_regex.match(obj.container):
                    name = _avgtexture_regex.match(obj.container).group(1).lower()
                    data = obj.read()
                    if isinstance(data, (Sprite, Texture2D)):
                        output_path = self.output_path / f"{name}.png"
                        data.image.save(output_path)
                        file_results[name] = str(output_path)

            return file_results
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {str(e)}")
            return {}


def main():
    parser = argparse.ArgumentParser(description='Process background images')
    parser.add_argument('--input', required=True, help='Input directory with .ab files')
    parser.add_argument('--output', required=True, help='Output directory for results')
    parser.add_argument('--txt-data', help='Path to gf-data-rus/asset/avgtxt directory')
    args = parser.parse_args()

    setup_environment()
    processor = BackgroundProcessor(args.input, args.output, args.txt_data)
    result_path = processor.process()
    print(f"Processing complete. Results saved to: {result_path}")


if __name__ == "__main__":
    main()