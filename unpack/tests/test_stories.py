from gfunpack import chapters, characters, mapper, prefabs, stories
import pathlib
import logging
import json  # Не хватало этого импорта


def test_stories():
    # 1. Инициализация путей
    output_dir = pathlib.Path('unpack/stories')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Обработка историй
    ss = stories.Stories(
        directory='downloader/output',
        destination=str(output_dir)  # Здесь была пропущена закрывающая скобка
    ss.save()  # Создаст stories.json

    # 3. Обработка глав
    chapters_processor = chapters.Chapters(ss)
    chapters_processor.save()  # Создаст chapters.json

    # 4. Валидация результатов
    validate_json_files(output_dir)


def validate_json_files(output_dir: pathlib.Path):
    required_files = {
        'stories.json': lambda f: len(json.load(f)) > 0,
        'chapters.json': lambda f: 'main' in json.load(f)
    }

    for filename, validator in required_files.items():
        filepath = output_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"{filename} not created!")

        with filepath.open('r', encoding='utf-8') as f:
            if not validator(f):
                raise ValueError(f"Invalid {filename} content")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    test_stories()