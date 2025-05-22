import argparse
import os
import sys
import pathlib

# Текущая директория скрипта (unpack/src/gfunpack/)
current_dir = pathlib.Path(__file__).parent

# Добавляем путь к корню проекта (unpack/)
sys.path.insert(0, str(current_dir.parent.parent))

# Локальные импорты
from gfunpack import audio, backgrounds, characters, chapters, mapper, prefabs, stories


def main():
    parser = argparse.ArgumentParser(description='GFUnpack - инструмент для распаковки ресурсов')
    parser.add_argument('dir', help='Директория с загруженными ресурсами')
    parser.add_argument('-o', '--output', required=True, help='Выходная директория')
    parser.add_argument('--no-clean', action='store_true', help='Не очищать временные файлы')
    args = parser.parse_args()

    cpus = os.cpu_count() or 2
    downloaded = args.dir
    destination = pathlib.Path(args.output)

    # Обработка фонов
    images = destination.joinpath('images')
    bg = backgrounds.BackgroundCollection(
        input_path=downloaded,
        output_path=str(images),
        pngquant=True,
        concurrency=cpus
    )
    bg.save()

    # Обработка персонажей
    sprite_indices = prefabs.Prefabs(downloaded)
    chars = characters.CharacterCollection(
        directory=downloaded,
        destination=str(images),
        sprite_indices=sprite_indices,
        pngquant=True,
        concurrency=cpus
    )
    chars.extract()

    # Создание карты персонажей
    character_mapper = mapper.Mapper(sprite_indices, chars)
    character_mapper.write_indices()

    # Обработка аудио
    bgm = audio.AudioProcessor(
        input_path=downloaded,
        output_path=str(destination.joinpath('audio')),
        force=False,
        concurrency=cpus,
        clean=not args.no_clean
    )
    bgm.process()
    bgm.save()

    # Обработка историй
    ss = stories.Stories(
        directory=downloaded,
        destination=str(destination.joinpath('stories'))
    )
    ss.save()

    # Обработка глав
    cs = chapters.Chapters(ss)
    cs.save()


if __name__ == '__main__':
    main()