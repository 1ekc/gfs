import json
import logging
import os
import pathlib
import re
import typing
import chardet  # Добавлен импорт для определения кодировки

import UnityPy
from UnityPy.classes import TextAsset

from gfunpack import mapper, utils, manual_chapters

_logger = logging.getLogger('gfunpack.prefabs')
_warning = _logger.warning

_text_asset_regex = re.compile('^assets/resources/dabao/avgtxt/(.+.txt)$')

_speaker_regex = re.compile('<speaker>(.*)</speaker>', re.IGNORECASE)
_sprite_regex = re.compile('^([^()<>]*)\\((\\d*)\\)')
_effect_tag_regex = re.compile('</?([^<>]+)>')
_line_replace_templates = [
    (
        re.compile('[\x00-\x1f\x7f-\x9f]'),
        ' ',
    ),
    (
        re.compile('<color=(#\\w+)>', re.IGNORECASE),
        lambda match: f'<span style="color: {match.group(1)}">',
    ),
    (
        re.compile('<size=(\\d+)>', re.IGNORECASE),
        lambda match: f'<span style="font-size: {int(match.group(1)) / 50}em">',
    ),
    (
        re.compile('</size>|</color>', re.IGNORECASE),
        '</span>',
    )
]

_va11_drinks = {
    1: 'Bad Touch',
    2: 'Beer',
    3: 'Bleeding Jane',
    4: 'Bloom Light',
    5: 'Blue Fairy',
    6: 'Brandtini',
    7: 'Cobalt Velvet',
    8: 'Crevice Spike',
    9: 'Fluffy Dream',
    10: 'Fringe Weaver',
    11: 'Frothy Water',
    12: 'Grizzly Temple',
    13: 'Gut Punch',
    14: 'Marsblast',
    15: 'Mercury Blast',
    16: 'Moonblast',
    17: 'Piano Man',
    18: 'Piano Woman',
    19: 'Piledriver',
    20: 'Sparkle Star',
    21: 'Sugar Rush',
    22: 'Sunshine Cloud',
    23: 'Suplex',
    24: 'Zen Star',
    25: 'Flaming Moai',
}

_wrong_sprites = {
    "G36C": {
        7: ("G36CMod", 0),
    },
}

_sprite_effects = {
    '隐身': 'stealth',
}

class StoryResources:
    audio: dict[str, str]
    backgrounds: dict[str, str]
    characters: dict[str, dict[str, mapper.SpriteDetails]]

    def __init__(self, audio_json: pathlib.Path, background_json: pathlib.Path, character_json: pathlib.Path) -> None:
        self.audio = json.load(audio_json.open(encoding='utf-8'))
        self.backgrounds = json.load(background_json.open(encoding='utf-8'))
        self.characters = json.load(character_json.open(encoding='utf-8'))
        for character in self.characters.values():
            for k, sprite in character.items():
                character[k] = mapper.SpriteDetails(**typing.cast(dict[str, typing.Any], sprite))
        characters: dict[str, dict[str, mapper.SpriteDetails]] = {}
        for k, v in self.characters.items():
            if k.lower() in characters:
                _warning('duplicate character: %s', k)
                characters[k.lower()].update(v)
            else:
                characters[k.lower()] = v
        self.characters = characters

