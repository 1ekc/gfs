import logging
import pathlib
import subprocess
from typing import Union, Optional

import UnityPy
from UnityPy.classes import TextAsset

_logger = logging.getLogger('gfunpack.utils')
_warning = _logger.warning


def check_directory(directory: typing.Union[pathlib.Path, str], create: bool = False) -> pathlib.Path:
    """Проверяет и создает (при необходимости) директорию."""
    d = pathlib.Path(directory)
    if not d.exists() and create:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as e:
            raise ValueError(f'Failed to create directory {d}: {str(e)}')
    if not d.exists() or not d.is_dir():
        raise ValueError(f'{d} is not a valid directory')
    return d.resolve()


def test_pngquant(use_pngquant: bool) -> bool:
    """Проверяет доступность pngquant."""
    if not use_pngquant:
        return False
    try:
        subprocess.run(
            ['pngquant', '--version'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ).check_returncode()
        return True
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        _warning('pngquant not available: %s', str(e))
        return False


def pngquant(image_path: pathlib.Path, use_pngquant: bool) -> None:
    """Оптимизирует PNG изображение с помощью pngquant."""
    if not use_pngquant or not test_pngquant(True):
        return

    try:
        quant_path = image_path.with_suffix('.fs8.png')
        result = subprocess.run(
            ['pngquant', '--quality', '70-90', '--ext', '.fs8.png', '--strip', str(image_path)],
            check=True
        )
        if result.returncode == 0 and quant_path.exists():
            os.replace(quant_path, image_path)
    except subprocess.SubprocessError as e:
        _warning('Failed to optimize image %s: %s', image_path, str(e))


def read_text_asset(bundle_path: Union[str, pathlib.Path], container: str) -> Optional[str]:
    """Читает текстовый ассет из Unity бандла."""
    try:
        env = UnityPy.load(str(bundle_path))
        for obj in env.objects:
            if isinstance(obj, TextAsset) and getattr(obj, 'container', None) == container:
                text_asset = obj.read()
                return text_asset.m_Script.tobytes().decode('utf-8')
        logger.error(f"TextAsset not found in container: {container}")
        return None
    except Exception as e:
        logger.error(f"Failed to read text asset: {str(e)}")
        return None

    except Exception as e:
        _warning('Failed to read text asset from %s: %s', bundle, str(e), exc_info=True)
        return None