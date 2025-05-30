import argparse
import os
import pathlib

from gfunpack import audio, backgrounds, chapters, characters, mapper, prefabs, stories


parser = argparse.ArgumentParser()
parser.add_argument('dir')
parser.add_argument('-o', '--output', required=True)
parser.add_argument('--no-clean', action='store_true')
parser.add_argument('--lang', default='rus', choices=['rus', 'ch'],
                   help='Localization language (rus/ch)')
args = parser.parse_args()

cpus = os.cpu_count() or 2

downloaded = args.dir
destination = pathlib.Path(args.output)

images = destination.joinpath('images')
bg = backgrounds.BackgroundCollection(
    str(downloaded),
    str(destination),
    pngquant=True,
    concurrency=cpus
)
bg.save()

sprite_indices = prefabs.Prefabs(downloaded)
chars = characters.CharacterCollection(downloaded, str(images), sprite_indices, pngquant=True, concurrency=cpus)
chars.extract()

character_mapper = mapper.Mapper(sprite_indices, chars)
character_mapper.write_indices()

bgm = audio.BGM(downloaded, str(destination.joinpath('audio')), concurrency=cpus, clean=not args.no_clean)
bgm.save()

ss = stories.Stories(
    str(pathlib.Path(downloaded).parent),  # передаем unpack/ вместо downloader/
    str(destination.joinpath('stories')),
    gf_data_directory=str(pathlib.Path(downloaded).parent.joinpath(f'gf-data-{args.lang}')),
    lang=args.lang
)
ss.save()
cs = chapters.Chapters(ss)
cs.save()