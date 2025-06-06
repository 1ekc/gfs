import dataclasses
import logging
import pathlib
import re
import typing

import UnityPy
from UnityPy import Environment
from UnityPy.classes import GameObject, MonoBehaviour, MonoScript

from gfunpack import utils

_logger = logging.getLogger('gfunpack.prefabs')
_warning = _logger.warning


@dataclasses.dataclass
class DialoguePicDetails:
    name: str
    path_id: int
    alpha_path_id: int
    pic_name: str = ''
    scale: float = -1.0
    offset: tuple[float, float] = (0.0, 0.0)


_path_regex = re.compile('^assets/resources/dabao/avgpicprefabs/([^/]+)\\.prefab$')


class Prefabs:
    directory: pathlib.Path

    resource_files: list[pathlib.Path]

    details: dict[str, list[DialoguePicDetails]]

    def __init__(self, directory: str) -> None:
        self.directory = utils.check_directory(directory)
        self.resource_files = list(self.directory.glob('*prefab*.ab'))
        prefabs = [UnityPy.load(str(path)) for path in self.resource_files]
        self.details = self.load_prefabs(prefabs)

    def _collect_dialogue_pic_holders(self, prefabs: list[Environment]):
        objects: dict[int, MonoBehaviour] = {}
        for prefab in prefabs:
            for obj in prefab.objects:
                if obj.type.name != 'MonoBehaviour':
                    continue
                data = typing.cast(MonoBehaviour, obj.read())
                try:
                    script: MonoScript = data.m_Script.read()
                    if script.name == 'DialoguePicHolder':
                        assert obj.path_id not in objects
                        assert data.m_GameObject.file_id == 0
                        objects[obj.path_id] = data
                except AssertionError as e:
                    _warning('something went wrong (%s): %s: %s', prefab.path, obj.path_id, e)
                except AttributeError:
                    pass
        return objects

    @classmethod
    def _match_container_path(cls, path: str) -> str | None:
        match = _path_regex.match(path)
        return None if match is None else match.group(1)

    def _collect_game_objects(self, prefabs: List[GameObject]) -> Dict[int, GameObject]:
        objects = {}
        for prefab in prefabs:
            # Используем m_Name вместо name
            if hasattr(prefab, 'm_Name') and prefab.m_Name and prefab.m_Name != '':
                objects[prefab.path_id] = prefab
            # Рекурсивный обход дочерних объектов
            if hasattr(prefab, 'm_Components'):
                for component in prefab.m_Components:
                    child_objects = self._collect_game_objects([component])
                    objects.update(child_objects)
        return objects

    @classmethod
    def _collect_pic_details(cls, name: str, pic: MonoBehaviour):
        pics: list[GameObject | None] | None = pic.get('pic')
        alphaPics: list[GameObject | None] | None = pic.get('picAlpha')
        assert pics is not None
        assert alphaPics is not None
        if name in {'Empty', 'backgroundFrame'}:
            assert len(alphaPics) == 0
        else:
            assert len(pics) == len(alphaPics), f'{name} {len(pics)} {len(alphaPics)}'
        scales = pic.get('orderScale') or []
        if len(pics) >= len(scales):
            scales.extend([None] * (len(pics) - len(scales)))
        else:
            _warning('curious pic holder %s with %d pics and %d orderScales', name, len(pics), len(scales))
            pics.extend([None] * (len(scales) - len(pics)))
        assert len(pics) == len(scales), f'{pic.read_typetree()}'

        details: list[DialoguePicDetails] = []
        for i, (p, alpha, scale) in enumerate(zip(pics, alphaPics, scales)):
            avg_offset = scale.avgOffset if scale else None
            if avg_offset is None:
                offset = (0.0, 0.0)
            else:
                offset = (avg_offset.x, avg_offset.y)
            if p is None:
                _warning('%s (%d) no path_id available', name, i)
            details.append(DialoguePicDetails(
                name=name,
                path_id=p.path_id if p is not None else 0,
                alpha_path_id=alpha.path_id if alpha is not None else 0,
                pic_name=scale.picname if scale else '',
                scale=scale.scale if scale else -1.0,
                offset=offset,
            ))
        return details

    def load_prefabs(self, prefabs: list[Environment]):
        dialogue_pics = self._collect_dialogue_pic_holders(prefabs)
        objects = self._collect_game_objects(prefabs)
        details: dict[str, list[DialoguePicDetails]] = {}
        for pic in dialogue_pics.values():
            parent_id = pic.m_GameObject.path_id
            if parent_id in objects:
                name = objects[parent_id].name
            elif pic.container is not None:
                _warning('%s game object not found', pic.container)
                name = self._match_container_path(pic.container)
                assert name is not None
                name = name.capitalize()
            else:
                name = None
                _warning('curious dialogue pic holder %d', pic.path_id)

            if name is not None:
                pic_details = self._collect_pic_details(name, pic)
                if pic_details is not None:
                    details[name] = pic_details
        return details