# Windows用exeファイルのビルドガイド

以下のコマンドを実行してアプリケーションをビルドしてください．

```
pyinstaller --onefile --windowed --icon icon.ico --add-data "icon.ico;." --name Namecle Namecle_Windows_Latest.py
```

# Linux用ビルドガイド

以下のコマンドを実行してアプリケーションをビルドしてください．

```
pyinstaller --onefile --windowed --add-data "icon.png:." --name Namecle Namecle_Linux_Latest.py
```