class StoryTranspiler:
    external: StoryResources
    script: str
    filename: str

    effect_tags: set[str]
    content_tags: set[str]

    missing_audio: dict[str, set[str]]

    _markdown: list[str]
    _remote_narrators: set[str]
    _sprites: dict[str, dict[int, str]]
    _resources: set[str]
    _classes: set[str]
    _class_updates: set[str]

    def __init__(self, resources: StoryResources, script: str, filename: str) -> None:
        self.external = resources
        self.script = script
        self.filename = filename

        self.effect_tags = set()
        self.content_tags = set()

        self.missing_audio = {}

        self._markdown = []
        self._remote_narrators = set()
        self._sprites = {}
        self._resources = set()
        self._classes = set()
        self._class_updates = set()

    def _update_class(self, c: str, state: bool):
        if state:
            self._classes.add(c)
            self._class_updates.add(c)
        else:
            if c in self._classes:
                self._classes.remove(c)
                self._class_updates.add(f'!{c}')

    def _convert_content_line(self, line: str):
        for pattern, replacement in _line_replace_templates:
            line = re.sub(pattern, replacement, line)
        self.content_tags.update(
            tag.lower()
            for tag in re.findall(_effect_tag_regex, line)
            if not tag.startswith('span')
        )
        return line

    def _convert_content(self, content: str, tags: str | None = None):
        tags = '' if tags is None else f'{tags} '
        return [
            f'{tags}<p>{self._convert_content_line(line)}</p>'
            for line in content.split('+')
        ]

    def _parse_narrators(self, narrators: str):
        sprites: list[tuple[str, int, dict[str, str]]] = []
        speakers = []
        for narrator in narrators.split(';'):
            match = re.search(_speaker_regex, narrator)
            if match is not None:
                speakers.append(match.group(1))
                narrator = re.sub(_speaker_regex, '', narrator)
            sprite = _sprite_regex.match(narrator)
            if sprite is None:
                _warning('unrecognized sprite `%s` in `%s`', narrator, narrators)
                continue
            if sprite.group(1) == '' or sprite.group(2) == '':
                sprites.append(('', 0, {}))
            else:
                attrs = self._parse_effects(narrator)
                name = sprite.group(1)
                if '#' in name:
                    name, effect = name.split('#')
                    assert effect in _sprite_effects, f'unknown sprite effect {effect}'
                    attrs[_sprite_effects[effect]] = ''
                sprites.append((name, int(sprite.group(2)), attrs))
        return sprites, speakers[-1] if len(speakers) > 0 else ''

    def _parse_effects(self, effects: str):
        tags = re.findall(_effect_tag_regex, effects)
        parsed: dict[str, str] = dict((tag, '') for tag in tags)
        for tag in parsed.keys():
            if f'</{tag}>' in effects:
                try:
                    full_tag = f'<{tag}>'
                    start = effects.index(full_tag)
                    end = effects.index(f'</{tag}>')
                    parsed[tag] = effects[start + len(full_tag) : end]
                except ValueError:
                    _warning('tag %s wrong in `%s`', tag, effects)
        result = dict((k.lower(), v) for k, v in parsed.items())
        self.effect_tags.update(result.keys())
        return result

    def _get_sprite_info(self, character: str, sprite: int):
        if character in _wrong_sprites:
            if sprite in _wrong_sprites[character]:
                character, sprite = _wrong_sprites[character][sprite]
        c = self.external.characters.get(character.lower())
        if c is not None:
            s = c.get(str(sprite))
            if s is not None:
                return {
                    'name': str(sprite),
                    'url': f'/images/{s.path}',
                    'scale': -1,
                    'center': (-1, -1),
                }
        if character != '':
            _warning('sprite %s not found in %s', sprite, character)
        return {
            'name': sprite,
            'url': '',
            'scale': -1,
            'center': (-1, -1),
        }

    def _inject_lua_scripts(self):
        character_list = []
        for name, sprites in self._sprites.items():
            character_list.append({
                'name': name,
                'sprites': [
                    self._get_sprite_info(name, sprite_name)
                    for sprite_name in sprites.keys()
                ],
            })
        serialized = json.dumps(json.dumps(character_list, ensure_ascii=False), ensure_ascii=False)
        resource_urls = json.dumps(json.dumps(
            list(self._resources), ensure_ascii=False), ensure_ascii=False)
        return f'''```lua global
extern.defineCharacters({serialized})
extern.preloadResources({resource_urls})
```\n\n''';

    def _generate_bg_line(self, bg: str, effects: dict[str, str]):
        if bg == '':
            _warning('invalid bg in %s', self.filename)
        bg_path = self.external.backgrounds.get(bg)
        if bg_path is None or bg_path == '':
            _warning('background not found for `%s` in %s', bg, self.filename)
            bg_path = f'background/{bg}.png'
        self._update_class('night', 'night' in effects)
        night = 'night' if 'night' in effects else '!night'
        self._resources.add(f'/images/{bg_path}')
        return f':background[] :classes[{night}] /images/{bg_path}'

    def _split_line(self, line: str):
        # 大致行格式：
        # 角色1;角色二;……||演出信息: 第一行+第二行+……
        line = line.strip()
        if line == '':
            return None
        line = line.replace('：', ': ') # 中文冒号……
        if ':' not in line:
            _warning('unrecognized line `%s` in %s', line, self.filename)
            return None
        metadata, content = line.split(':', 1)
        if '||' not in metadata:
            _warning('unrecognized line metadata `%s` in %s', line, self.filename)
            return None
        narrator_string, effect_string = metadata.split('||', 1)
        return narrator_string, effect_string, content

    def record_missing_audio(self, type: str, name: str):
        self.missing_audio.setdefault(type, set()).add(name)

    def _process_effects(self, effect_string: str):
        # 在角色信息和演出信息里都会有类似 <BIN> 这种信息来记录对应的程序效果
        effects = self._parse_effects(effect_string)
        if 'bin' in effects:
            self._update_class('blank', False)
            self._markdown.append(self._generate_bg_line(effects['bin'], effects))
        if 'bgm' in effects:
            if effects['bgm'] not in self.external.audio:
                self.record_missing_audio('bgm', effects['bgm'])
            bgm = self.external.audio.get(effects['bgm'], f'bgm/{effects["bgm"]}.m4a')
            self._resources.add(f'/audio/{bgm}')
            self._markdown.append(f':audio[] /audio/{bgm}')
        if 'se' in effects or 'se1' in effects or 'se2' in effects or 'se3' in effects:
            se =  effects.get('se') or effects.get('se1') or effects.get('se2') or effects.get('se3') or ''
            if se not in self.external.audio:
                self.record_missing_audio('se', se)
            se = self.external.audio.get(se, f'se/{se}.m4a')
            self._resources.add(f'/audio/{se}')
            self._markdown.append(f':se[] /audio/{se}')
        if 'cg' in effects:
            self._update_class('blank', False)
            for i, cg in enumerate(effects['cg'].split(','), 1):
                if cg.strip() == '':
                    continue
                self._markdown.append(self._generate_bg_line(cg.strip(), effects))
                self._markdown.append('……' * i)

        # 一众的蒙版效果
        if '回忆' in effects:
            self._update_class('memories', True)
        # 关闭所有蒙版效果
        if '关闭蒙版' in effects:
            self._update_class('memories', False)
            self._update_class('night', False)

        # 没猜错的和，这两个都是永久性黑屏，直至新的背景出现
        if '黑屏1' in effects or '黑点1' in effects:
            self._update_class('blank', True)
        # 没猜错的话，这两个都是暂时性黑屏，一定时间后消失
        # 但的确不知道黑屏会不会挡住角色
        if '黑屏2' in effects or '黑点2' in effects:
            self._update_class('blank', False)
            self._update_class('fade-in', True)
        else:
            self._update_class('fade-in', False)
        return effects

    def _process_sprites(self, narrator_string: str):
        sprites, speaker = self._parse_narrators(narrator_string)
        for character, sprite, _ in sprites:
            if character not in self._sprites:
                self._sprites[character] = {}
            self._sprites[character][sprite] = ''
        sprite_string = '|'.join(f'{character}/{sprite}/{",".join(effects.keys())}'
                                 for character, sprite, effects in sprites)
        self._remote_narrators = set(
            character for character, _, attrs in sprites
            if '通讯框' in attrs or character in self._remote_narrators
        )
        remote_string = '|'.join(
            f'{character}/{sprite}' for character, sprite, _ in sprites
            if character in self._remote_narrators
        )
        return speaker, sprite_string, remote_string

    def _parse_va11(self, content: str):
        content, option_string = content.split('<va11>')
        rankings: list[str] = []
        for tag in ('perfect', 'good'):
            if tag not in option_string:
                assert tag == 'good'
                continue
            i = option_string.find(tag) + len(tag) + 1
            j = option_string.find('<', i)
            j = len(option_string) if j == -1 else j
            drinks = [_va11_drinks[int(drink_id)] for drink_id in option_string[i:j].split(',')]
            rankings.append(f'调制 {" 或 ".join(drinks)}')
        return content, rankings

    def decode(self):
        if self.filename in ['avgplaybackprofiles.txt', 'profiles.txt']:
            return None

        for line in self.script.split('\n'):
            self._class_updates = set()
            segments = self._split_line(line)
            if segments is None:
                continue
            narrator_string, effect_string, content = segments

            effects = self._process_effects(effect_string)
            speaker, sprite_string, remote_string = self._process_sprites(narrator_string)

            # 目前出现了 4 种选项：
            # cg: 点击屏幕 CG 的对应地方进行选择，我们直接不处理了，依次显示所有选项
            # c: 最简单的单次选项
            # r: 重复选项，似乎最后一个选项不重复……暂时也不处理
            # t: 重复选项，走完一个分支会返回来继续选……暂时也不处理
            # va11: 特殊，瓦尔哈拉联动
            option_type = ''
            options = []
            if '<cg>' in content:
                content = content.split('<cg>')[0]
                self._markdown.append('`branch = 0`')
            elif '<c>' in content:
                options = content.split('<c>')
                content, options = options[0], options[1:]
                option_type = 'c'
            elif '<r>' in content:
                options = content.split('<r>')
                content, options = options[0], options[1:]
                option_type = 'r'
            elif '<t>' in content:
                options = content.split('<t>')
                content, options = options[0], options[1:]
                option_type = 't'
            elif '<va11>' in content:
                content, options = self._parse_va11(content)
                option_type = 'c'
            if '分支' in effects:
                branching = f'`branch == 0 or branch == {effects["分支"]}` '
            else:
                branching = ''

            classes_string = '' if len(self._class_updates) == 0 else f':classes[{" ".join(self._class_updates)}] '
            tags = f'{branching}{classes_string}:sprites[{sprite_string}] :remote[{remote_string}] :narrator[{speaker}] :color[#fff]'
            self._markdown.extend(self._convert_content(content, tags))

            if len(options) != 0:
                for i, option in enumerate(options, 1):
                    self._markdown.append(f'- {"".join(self._convert_content(option))}\n\n  `branch = {i}`')
                if option_type == 't':
                    self._markdown.append('`branch = 0`')
        return self._inject_lua_scripts() + '\n\n'.join(self._markdown)


