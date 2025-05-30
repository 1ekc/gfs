from gfunpack import characters, prefabs
from gfunpack.mapper import Mapper  # Добавляем импорт Mapper
import pathlib


def test_characters():
    # 1. Инициализация prefabs
    sprite_indices = prefabs.Prefabs('downloader/output')

    # 2. Создаем целевую директорию
    output_dir = pathlib.Path('unpack/images/characters')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 3. Обработка персонажей
    character_collection = characters.CharacterCollection(
        directory='downloader/output',
        destination=str(output_dir),
        prefab_indices=sprite_indices,
        pngquant=True
    )
    character_collection.extract()

    # 4. Создание маппинга и сохранение JSON
    mapper = Mapper(sprite_indices, chars)
    mapper.write_indices()  # Это создаст characters.json


if __name__ == '__main__':
    test_characters()