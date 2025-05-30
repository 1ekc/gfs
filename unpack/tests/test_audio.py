from gfunpack import audio
from pathlib import Path


def test_bgm():
    base_dir = Path(__file__).parent.parent  # Переход в корень проекта
    input_dir = base_dir / "downloader" / "output"
    output_dir = base_dir / "audio"
    output_dir.mkdir(exist_ok=True)

    audio.BGM(str(input_dir), str(output_dir))


if __name__ == '__main__':
    test_bgm()