class Stories:
    directory: pathlib.Path
    gf_data_directory: pathlib.Path
    destination: pathlib.Path
    resource_file: pathlib.Path
    extracted: dict[str, pathlib.Path]
    content_tags: set[str]
    effect_tags: set[str]
    missing_audio: dict[str, set[str]]

    def __init__(self, directory: str, destination: str, *,
                 gf_data_directory: str | None = None,
                 root_destination: str | None = None,
                 lang: str = 'rus'):
        # Явно определяем базовые пути
        unpack_dir = pathlib.Path(directory).parent  # unpack/
        downloader_dir = pathlib.Path(directory)  # downloader/

        # Проверяем, если directory уже указывает на output/
        if downloader_dir.name == 'output':
            downloader_dir = downloader_dir.parent  # поднимаемся на уровень выше

        # Основные рабочие пути
        self.directory = downloader_dir
        self.destination = utils.check_directory(destination, create=True)

        # Путь к ресурсному файлу (учитываем output/)
        self.resource_file = pathlib.Path('unpack/downloader/output/asset_textavg.ab').resolve()

        # Пути к ресурсам (из unpack/)
        audio_path = unpack_dir.joinpath('audio', 'audio.json')
        bg_path = unpack_dir.joinpath('images', 'backgrounds.json')
        chars_path = unpack_dir.joinpath('images', 'characters.json')

        # Отладочный вывод
        print("\n[DEBUG] Path configuration:")
        print(f"Unpack directory: {unpack_dir}")
        print(f"Downloader directory: {downloader_dir}")
        print(f"Resource file: {self.resource_file} (exists: {self.resource_file.exists()})")
        print(f"Audio path: {audio_path} (exists: {audio_path.exists()})")
        print(f"Backgrounds path: {bg_path} (exists: {bg_path.exists()})")
        print(f"Characters path: {chars_path} (exists: {chars_path.exists()})\n")

        # Проверка существования файлов
        if not self.resource_file.exists():
            raise FileNotFoundError(f"Main resource file not found at: {self.resource_file}")
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio config not found at: {audio_path}")
        if not bg_path.exists():
            raise FileNotFoundError(f"Backgrounds config not found at: {bg_path}")
        if not chars_path.exists():
            raise FileNotFoundError(f"Characters config not found at: {chars_path}")

        self.resources = StoryResources(audio_path, bg_path, chars_path)

        # Путь к локализации
        self.gf_data_directory = unpack_dir.joinpath(f'gf-data-{lang}')
        print(f"GF Data directory: {self.gf_data_directory} (exists: {self.gf_data_directory.exists()})")

        # Остальная инициализация
        self.lang = lang
        self.content_tags = set()
        self.effect_tags = set()
        self.missing_audio = {'bgm': set(), 'se': set()}
        self.extracted = self.extract_all()
        self.copy_missing_pieces()

    def _decode(self, content: str, filename: str):
        transpiler = StoryTranspiler(self.resources, script=content, filename=filename)
        chunk = transpiler.decode()
        self.content_tags.update(transpiler.content_tags)
        self.effect_tags.update(transpiler.effect_tags)
        for k, v in transpiler.missing_audio.items():
            if k in self.missing_audio:
                self.missing_audio[k].update(v)
        return chunk

    def _decode_text_asset(self, text: TextAsset) -> str:
        """Улучшенный метод декодирования текстовых ассетов"""
        raw_bytes = text.m_Script.tobytes()

        # Попробуем UTF-8 сначала
        try:
            return raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            pass

        # Если не получилось, определим кодировку автоматически
        encoding = chardet.detect(raw_bytes)['encoding']
        try:
            return raw_bytes.decode(encoding or 'gbk')  # GBK как fallback для китайских текстов
        except UnicodeDecodeError:
            # Последняя попытка с заменой нечитаемых символов
            return raw_bytes.decode('utf-8', errors='replace')

    def extract_all(self):
        assets = UnityPy.load(str(self.resource_file))
        extracted: dict[str, pathlib.Path] = {}
        for o in assets.objects:
            if o.container is None or o.type.name != 'TextAsset':
                continue
            match = _text_asset_regex.match(o.container)
            if match is None:
                continue
            name = match.group(1)
            text = typing.cast(TextAsset, o.read())

            # Используем улучшенный метод декодирования
            content = self._decode_text_asset(text)

            path = self.destination.joinpath(*name.split('/'))
            os.makedirs(path.parent, exist_ok=True)
            with path.open('w', encoding='utf-8') as f:
                decoded_content = self._decode(content, name) or ''
                f.write(decoded_content)
            extracted[name] = path
        return extracted

    def copy_missing_pieces(self):
        if self.lang == 'rus':
            # Пробуем оба возможных пути
            for folder in ['formatted', 'asset']:
                directory = self.gf_data_directory.joinpath(folder, 'avgtxt')
                if directory.exists():
                    break
            else:
                _warning(f'Russian localization directory not found in {self.gf_data_directory}')
                return
        else:
            directory = self.gf_data_directory.joinpath('asset', 'avgtxt')
            manual_chapters.get_extra_stories(directory)
            manual_chapters.get_extra_anniversary_stories(directory)
        # else:
        #     directory = self.gf_data_directory.joinpath('asset', 'avgtxt')
        #     manual_chapters.get_extra_stories(directory)
        #     manual_chapters.get_extra_anniversary_stories(directory)

        for file in directory.glob('**/*.txt'):
            rel = file.relative_to(directory)
            name = str(rel)
            if name not in self.extracted:
                _warning('filling in %s', name)
                path = self.destination.joinpath(rel)
                path.parent.mkdir(exist_ok=True)
                with path.open('w', encoding='utf-8') as f:
                    with file.open('r', encoding='utf-8') as content:
                        try:
                            file_content = content.read()
                        except UnicodeDecodeError:
                            with file.open('rb') as content_bin:
                                raw_data = content_bin.read()
                                encoding = chardet.detect(raw_data)['encoding']
                                file_content = raw_data.decode(encoding or 'gbk')
                        f.write(self._decode(file_content, name) or '')
                self.extracted[name] = path

    def save(self):
        # Явно создаём папку stories
        stories_dir = self.destination.parent.joinpath('stories')
        stories_dir.mkdir(parents=True, exist_ok=True)  # parents=True для вложенных путей

        path = stories_dir.joinpath('stories.json')
        with path.open('w', encoding='utf-8') as f:
            json.dump(
                dict((k, str(p.relative_to(self.destination))) for k, p in self.extracted.items()),
                f,
                ensure_ascii=False,
                indent=2
            )
        _logger.info(f'Saved stories to {path}')