# Windows用EXEファイルのビルドガイド

以下のコマンドを実行してアプリケーションをビルドしてください．

```
pyinstaller --onefile --windowed --icon icon.ico --add-data "icon.ico;." --name Namecle Namecle_Windows_Latest.py
```
