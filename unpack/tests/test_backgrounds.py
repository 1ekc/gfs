from gfunpack import backgrounds

def check_cache(cache_dir: Path, required_files: List[str]) -> bool:
    """Проверяет целостность кэша"""
    for file in required_files:
        if not (cache_dir / file).exists():
            return False
    return True

def test_backgrounds():
    bg = backgrounds.BackgroundCollection('downloader/output', 'images', pngquant=True)
    bg.save()


if __name__ == '__main__':
    test_backgrounds()
