import json
import logging
import pathlib
import shutil
import subprocess
import threading
import zipfile

import tqdm

from gfunpack import utils

_logger = logging.getLogger('gfunpack.utils')
_info = _logger.info
_warning = _logger.warning


def _test_vgmstream():
    try:
        subprocess.run([
            'vgmstream-cli',
            '-V',
        ], stdout=subprocess.DEVNULL)
    except FileNotFoundError:
        raise FileNotFoundError('vgmstream-cli is required to unpack sound files')


def _extract_zip(path: pathlib.Path, directory: pathlib.Path, force: bool = False):
    with zipfile.ZipFile(path) as z:
        extracted: list[pathlib.Path] = []
        for file in z.filelist:
            output = directory.joinpath(file.filename)
            if force or not (
                    output.is_file() # *.acb.bytes
                    or output.with_suffix('').is_file() # *.acb
                    or output.with_suffix('').with_suffix('.wav').is_file() # *.wav
                    or output.with_suffix('').with_suffix('.m4a').is_file() # *.m4a
            ):
                z.extract(file, directory)
                extracted.append(output)
        return extracted


def _test_ffmpeg():
    try:
        subprocess.run([
            'ffmpeg',
            '-h',
        ], stdout=subprocess.DEVNULL).check_returncode()
    except FileNotFoundError:
        raise FileNotFoundError('ffmpeg is required to transcode audio files')


def _transcode_files(files: list[pathlib.Path], force: bool, concurrency: int, clean: bool,
                     batch_size: int = -1, bar: tqdm.tqdm | None = None):
    semaphore = threading.Semaphore(concurrency)
    def transcode(file: pathlib.Path, output: pathlib.Path):
        nonlocal clean, force, semaphore
        if force or not output.is_file():
            subprocess.run([
                'ffmpeg',
                '-hide_banner',
                '-loglevel',
                'error',
                '-i',
                file,
                output,
            ]).check_returncode()
        if clean:
            file.unlink()
        semaphore.release()

    converted: dict[str, pathlib.Path] = {}
    for file in files:
        semaphore.acquire()
        output = file.with_suffix('.m4a')
        threading.Thread(target=transcode, args=(file, output)).start()
        converted[file.stem] = output
        if bar:
            if batch_size == -1 or batch_size == len(files):
                bar.update()
            else:
                bar.set_description(f'{file.stem}')

    if bar and batch_size != -1 and batch_size != len(files):
        bar.update(batch_size)

    for _ in range(concurrency):
        semaphore.acquire()
    return converted


def _extract_acb_to_wav(dat: pathlib.Path, destination: pathlib.Path,
                        semaphore: threading.Semaphore | None = None,
                        force: bool = False,
                        clean: bool = True):
    try:
        acb_audios = _extract_zip(dat, destination, force=force)
        assert len(acb_audios) <= 1
        if len(acb_audios) == 1:
            acb = acb_audios[0]
            assert acb.suffix == '.bytes'
            acb = acb.rename(acb.with_suffix(''))
            subprocess.run([
                'vgmstream-cli',
                acb,
                '-o',
                destination.joinpath('?n.wav'),
                '-S',
                '0',
            ], stdout=subprocess.DEVNULL).check_returncode()
            if clean:
                acb.unlink()
        else:
            acb = None
        return acb
    finally:
        if semaphore is not None:
            semaphore.release()


