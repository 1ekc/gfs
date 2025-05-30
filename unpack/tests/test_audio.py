from gfunpack.audio import BGM
import pathlib
import logging


def test_audio_conversion():
    # 1. Настройка путей
    input_dir = pathlib.Path('downloader/output')
    output_dir = pathlib.Path('unpack/audio')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Инициализация и обработка аудио
    bgm = BGM(
        directory=str(input_dir),
        destination=str(output_dir),
        force=False,
        concurrency=4,
        clean=True
    )

    # 3. Сохранение результата
    json_path = bgm.save()
    print(f"Audio data saved to: {json_path}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    test_audio_conversion()