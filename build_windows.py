import PyInstaller.__main__
import llama_cpp
import os

llama_cpp_path = os.path.dirname(llama_cpp.__file__)
llama_lib_path = os.path.join(llama_cpp_path, 'lib')

print(f"Llama-cpp lib path found: {llama_lib_path}")

PyInstaller.__main__.run([
    'Namecle_Windows.py',
    '--name=Namecle_Windows',
    '--onefile',
    '--windowed',
    '--noconfirm',
    '--icon=assets/icon.ico',

    f'--add-data={llama_lib_path}{os.pathsep}./llama_cpp/lib',

    f'--add-data=assets{os.pathsep}assets',
    f'--add-data=Namecle_UI.ui{os.pathsep}.',
])