class BGM:
    directory: pathlib.Path

    destination: pathlib.Path

    se_destination: pathlib.Path

    resource_files: list[pathlib.Path]

    se_resource_file: pathlib.Path

    extracted: dict[str, pathlib.Path]

    force: bool

    concurrency: int

    clean: bool

    def __init__(self, directory: str, destination: str,
                 force: bool = False, concurrency: int = 8, clean: bool = True) -> None:
        self.directory = utils.check_directory(directory)
        self.destination = utils.check_directory(pathlib.Path(destination).joinpath('bgm'), create=True)
        self.se_destination = utils.check_directory(pathlib.Path(destination).joinpath('se'), create=True)
        self.force = force
        self.concurrency = concurrency
        self.clean = clean
        self.resource_files = list(f for f in self.directory.glob('*.acb.dat') if f.name != 'AVG.acb.dat')
        self.se_resource_file = self.directory.joinpath('AVG.acb.dat')
        _test_ffmpeg()
        self.extracted = self.extract_and_convert()

    def extract_all(self, resource_files: list[pathlib.Path]):
        _test_vgmstream()
        semaphore = threading.Semaphore(self.concurrency)
        for file in resource_files:
            semaphore.acquire()
            threading.Thread(
                target=_extract_acb_to_wav,
                args=(file, self.destination, semaphore, self.force, self.clean),
            ).start()
        for _ in range(self.concurrency):
            semaphore.acquire()
        return list(self.destination.glob('*.wav'))

    def _get_audio_template(self):
        content = utils.read_text_asset(self.directory.joinpath('asset_textes.ab'), 'assets/resources/textdata/audiotemplate.txt')
        mapping: dict[str, str] = {}
        for line in (l.strip() for l in content.split('\n')):
            if '//' in line:
                comment_index = line.index('//')
                line = line[:comment_index].strip()
            if line == '' or '|' not in line:
                continue
            fields = line.split('|')
            assert len(fields) >= 4 or (len(fields) == 3 and fields[1] in [
                'Skip',
                'UI_dsExstart',
                'UI_dsMissionStart',
                'UI_dsenemy',
                'UI_dsLogin',
                'BGM_PAUSE',
                'BGM_UNPAUSE',
            ]), line
            name, file = fields[1:3]
            mapping[name] = file
        return mapping

    def extract_and_convert(self):
        _info('extracting se audio')
        _extract_acb_to_wav(self.se_resource_file, self.se_destination, None, self.force, self.clean)
        files = _transcode_files(
            list(self.se_destination.glob('*.wav')),
            self.force,
            self.concurrency,
            self.clean,
        )
        _info('extracting bgm audio')
        bar = tqdm.tqdm(total=len(self.resource_files))
        batch_count = min(self.concurrency * 8, 32) if self.clean else len(self.resource_files)
        for i in range(0, len(self.resource_files), batch_count):
            batch = self.resource_files[i: i + batch_count]
            files.update(_transcode_files(
                self.extract_all(batch),
                self.force,
                self.concurrency,
                self.clean,
                len(batch),
                bar,
            ))
        bar.close()
        files.update((existing.stem, existing) for existing in self.destination.glob('*.m4a'))
        files.update((existing.stem, existing) for existing in self.se_destination.glob('*.m4a'))

        for audio_name, file in [item for item in files.items() if ';' in item[0]]:
            audio_names = [name.strip() for name in audio_name.split(';')]
            for name in audio_names:
                f = file.with_stem(name + '.m4a')
                shutil.copyfile(file, f)
                files[name] = f
            files.pop(audio_name)
            file.unlink()

        name_mapping = self._get_audio_template()
        mapping: dict[str, pathlib.Path] = {}
        for name, audio_name in name_mapping.items():
            if audio_name in files:
                mapping[name] = files[audio_name].relative_to(self.destination.parent)
            elif name in files:
                mapping[name] = files[name].relative_to(self.destination.parent)
            else:
                _warning('audio identifier %s not found', name)
        mapped_files = set(mapping.values())
        for audio_name, file in files.items():
            path = file.relative_to(self.destination.parent)
            if path not in mapped_files:
                mapping[audio_name] = path
        return mapping

    def save(self):
        path = self.destination.parent.joinpath('audio.json')
        with path.open('w') as f:
            f.write(json.dumps(dict((k, str(v)) for k, v in self.extracted.items()), indent=2, ensure_ascii=False))
        return path