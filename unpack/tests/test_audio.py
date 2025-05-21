from pathlib import Path
from typing import List
from gfunpack import audio

def check_cache(cache_dir: Path, required_files: List[str]) -> bool:
    """Проверяет целостность кэша"""
    for file in required_files:
        if not (cache_dir / file).exists():
            return False
    return True

def test_bgm():
    audio.BGM('downloader/output', 'audio')

if __name__ == '__main__':
    test_bgm()
