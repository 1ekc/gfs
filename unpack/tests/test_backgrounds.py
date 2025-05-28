from gfunpack import backgrounds
from pathlib import Path


def test_backgrounds():
    # Указываем абсолютные пути
    bg = backgrounds.BackgroundCollection(
        directory=str(Path("downloader/output").resolve()),
        destination=str(Path("images").resolve()),
        pngquant=True
    )

    # Принудительно задаём profiles.txt (если скрипт его не находит)
    bg.profile_asset = Path("gf-data-rus/asset/avgtxt/profiles.txt").resolve()

    bg.save()

    # Проверка
    json_path = Path("images/backgrounds.json")
    print(f"JSON создан: {json_path.exists()}")


if __name__ == '__main__':
    test_backgrounds()