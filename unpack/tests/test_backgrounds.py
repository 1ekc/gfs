import sys
from pathlib import Path
from typing import List

# Добавляем путь к исходникам в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Импортируем нужные модули
try:
    from gfunpack.backgrounds import BackgroundCollection
    from gfunpack import utils
except ImportError:
    from backgrounds import BackgroundCollection
    import utils


def check_cache(cache_dir: Path, required_files: List[str]) -> bool:
    """Проверяет целостность кэша"""
    for file in required_files:
        file_path = cache_dir / file
        if not file_path.exists():
            return False
        if file_path.stat().st_size == 0:  # Проверка на пустые файлы
            return False
    return True


def test_backgrounds():
    # Пути и настройки
    input_dir = 'downloader/output'
    output_dir = 'images'
    required_files = ['backgrounds.json', 'characters.json']  # Пример файлов для проверки

    # Проверяем кэш перед обработкой
    output_path = Path(output_dir)
    if check_cache(output_path, required_files):
        print("Кэш актуален, пропускаем обработку фонов")
        return

    # Если кэш неактуален или отсутствует - обрабатываем
    bg = BackgroundCollection(
        input_path=input_dir,
        output_path=output_dir,
        pngquant=True,
        concurrency=4
    )
    bg.save()

    # После успешной обработки можно создать/обновить кэш-файл
    cache_marker = output_path / '.cache_valid'
    cache_marker.touch()  # Создаем маркер валидного кэша


if __name__ == '__main__':
    test_backgrounds()