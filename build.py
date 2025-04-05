import os

os.system('pip install -r requirements.txt')

def rmtree(path):
    if os.path.isdir(path) and not os.path.islink(path):
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            rmtree(full_path)
        os.rmdir(path)
    else:
        os.remove(path)

import PyInstaller.__main__

PyInstaller.__main__.run([
    'main.py',
    '--onefile',
    '--windowed',
    '--clean',
    '--name=Smart Event',
    '--icon=icon.ico',
    '--add-data=icon.ico;.',
    '--distpath=.',
    '--workpath=./build',
    '--specpath=.'
])

rmtree('build')
os.remove('Smart Event.spec')