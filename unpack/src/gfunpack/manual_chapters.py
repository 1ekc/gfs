# -*- coding: utf-8 -*-
import dataclasses
import pathlib
import shutil
import subprocess
import typing
from urllib import request


@dataclasses.dataclass
class Story:
    name: str
    description: str
    files: list[str | tuple[str, str]]


@dataclasses.dataclass
class Chapter:
    name: str
    description: str
    stories: list[Story]


def safe_str(s):
    """Функция для исправления проблем с кодировкой строк"""
    if isinstance(s, bytes):
        try:
            return s.decode('utf-8')
        except UnicodeError:
            try:
                return s.decode('gb18030')
            except UnicodeError:
                try:
                    return s.decode('gbk')
                except UnicodeError:
                    return s.decode('latin1', errors='replace')
    return s


def _chapter_starting():
    return Chapter(
        name='Стартовый эпизод',
        description='Автзапуск, при первом входе в игру',
        stories=[
            Story(name=f'第 {i + 1} 节', description='',
                  files=[f'startavg/start{i}.txt'])
            for i in range(11 + 1)
        ],
    )


def _extra_stories_va11():
    return [
        (
            'Пособие по игре на диджериду',
            '',
            [
                ('-32-1-1.txt', 'Этап 1'),
                ('battleavg/-32-specialbattletips-fly.txt', 'Совет по игре 1'),
                ('battleavg/-32-specialbattletips-spdup.txt', 'Совет по игре 2'),
                ('-32-1-2first.txt', 'Пункт 2'),
                ('va11/va11_1.txt', 'Коктейли'),
            ],
        ),
        (
            'Подросток',
            '',
            [
                ('-32-2-1.txt', 'Этап 1'),
                ('-32-ext-2-1-point94524.txt', 'Событие'),
                ('-32-10-4-point12875.txt', 'Событие'),
                ('-32-2-2first.txt', 'Пункт 2'),
                ('va11/va11_2.txt', 'Коктейли'),
            ],
        ),
        (
            'Гангстер',
            '',
            [
                ('-32-3-1.txt', 'Этап 1'),
                ('-32-3-2first.txt', 'Пункт 2'),
                ('va11/va11_3.txt', 'Коктейли'),
            ],
        ),
        (
            'Звуковой удар',
            '',
            [
                ('-32-4-1.txt', 'Этап 1'),
                ('-32-ext-4-1.txt', 'Событие'),
                ('-32-12-4-point12932.txt', 'Событие'),
                ('-32-4-2first.txt', 'Пункт 2'),
                ('va11/va11_4.txt', 'Коктейли'),
            ],
        ),
        (
            'Куриное филе',
            '',
            [
                ('-32-5-1.txt', 'Этап 1'),
                ('-32-13-4-point12945.txt', 'Событие'),
                ('-32-5-2first.txt', 'Пункт 2'),
                ('va11/va11_5.txt', 'Коктейли'),
            ],
        ),
        (
            'Фобия публичных выступлений',
            '',
            [
                ('-32-6-1.txt', 'Этап 1'),
                ('-32-ext-6-1.txt', 'Событие'),
                ('-32-6-2first.txt', 'Пункт 2'),
                ('va11/va11_6.txt', 'Коктейли'),
            ],
        ),
        (
            'Момент истины (телешоу)',
            '',
            [
                ('-32-7-1.txt', 'Этап 1'),
                ('-32-15-4-point13027.txt', 'Событие'),
                ('-32-7-2first.txt', 'Пункт 2'),
                ('va11/va11_7.txt', 'Коктейли'),
            ],
        ),
        (
            'Последний дождь на Земле.',
            '',
            [
                ('-32-8-1.txt', 'Этап 1'),
                ('-32-16-4-point13052.txt', 'Событие'),
                ('-32-8-4-point12833.txt', 'Событие'),
                ('-32-8-2first.txt', 'Пункт 2'),
                ('-32-8-2end.txt', 'Пункт 3'),
                ('va11/va11_8.txt', 'Коктейли'),
            ],
        ),
    ]


