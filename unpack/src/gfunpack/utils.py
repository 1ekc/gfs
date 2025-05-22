import logging
import os
import pathlib
import subprocess
import typing

import UnityPy
from UnityPy.classes import TextAsset

_logger = logging.getLogger('gfunpack.utils')
_warning = _logger.warning


def check_directory(directory: pathlib.Path | str, create: bool = False) -> pathlib.Path:
    d = pathlib.Path(directory)
    if not d.exists() and create:
        os.makedirs(d)
    if not d.exists() or not d.is_dir():
        raise ValueError(f'{d} is not a valid directory')
    return d.resolve()


def test_pngquant(use_pngquant: bool):
    if not use_pngquant:
        return False
    else:
        try:
            subprocess.run(['pngquant', '--help'], stdout=subprocess.DEVNULL).check_returncode()
            return True
        except FileNotFoundError as e:
            _warning('pngquant not available', exc_info=e)
            return False


def pngquant(image_path: pathlib.Path, use_pngquant: bool):
    # pngquant to minimize the image
    if use_pngquant:
        quant_path = image_path.with_suffix('.fs8.png')
        subprocess.run(['pngquant', image_path, '--ext', '.fs8.png', '--strip']).check_returncode()
        os.replace(quant_path, image_path)


def read_text_asset(bundle: pathlib.Path, container: str):
    asset = UnityPy.load(str(bundle))
    profile_reader = [o for o in asset.objects if o.container == container][0]
    assert profile_reader.type.name == 'TextAsset'
    profile = typing.cast(
        TextAsset,
        profile_reader.read(),
    )
    content: str = profile.m_Script.tobytes().decode()
    return content