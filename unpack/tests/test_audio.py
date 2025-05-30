import os
import subprocess
import pathlib

def test_audio_conversion():
    # Проверяем базовую функциональность vgmstream
    vgmstream_path = os.getenv('VGMSTREAM_PATH', 'vgmstream-cli.exe')
    try:
        subprocess.run([vgmstream_path, '-V'], check=True)
        print("vgmstream-cli работает корректно")
    except Exception as e:
        print(f"Ошибка vgmstream: {e}")
        raise

if __name__ == '__main__':
    test_audio_conversion()