def _extra_stories_cocoon():
    return [
        ('Прохладная ночь', '', ['-42-1-1first.txt']),
        ('Разговор в дождливую ночь', '', ['-42-1-2.txt']),
        ('Перевернутое изображение ', '', ['-42-2-1first.txt']),
        ('Вспоминать (прошлое)', '', ['-42-2-2.txt']),
        ('Неизвестный', '', [
            ('-42-3-1first.txt', 'Сюжетная линия'),
            ('-42-3-2.txt', 'Фрагмент памяти 1'),
            ('-42-3-3.txt', 'Фрагмент памяти 2'),
            ('-42-3-4.txt', 'Фрагмент памяти 3'),
            ('-42-3-5.txt', 'Фрагмент памяти 4'),
            ('-42-3-6.txt', 'Фрагмент памяти 5'),
            ('-42-3-7.txt', 'Фрагмент памяти 6'),
        ]),
        ('Слезы без следа', '', ['-42-3-8.txt']),
        ('Тень бабочки исчезает', '', ['-42-4-1first.txt']),
        ('Время, когда человек разрушает кокон', '', ['-42-4-2.txt']),
    ]


def _extra_stories_sac2045():
    return [
        ('Подарки от незнакомцев', '', ['-64-1-0.txt']),
        ('Каштановое дерево', '', ['-64-2-0.txt']),
        ('Доброе утро, «Новый мир».', '', ['-64-3-0.txt']),
        ('Легенда о картошке', '', ['-64-3-1.txt']),
        ('Отказ от Интернет-зависимости', '', ['-64-3-2.txt']),
        ('Эрл Грей Особый', '', ['-64-3-3.txt']),
        ('Виноградный сок', '', ['-64-3-4.txt']),
        ('Цветение сакуры и ты', '', ['-64-4-0.txt']),
        ('Комиссия майора', '', ['-64-5-1.txt']),
        ('Узники свободы', '', ['-64-5-2.txt']),
        ('Проследить свой путь', '', ['-64-6-0.txt']),
        ('Невозможность обновить', '', ['-64-6-1.txt']),
        ('Я желаю тебе всего счастья на свете.', '', ['-64-7-1.txt']),
        ('За групповым фото', '', ['-64-7-2.txt']),
        ('Ярость', '', ['-64-8-1.txt']),
        ('Призрак в канале', '', ['-64-8-2.txt']),
        ('Слезы в пудинге', '', ['-64-9-1.txt']),
        ('Это только моя война', '', ['-64-9-2.txt']),
        ('Закат на краю мира', '', ['-64-10-0.txt']),
    ]


def _extra_stories_gunslinger():
    return [
        ('Номер девять', '', ['-38-0-1.txt']),
        ('Калейдоскоп', '1', ['-38-1-1.txt']),
        ('Новая вилка', '2/2 Борьба', ['-38-2-1.txt', '-38-2-2first.txt', '-38-2-2round.txt', '-38-2-2end.txt']),
        ('Сумеречные звезды', '2 Интервал', ['-38-2-3.txt']),
        ('Многоактная игра Ⅰ', '3', ['-38-3-1.txt']),
        ('Многоактная игра II', '3/3 Борьба', ['-38-3-1first.txt', '-38-3-2round.txt', '-38-3-2end.txt']),
        ('Магия счастья', '3 Интервал', ['-38-3-3.txt']),
        ('Стрельбище в коммуне', '', ['battleavg/-38-specialbattletips.txt']),
        ('Пиноккио, который не умеет лгать Ⅰ', '4/4 Борьба', ['-38-4-1first.txt', '-38-4-1round.txt']),
        ('Пиноккио, который не умеет лгать II', '4 Поселковый участок', ['-38-4-1end.txt']),
        ('Бывший двор Ⅰ', '5/5 Борьба', ['-38-5-1first.txt', '-38-5-1round.txt']),
        ('Бывший двор II', '5 Поселковый участок', ['-38-5-1end.txt']),
        ('Hai capito', '6 Борьба', ['-38-6-1first.txt', '-38-6-1round.txt', '-38-6-1end.txt']),
        ('Идеальная гармония', '7 концовок', ['-38-7-1.txt']),
    ]


