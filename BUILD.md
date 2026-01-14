# Windows用exeファイルのビルドガイド(v2 / LLM版)-推奨

[**build_windows.py**](https://github.com/ms2224/Namecle/blob/main/build_windows.py)を実行してビルドしてください．

# Linux用ビルドガイド

以下のコマンドを実行してアプリケーションをビルドしてください．

```
pyinstaller --onefile --windowed --add-data "assets/icon.png:." --name Namecle Namecle_Linux.py
```

# Windows用exeファイルのビルドガイド(Legacy版)

以下のコマンドを実行してアプリケーションをビルドしてください．

```
pyinstaller --onefile --windowed --icon assets/icon.ico --add-data "assets/icon.ico;." --name Namecle_Legacy legacy_v1/Namecle_Windows_v1.py
```