_extra_chapters: list[tuple[str, str, str, list]] = [
    ('-42', 'C.E. 2020 Тень бабочки в коконе', '2020', _extra_stories_cocoon()),
    ('-50', 'C.E. 2022 Выпечка с любовью', '2022', []),
    ('-52', 'C.E. 2022 Зона отчуждения "Рикан"', '2022', []),
    ('-59', 'C.E. 2023 Иллюзия', '2023', []),
    ('-61', 'C.E. 2023 Гражданский поход', '2023', []),
    ('-62', 'C.E. 2023 Лицензия! Вторичная загрузка', '2023', []),

    ('-8', 'Операция "Охота на кролика"', '《Мимеограф Асуки (серия видеоигр)》x《Греховная шестерка》Содержание ссылки',
     []),
    ('-14,-15', 'Индивидуальный практик', '《Академия Кракдаун》Содержание ссылки', []),
    ('-19,-20,-22', 'Дни Славы', '《DJMAX RESPECT》Содержание ссылки', []),
    ('-32', 'Вальгалла', '《VA-11 HALL-A》Содержание ссылки', _extra_stories_va11()),
    ('-38', 'Уличный спектакль', '《Девушка-》Содержание ссылки', _extra_stories_gunslinger()),
    ('-43', 'Черный прилив', '《Полное закрытие границ》Содержание ссылки', []),
    ('-46', 'Фронт маленького зла', '《Злой Бог и девочка с кухонной болезнью》Содержание ссылки', []),
    ('-57', 'Снежные волны отражают лик цветка', '《Saga Idol - это легенда, и она возвращается.》Содержание ссылки', []),
    ('-64', 'Вечность зеркального футляра', '《Атака на "Титаник"：SAC_2045》Содержание ссылки', _extra_stories_sac2045()),
    ('-73', 'Туманность Бабочки M20', '《Прорыв в темную зону》Содержание ссылки', []),
]


def _get_extra_chapters():
    return dict(
        (
            (i + 5000),
            Chapter(name, description,
                    [Story(s[0], s[1], s[2]) for s in stories]),
        )
        for i, (_, name, description, stories) in enumerate(_extra_chapters)
    )


def _get_extra_chapter_mapping():
    mapping: dict[str, int] = {}
    for i, chapter in enumerate(_extra_chapters):
        for j in chapter[0].split(','):
            mapping[j] = i + 5000
    return mapping


def get_recorded_chapters():
    chapters: dict[int, Chapter] = {
        0: _chapter_starting(),
    }
    id_mapping: dict[str, int] = {'0': 0}

    chapters.update(_get_extra_chapters())
    id_mapping.update(_get_extra_chapter_mapping())

    recorded_files: set[str] = set()
    for chapter in chapters.values():
        for story in chapter.stories:
            recorded_files.update((f if isinstance(f, str) else f[0])
                                  for f in story.files)
    return chapters, id_mapping, recorded_files


_attached_stories_motor_race = [
    '-31-3c3-1.txt',
    'battleavg/-31-specialbattletips-1.txt',
    'battleavg/-31-specialbattletips-3.txt',
    'battleavg/-31-specialbattletips-4.txt',
    'battleavg/-31-specialbattletips-5.txt',
    'battleavg/-31-specialbattletips-6.txt',
    'battleavg/-31-specialbattletips-fly.txt',
    'battleavg/-31-specialbattletips-spdup.txt',
    'battleavg/-31-specialbattletips-lose.txt',
    'battleavg/-31-specialbattletips-victory.txt',
]
_attached_stories: list[tuple[str, str, str]] = [
                                                    ('0-2-1.txt', '0-2-3round2.txt'),
                                                    ('-2-1-1.txt', '-2-1-4-point2207.txt'),

                                                    # Жареная любовь, белое торжество Описание
                                                    ('-50-1-4.txt', '-50-3-1.txt', 'Неправильный шоколад'),
                                                    ('-50-3-1.txt', '-50-3-2.txt', 'Льюис'),
                                                    ('-50-3-2.txt', '-50-3-3.txt', 'Соколы'),
                                                    ('-50-3-3.txt', '-50-3-4.txt', '79 стиль'),
                                                    ('-50-3-4.txt', '-50-3-5.txt', '97 стиль'),
                                                    ('-50-3-5.txt', '-50-3-6.txt', 'Охотник'),
                                                    ('-50-3-6.txt', '-50-3-7.txt', 'LWMMG'),
                                                    ('-50-3-7.txt', '-50-3-8.txt', 'K5'),
                                                    ('-50-3-8.txt', '-50-3-9.txt', 'Гарланд'),
                                                    ('-50-3-9.txt', '-50-3-10.txt', 'P22'),
                                                    ('-50-3-10.txt', '-50-3-11.txt', 'T77'),
                                                    ('-50-3-11.txt', '-50-3-12.txt', 'Блез Паскаль'),
                                                    # Запеченная любовь, маленький монстр
                                                    ('-50-1-4.txt', '-50-ext-1-4-1.txt', 'Десерт "Волшебные муравьи"'),
                                                    ('-50-ext-1-4-1.txt', '-50-ext-1-4-2.txt',
                                                     'Собачьи закуски Судного дня'),
                                                    ('-50-ext-1-4-2.txt', '-50-ext-1-4-3.txt',
                                                     'Калорийная бомба（шоколадные конфеты）'),
                                                    ('-50-ext-1-4-3.txt', '-50-ext-1-4-4.txt',
                                                     'Калорийная бомба（Чосулу）'),
                                                    ('-50-ext-1-4-4.txt', '-50-ext-1-4-5.txt', 'Какао Новый мир'),
                                                    ('-50-ext-1-4-5.txt', '-50-ext-1-4-6.txt', 'Чосулу'),
                                                    # Пекарня, любовь, шоколад
                                                    ('-50-1-3.txt', '-50-ext-1-3-2.txt', 'Лист с рецептами'),
                                                    ('-50-ext-1-3-2.txt', '-50-ext-1-3.txt', 'Лист с рецептами？'),
                                                    ('-50-ext-1-3.txt', '-50-ext-0-1.txt', 'Семья Минт'),
                                                    ('-50-ext-0-1.txt', '-50-ext-0-2.txt', 'Сладкая сабля'),
                                                    ('-50-ext-0-2.txt', '-50-ext-0-3.txt', 'Поцелуй судьбы'),
                                                    ('-50-ext-0-3.txt', '-50-ext-0-4.txt', 'Шоколадный дуэт'),
                                                    ('-50-ext-0-4.txt', '-50-ext-0-5.txt', 'Классическая память'),
                                                    ('-50-ext-0-5.txt', '-50-ext-0-6.txt', 'Какао Новый мир'),
                                                    ('-50-ext-0-6.txt', '-50-ext-0-7.txt', 'Чосулу'),

                                                    # Убежище Рикан
                                                    ('-52-1-1.txt', 'battleavg/-52-dxg.txt', 'Бить арбузы'),

                                                    # Правило слепого сплита: кажется, что это должна быть вторая еженедельная смена цели?
                                                    ('-7-1-3round1.txt', '-7-1-3round2.txt', 'Пункт2.5'),
                                                    ('-7-2-3round1.txt', '-7-2-3round2.txt', 'Пункт.5'),
                                                    ('-7-3-3round1.txt', '-7-3-3round2.txt', 'Пункт.5'),
                                                    ('-7-4-3round1.txt', '-7-4-3round2.txt', 'Пункт.5'),

                                                    # Упорядоченная турбулентность
                                                    ('-24-2-1.txt', '-24-2-2.txt'),
                                                    ('-24-3-2first.txt', '-24-3-2.txt'),
                                                    ('-24-4-2first.txt', '-24-4-2.txt'),
                                                    ('-24-6-1.txt', '-24-6-2.txt'),
                                                    ('-24-7-2first.txt', '-24-7-2.txt'),
                                                    ('-24-8-2first.txt', '-24-8-2.txt'),
                                                    ('-24-9-2first.txt', '-24-9-2.txt'),
                                                    ('-24-10-2first.txt', '-24-10-2.txt'),
                                                    ('-24-11-2first.txt', '-24-11-2.txt'),
                                                    ('-24-12-2first.txt', '-24-12-2.txt'),
                                                    ('-24-13-2first.txt', '-24-13-2.txt'),
                                                    ('-24-14-2first.txt', '-24-14-2.txt'),
                                                    ('-24-15-1.txt', '-24-15-2first.txt'),
                                                    ('-24-15-2first.txt', '-24-15-2.txt'),

                                                    # Ссылки на деление
                                                    # ('-33-59-4-point13290.txt', '-33-59-4-point80174.txt'), # Одинаковые события в обеих точках
                                                    ('-33-59-4-point13290.txt', 'battleavg/-33-24-1first.txt'),

                                                    # Поляризованный свет
                                                    ('-36-5-ex.txt', 'battleavg/-36-specialbattletips.txt'),
                                                ] + [  # Настольная игра "Гетеродинные гонки" Эпизоды
                                                    (prev, after)
                                                    for prev, after in zip(
        _attached_stories_motor_race[:-1],
        _attached_stories_motor_race[1:],
    )
                                                ]
_attached_events: list[tuple[str, Story]] = [
    # Звено деления: всепоглощающее море цветов-борьба
    ('-33-42-1first.txt', Story(
        name='Море цветов, которое поглощает все - Битва',
        description='Инструкции к мини-игре',
        files=['battleavg/-33-44-1first.txt'],
    )),
    # День апрельских дураков
    ('1-1-1.txt', Story(
        name='Тренировки - выпуск "День апрельского дурака"',
        description='С возвращением, отец-настоятель.',
        files=['always-404-1-1-1.txt', 'battleavg/always-404-1-1-2.txt', 'always-404-1-1-3.txt'],
    )),
    # Снежные волны, отражающие лицо цветка
    ('-57-0-1.txt', Story(
        name='День 1 - утро',
        description='',
        files=[
            ('-57-a1-1.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-c1-1.txt', 'Студия пения До-ре-ми'),
            ('-57-w1-1.txt', 'Бани. Гоббл-гоббл-гоббл'),
            ('-57-x1-1.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-d1-1.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-1-1.txt', Story(
        name='День 1 - Ночь',
        description='',
        files=[
            ('-57-w1-2.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-x1-2.txt', 'Cтудия пения До-ре-ми'),
            ('-57-a1-2.txt', 'Бани. Гоббл-гоббл-гоббл.'),
            ('-57-d1-2.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-l1-2.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-1-2.txt', Story(
        name='День 2 - утро',
        description='',
        files=[
            ('-57-x2-1.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-y2-1.txt', 'Cтудия пения До-ре-ми'),
            ('-57-c2-1.txt', 'Бани. Гоббл-гоббл-гоббл.'),
            ('-57-l2-1.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-d2-1.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-2-1.txt', Story(
        name='День 2 - Ночь',
        description='',
        files=[
            ('-57-l2-2.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-c2-2.txt', 'Cтудия пения До-ре-ми'),
            ('-57-w2-2.txt', 'Бани. Гоббл-гоббл-гоббл.'),
            ('-57-x2-2.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-y2-2.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-2-2.txt', Story(
        name='День 3 - утро',
        description='',
        files=[
            ('-57-l3-1.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-y3-1.txt', 'Cтудия пения До-ре-ми'),
            ('-57-w3-1.txt', 'Бани. Гоббл-гоббл-гоббл.'),
            ('-57-x3-1.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-d3-1.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-3-1.txt', Story(
        name='День 3 - Ночь',
        description='',
        files=[
            ('-57-3-point1.txt', 'Cтудия пения До-ре-ми'),
            ('-57-3-point2.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
        ],
    )),
    ('-57-3-2.txt', Story(
        name='День 4 - утро',
        description='',
        files=[
            ('-57-a4-1.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-c4-1.txt', 'Cтудия пения До-ре-ми'),
            ('-57-y4-1.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-4-1.txt', Story(
        name='День 4 - Ночь',
        description='',
        files=[
            ('-57-l4-2.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-y4-2.txt', 'Cтудия пения До-ре-ми'),
            ('-57-a4-2.txt', 'Бани. Гоббл-гоббл-гоббл.'),
            ('-57-x4-2.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-d4-2.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-4-2.txt', Story(
        name='День 5 - утро',
        description='',
        files=[
            ('-57-l5-1.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-a5-1.txt', 'Cтудия пения До-ре-ми'),
            ('-57-w5-1.txt', 'Бани. Гоббл-гоббл-гоббл.'),
            ('-57-x5-1.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-d5-1.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-5-1.txt', Story(
        name='День 5 - Ночь',
        description='',
        files=[
            ('-57-w5-2.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-d5-2.txt', 'Cтудия пения До-ре-ми'),
            ('-57-x5-2.txt', 'Бани. Гоббл-гоббл-гоббл.'),
            ('-57-l5-2.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-c5-2.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-5-2.txt', Story(
        name='День 6 - утро',
        description='',
        files=[
            ('-57-a6-1.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-c6-1.txt', 'Cтудия пения До-ре-ми'),
            ('-57-w6-1.txt', 'Бани. Гоббл-гоббл-гоббл.'),
            ('-57-x6-1.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-d6-1.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-6-1.txt', Story(
        name='День 6 - Ночь',
        description='',
        files=[
            ('-57-6-point1.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-6-point2.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
    ('-57-6-2.txt', Story(
        name='День 7 - утро',
        description='',
        files=[
            ('-57-a7-1.txt', 'Бальный зал. Голова вверх, грудь вперед, бедра в стороны'),
            ('-57-l7-1.txt', 'Cтудия пения До-ре-ми'),
            ('-57-d7-1.txt', 'Бани. Гоббл-гоббл-гоббл.'),
            ('-57-w7-1.txt', 'Ресторан быстрого питания. Зи-ва-виш'),
            ('-57-y7-1.txt', 'Добро пожаловать в магазин "Удобство"'),
        ],
    )),
]

_extra_chapter_mapping = {
    '-27': '-24',  # Упорядоченная турбулентность: спасение от урагана
    '-45': '-24',  # Ураганное спасение # Возрождение
    '-99': '-58',  # Медленный шок END
}


def add_extra_chapter_mappings(id_mapping: dict[str, int]):
    for extra, mapping in _extra_chapter_mapping.items():
        id_mapping[extra] = id_mapping[mapping]


_manual_processed = set().union(
)


def is_manual_processed(file: str):
    return file in _manual_processed


def manually_process(chapters: dict[int, Chapter], id_mapping: dict[str, int], mapped_files: set[str]):
    # Сага
    c = chapters[id_mapping['-57']]
    specials = {
        'Источник вишни': ['Lержаться подальше！', '吉光片羽', '樱之蕊'],
        'Благоприятный свет и несколько мимолетных мгновений': ['Riot Radio！', 'Воспоминания！', 'Подарок на выпускной'],
        'Мидзуно Аи': ['Дождливый двор', 'Лунная коса', '闪耀之爱'],
        'Коно Дзюнко': ['Мнимые гости в чужой стране', 'Когда начала светить луна?',
                        'Насколько хватает глаз из-за туманных волн, с другой стороны - запад и восток'],
        'Югири': ['Путешественник во времени', 'Звуки моря', 'Пока солнце не сядет'],
        'Лили Хошикава': ['Прекрасный незнакомец', 'Оперативник Kingsman', 'Проходит много времени'],
        'Таэ Ямада': ['Чудесное ночное путешествие', 'Даритель', '“Пожалуйста, не уходите.”'],
    }
    endings = [
        'Ночь смеха и слез',
        'Флуоресцентная цветная ночь',
        'Ночь, оседлавшая ветер',
        'Серая ночь.',
        'Свободный фон',
        'Песня продолжается и продолжается，танец продолжается и продолжается',
        'Расстояние от плеча до плеча',
        'Давай, киллер! ',
        'Пик!Рампаж! ',
        'Вдохновение!Родники! ',
    ]
    files: dict[str, str] = {}

    # Применяем safe_str ко всем именам в specials
    normalized_specials = {}
    for character, story_names in specials.items():
        normalized_character = safe_str(character)
        normalized_names = [safe_str(name) for name in story_names]
        normalized_specials[normalized_character] = normalized_names

    names = set(n for ns in normalized_specials.values() for n in ns)

    # Применяем safe_str к именам в c.stories
    for s in c.stories:
        normalized_name = safe_str(s.name)
        if normalized_name in names:
            assert len(s.files) == 1
            file = s.files[0]
            assert isinstance(file, str)
            files[normalized_name] = file

    # Фильтруем истории
    c.stories = [s for s in c.stories if safe_str(s.name) not in names]

    # Обрабатываем концовки
    for s in c.stories:
        normalized_name = safe_str(s.name)
        if normalized_name in endings:
            s.description = f'结局 {endings.index(s.name) + 1}'

    # Добавляем специальные истории
    for character, stories in normalized_specials.items():
        file_list = []
        for name in stories:
            if name in files:
                file_list.append((files[name], name))
            else:
                # Логируем отсутствующие файлы
                print(f"Warning: Missing file for {name} in character {character}")

        c.stories.append(Story(
            name=character,
            description='剧情',
            files=file_list,
        ))


def _index_of_file(story: Story, file: str):
    for i, f in enumerate(story.files):
        if isinstance(f, str):
            if f == file:
                return i
        else:
            if f[0] == file:
                return i
    raise ValueError(f'{file} not found in {story}')


def post_insert(chapters: dict[int, Chapter], mapped_files: set[str]):
    stories: dict[str, tuple[Chapter, Story]] = {}
    for chapter in chapters.values():
        for story in chapter.stories:
            for file in story.files:
                stories[file if isinstance(file, str) else file[0]] = (chapter, story)
    for attachment in _attached_stories:
        file, attached = attachment[0:2]
        assert attached not in mapped_files, attached
        c, story = stories[file]
        assert isinstance(story.files[0], str)
        stories[attached] = (c, story)
        story.files.insert(
            _index_of_file(story, file) + 1,
            attached if len(attachment) == 2 else (attached, attachment[2]),
        )
        mapped_files.add(attached)
    for file, attached in _attached_events:
        assert all(
            f not in mapped_files and f[0] not in mapped_files for f in attached.files
        ), [f for f in attached.files if f in mapped_files or f[0] in mapped_files]
        c, story = stories[file]
        c.stories.insert(c.stories.index(story) + 1, attached)
        for f in attached.files:
            if not isinstance(f, str):
                f = f[0]
            stories[f] = (c, attached)
            mapped_files.add(f)


def get_block_list():
    return set(
        [
            '0-0-0.txt',  # Пустое, "Альтернативный сюжет"
            '0-0-1.txt',  # Blank, "Альтернативный учебник".
            'profiles.txt',
            'avgplaybackprofiles.txt',

            # Действия с кубиком Рубика, например, -6-1-1 и -1-1-1 одинаковы ......
            '-6-1-1.txt',
            '-6-1-2first.txt',
            '-6-2-1.txt',
            '-6-2-2end.txt',
            '-6-2-2first.txt',
            '-6-3-1.txt',
            '-6-3-2end.txt',
            '-6-3-2first.txt',
            '-6-4-1.txt',
            '-6-4-2end.txt',
            '-6-4-2first.txt',

            # Деление ссылок, два события с одинаковым содержанием
            '-33-59-4-point80174.txt',

            # Различные советы по созданию реплик Лысой Дыры
            '-39-ex1-4-point91502.txt',
            '-55-ext.txt',
            '-60-tips.txt',
            '-63-tips.txt',
            '-65-tips.txt',
            '-65-tips2.txt',
            '-404-ext-1-1.txt',
            # Ураганное спасение # Возрождение (-45 -> -24)
            '-45-ext-04.txt',
            '-45-ext-01.txt',
            '-45-ext-02.txt',
            '-45-ext-03.txt',

            # Правила завязывания глаз: они на английском языке
            '-7-1-4-point3498.txt',
            '-7-2-4-point3342.txt',
            '-7-3-4-point3533.txt',
            '-7-4-4-point3612.txt',

            # Игра слов, это просто описание того, как играть.
            '-38-ex-point91820.txt',
            '-38-ex-point91829.txt',
            '-38-ex1-5-point91849.txt',
            '-38-ex1-2-point91865.txt',
            '-38-2-4first.txt',
            # 和 '-38-2-1.txt', '-38-2-2first.txt' Повторите, используя версию с исправленными опечатками.

            # Одна монета, советы по игре
            '-49-3-1-point94780.txt',
            '-49-ext-1-1.txt',
            '-49-ext-4-1.txt',

            # Переворот ронина, советы по игре
            '-47-2-skill-1.txt',
            '-47-2-skill-2.txt',
            '-47-2-skill-3.txt',

            # Жареная любовь, "текст будет заменен" #
            '-50-ext-0.txt',
            '-50-ext-1-4-0.txt',

            # Убежище Рикан, текст подсказки к игре
            '-52-ext-2-1.txt',
            '-52-ext-3-1.txt',
            '-52-ext-4-1.txt',
            '-52-ext-5-1.txt',
            '-52-ext-5-2.txt',
            '-52-ext-5-3.txt',
            '-52-pachinko0.txt',
            '-52-pachinko1.txt',
            '-52-pachinko2.txt',
            '-52-pachinko3.txt',
            '-52-pachinko4.txt',
            '-52-pachinko5.txt',
            '-52-pachinko6.txt',
            '-52-pachinko7.txt',
            '-52-pachinko8.txt',
            '-52-pachinko9.txt',
            '-52-pachinkornd2.txt',

            # Лицензия!Вторичная загрузка
            '-62-sangvis-tutorial-4kill.txt',
            '-62-sangvis-tutorial-8kill.txt',
            '-62-sangvis-tutorial-missionstart.txt',

            # Saga Link
            '-57-ext-5.txt',
            '-57-ext-6.txt',
            '-57-ext-7-00.txt',
            '-57-ext-7-01.txt',
            '-57-ext-7-11.txt',
            '-57-ext-7-12.txt',
            '-57-ext-7-13.txt',
            '-57-ext-7-14.txt',
            '-57-ext-7-15.txt',
            '-57-ext-7-16.txt',
            '-57-ext-7-17.txt',
            '-57-ext-7-24.txt',
            '-57-ext-7-26.txt',
            '-57-ext-7-27.txt',
            '-57-ext-7-36.txt',
            '-57-ext-7-41.txt',
            '-57-ext-7-42.txt',
            '-57-ext-7-43.txt',
            '-57-ext-7-44.txt',
            '-57-ext-7-45.txt',
            '-57-ext-7-46.txt',
            '-57-ext-7-47.txt',
            '-57-ext-7-48.txt',
            '-57-ext-7-51.txt',
            '-57-ext-7-54.txt',
            '-57-ext-7-57.txt',
            '-57-ext-7-61.txt',
            '-57-ext-7-62.txt',
            '-57-ext-7-63.txt',
            '-57-ext-7-64.txt',
            '-57-ext-7-65.txt',
            '-57-ext-7-66.txt',
            '-57-ext-7-67.txt',
            '-57-ext-7-68.txt',
            '-57-ext-7-71.txt',
            '-57-ext-7-74.txt',
            '-57-ext-7-77.txt',
            '-57-ext-7-78.txt',
            '-57-ext-7-81.txt',
            '-57-ext-7-82.txt',
            '-57-ext-7-83.txt',
            '-57-ext-7-84.txt',
            'battleavg/-57-dance.txt',
            'battleavg/-57-sing.txt',
            'battleavg/-57-work.txt',

            # SAC 2045
            '-64-ext-1.txt',
            '-64-ext-2.txt',
            '-64-ext-3.txt',

            # 22 большая дилемма
            '-69-ext-1.txt',

            # двойное неупорядоченное число
            '-41-3-4-point71201.txt',
            '-41-3-4-point71305.txt',
            '-41-3-4-point72006.txt',
            '-41-2-4-ex1point91924.txt',
            '-41-2-4-ex1point91926.txt',
            '-41-2-4-ex2point92278.txt',
            '-41-2-4-ex3point92127.txt',
            '-41-2-4-ex4point92161.txt',
            '-41-2-4-ex5point92614.txt',
            '-41-2-4-ex6point92372.txt',
            '-41-3-4-ex1point91991.txt',
            '-41-3-4-ex2point91990.txt',
            '-41-3-4-ex3point92264.txt',
            '-41-3-4-ex4point92396.txt',
            '-41-3-4-ex5point92254.txt',
            '-41-3-4-ex6point92335.txt',
        ]
    )


def get_extra_stories(destination: pathlib.Path):
    downloadables = [
        # (
        #     'https://gcore.jsdelivr.net/gh/gf-data-tools/gf-data-ch@42b067b833a5e10a8f9cedf198fe182f1df122f1/asset/avgtxt/-52-e-1.txt',
        #     '-52-e-1-springfield.txt',
        # ),
    ]
    for url, file in downloadables:
        path = destination.joinpath(file)
        if not path.is_file():
            request.urlretrieve(url, path)


def get_extra_anniversary_stories(destination: pathlib.Path):
    directory = pathlib.Path('GFLData', 'ch', 'text', 'avgtxt', 'anniversary')
    old_directory = pathlib.Path('GirlsFrontlineData', 'zh-CN', 'asset_textes', 'avgtxt', 'anniversary')
    if not pathlib.Path('GFLData').is_dir():
        subprocess.run([
            'git', 'clone', 'https://github.com/randomqwerty/GFLData.git',
        ], stdout=subprocess.DEVNULL).check_returncode()
    if not pathlib.Path('GirlsFrontlineData').is_dir():
        subprocess.run([
            'git', 'clone', 'https://github.com/Dimbreath/GirlsFrontlineData.git',
        ], stdout=subprocess.DEVNULL).check_returncode()
    if not destination.joinpath('anniversary4').is_dir():
        subprocess.run([
            'git', 'checkout', '41793e107cb4697de10ac5bf507f1909f1c47030',
        ], cwd='GirlsFrontlineData').check_returncode()
        shutil.copytree(old_directory, destination.joinpath('anniversary4'))
    if not destination.joinpath('anniversary5').is_dir():
        subprocess.run([
            'git', 'checkout', '9d0dae0066ccf1bc9e32abf35401d5ef7eaf7746',
        ], cwd='GFLData').check_returncode()
        shutil.copytree(directory, destination.joinpath('anniversary5'))
    if not destination.joinpath('anniversary6').is_dir():
        subprocess.run([
            'git', 'checkout', '93e4c8dd9a236f57b6869cf5c88c93c1cc79255c',
        ], cwd='GFLData').check_returncode()
        shutil.copytree(directory, destination.joinpath('anniversary6'))
        # 四周年的残留？
        dup = destination.joinpath('anniversary6/55-102686.txt')
        if dup.is_file():
            dup.unlink()


def fill_in_chapter_info(main: list[Chapter], events: list[Chapter]):
    assert main[1].description == '0'
    chpt_zero = main[1]
    main.remove(chpt_zero)
    assert main[4].description == '4'
    main.insert(5, chpt_zero)
    mapping = {
        0: 'Пролог',
        1: 'Пробуждение',
        2: 'Эхо',
        3: 'Тишина',
        4: 'Сообщение',
        5: 'Разжигание',
        6: 'Комета',
        7: 'Партнер',
        8: 'Искра',
        9: 'Потерянный',
        10: 'Чистилище',
        11: 'Охота',
        12: 'Перерыв',
        13: 'Обливион',
    }
    for c in main:
        if c.description.isdigit():
            i = int(c.description)
            if i in mapping:
                c.description = mapping[i]
            else:
                c.description = ''