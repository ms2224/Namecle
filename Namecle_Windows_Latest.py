import sys
import os
import re
import urllib.parse
import requests
import time
import fitz
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QFileDialog, QLabel, QMessageBox, QListWidgetItem,
    QHBoxLayout, QInputDialog, QGroupBox, QStatusBar, QProgressBar, QStyle, QSizePolicy,
    QTableWidget, QTableWidgetItem, QTextEdit, QAbstractItemView, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QFont, QIcon, QBrush, QColor

__version__ = "1.0.1"

PDF_PREVIEW_PAGES = 5 # PDFの最初の何ページを読み込むか
TITLE_FONT_SIZE_THRESHOLD = 15 # タイトルと見なす最小フォントサイズ
MIN_TITLE_LENGTH = 5 # タイトルと見なす最小文字数
MAX_AUTHORS_TO_EXTRACT = 5 # 抽出する著者の最大数

# 引用数グレード関連の定数
GRADE_SSS_THRESHOLD = 1000
GRADE_AAA_THRESHOLD = 100
GRADE_BBB_THRESHOLD = 10

def extract_pdf_info(pdf_path):
    """
    PDF の最初の5ページからテキストを抽出
    タイトル、著者、発行年、DOI を抽出
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return None, None, None, None, f"PDF読み込みエラー: {e}"

    text = ""
    for page in doc[:PDF_PREVIEW_PAGES]:
        text += page.get_text()

    # DOI 抽出
    doi_pattern = re.compile(
        r'(?i)\b(?:https?://doi\.org/|doi[:\s]*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b',
        re.IGNORECASE
    )
    doi_match = doi_pattern.search(text)
    doi = doi_match.group(1) if doi_match else None

    # タイトル抽出（フォントサイズなどを参考に）
    title = None
    for block in doc[0].get_text("dict")["blocks"]:
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["size"] > TITLE_FONT_SIZE_THRESHOLD and len(span["text"].strip()) > MIN_TITLE_LENGTH:
                        title = span["text"].strip()
                        break
                if title:
                    break
        if title:
            break

    # 著者抽出（簡易な正規表現）
    author_pattern = re.compile(r'(?i)([A-Z]\.[A-Z]?\.?\s?[A-Z][a-z]+|[A-Z][a-z]+\s[A-Z][a-z]+)')
    authors = author_pattern.findall(text)
    authors = ", ".join(dict.fromkeys(authors[:MAX_AUTHORS_TO_EXTRACT]))

    # 発行年抽出
    year_match = re.findall(r'(20\d{2}|19\d{2})', text)
    year = year_match[0] if year_match else None

    doc.close()
    return title, authors, year, doi, None

def search_semantic_scholar(title):
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {"query": title, "limit": 1, "fields": "title,authors,citationCount,year"}
    try:
        time.sleep(1)
        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            return None, None, None, f"Semantic Scholar API エラー: {response.status_code}"
        data = response.json()
        if data.get("total", 0) == 0 or not data.get("data"):
            return None, None, None, "Semantic Scholar で論文が見つかりませんでした。"
        paper = data["data"][0]
        citation_count = paper.get("citationCount")
        year = paper.get("year")
        authors = ", ".join([a.get("name", "") for a in paper.get("authors", [])])
        info = {
            "title": paper.get("title"),
            "authors": authors,
            "year": year,
            "citation_count": citation_count
        }
        return citation_count, year, authors, info
    except Exception as e:
        return None, None, None, f"Semantic Scholar API 呼び出し中にエラー: {e}"

def search_semantic_scholar_by_doi(doi):
    base_url = "https://api.semanticscholar.org/graph/v1/paper/"
    doi_query = doi if doi.upper().startswith("DOI:") else "DOI:" + doi
    url = base_url + doi_query
    params = {"fields": "title,authors,citationCount,year"}
    try:
        time.sleep(1)
        response = requests.get(url, params=params)
        if response.status_code != 200:
            return None, None, None, f"Semantic Scholar DOI API エラー: {response.status_code}"
        data = response.json()
        citation_count = data.get("citationCount")
        year = data.get("year")
        authors = ", ".join([a.get("name", "") for a in data.get("authors", [])])
        info = {
            "title": data.get("title"),
            "authors": authors,
            "year": year,
            "citation_count": citation_count
        }
        return citation_count, year, authors, info
    except Exception as e:
        return None, None, None, f"Semantic Scholar DOI API 呼び出し中にエラー: {e}"

def search_crossref(title):
    base_url = "https://api.crossref.org/works"
    params = {"query.title": title, "rows": 1}
    try:
        time.sleep(1)
        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            return None, None, None, f"CrossRef API エラー: {response.status_code}"
        data = response.json()
        items = data.get("message", {}).get("items", [])
        if not items:
            return None, None, None, "CrossRef で論文が見つかりませんでした。"
        paper = items[0]
        date_parts = paper.get("issued", {}).get("date-parts", [[None]])
        year = date_parts[0][0]
        authors = ", ".join(
            f"{a.get('given','')} {a.get('family','')}".strip()
            for a in paper.get("author", [])
        )
        citation_count = paper.get("is-referenced-by-count")
        info = {
            "title": paper.get("title", [None])[0],
            "authors": authors,
            "year": year,
            "citation_count": citation_count
        }
        return citation_count, year, authors, info
    except Exception as e:
        return None, None, None, f"CrossRef API 呼び出し中にエラー: {e}"

def search_crossref_by_doi(doi):
    base_url = "https://api.crossref.org/works/"
    doi_encoded = urllib.parse.quote(doi)
    url = base_url + doi_encoded
    try:
        time.sleep(1)
        response = requests.get(url)
        if response.status_code != 200:
            return None, None, None, f"CrossRef DOI API エラー: {response.status_code}"
        message = response.json().get("message", {})
        date_parts = message.get("issued", {}).get("date-parts", [[None]])
        year = date_parts[0][0]
        authors = ", ".join(
            f"{a.get('given','')} {a.get('family','')}".strip()
            for a in message.get("author", [])
        )
        citation_count = message.get("is-referenced-by-count")
        info = {
            "title": message.get("title", [None])[0],
            "authors": authors,
            "year": year,
            "citation_count": citation_count
        }
        return citation_count, year, authors, info
    except Exception as e:
        return None, None, None, f"CrossRef DOI API 呼び出し中にエラー: {e}"

def determine_grade(citation_count):
    if citation_count is None:
        return "unknown"
    if citation_count >= GRADE_SSS_THRESHOLD:
        return "sss"
    if citation_count >= GRADE_AAA_THRESHOLD:
        return "aaa"
    if citation_count >= GRADE_BBB_THRESHOLD:
        return "ccc"
    return "ccc"

def clean_filename(text):
    return re.sub(r'[\\/*?:"<>|]', '_', text)

def process_file(pdf_path, logger, manual_title=None):

    if not os.path.isfile(pdf_path):
        err = f"[ファイルエラー] ファイルが見つかりません: {pdf_path}"
        logger(err)
        return None, {"エラー": err}

    logger(f"\n---\n[処理開始] ファイル: {pdf_path}")

    if manual_title:
        # 手動モード
        title = manual_title
        meta_authors = None
        meta_year = None
        doi = None
        logger(f"[手動モード] 題目を手動入力から取得 → {title}")
    else:
        # 通常モード
        title, meta_authors, meta_year, doi, err = extract_pdf_info(pdf_path)
        if err:
            logger(f"[PDF抽出エラー] {err}")
            return None, {"エラー": err}
        logger(f"[PDF抽出] DOI: {doi or 'なし'}")
        logger(f"[PDF抽出] 題目: {title}")
        logger(f"[PDF抽出] 著者: {meta_authors}")
        logger(f"[PDF抽出] 発行年: {meta_year}")

    # 検索フェーズ
    if doi and not manual_title:
        logger("[検索] DOI検索を実行中...")
        citation_count, api_year, api_authors, info = search_semantic_scholar_by_doi(doi)
        if not isinstance(info, dict):
            logger(f"[検索エラー] Semantic Scholar DOI: {info}")
            logger("[検索] CrossRef DOI 検索を実行中...")
            citation_count, api_year, api_authors, info = search_crossref_by_doi(doi)
    else:
        if not title:
            err = "[スキップ] 題目が取得できなかったためスキップしました。"
            logger(err)
            return None, {"エラー": err}
        logger("[検索] タイトル検索を実行中...")
        citation_count, api_year, api_authors, info = search_semantic_scholar(title)
        if not isinstance(info, dict):
            logger(f"[検索エラー] Semantic Scholar: {info}")
            logger("[検索] CrossRef 検索を実行中...")
            citation_count, api_year, api_authors, info = search_crossref(title)

    # 最終情報の決定
    final_year    = info.get("year")    or meta_year
    final_authors = info.get("authors") or meta_authors
    final_title   = info.get("title")   or title
    grade         = determine_grade(info.get("citation_count"))

    if grade == "unknown":
        logger("[グレード判定] 引用件数のグレードを判定できませんでした。")

    safe_title_original = clean_filename(final_title)
    safe_authors_original = clean_filename(final_authors or "")

    prefix = ""
    if final_year:
        prefix += str(final_year) + " "
    if grade and grade != "unknown":
        prefix += grade + " "
    
    current_title = safe_title_original
    current_authors = safe_authors_original

    temp_filename_base = f"{prefix}{current_title} {current_authors}"
    total_length = len(temp_filename_base) + len(".pdf")

    MAX_FILENAME_LENGTH = 255

    # 255文字を超えている場合のみ、著者名を短縮する
    if total_length > MAX_FILENAME_LENGTH:
        logger(f"[ファイル名生成] ファイル名が長すぎます ({total_length}文字)。短縮します。")
        
        if safe_authors_original:
            first_author = safe_authors_original.split(',')[0].strip()
            current_authors = f"{first_author} et al."
            logger(f"[ファイル名生成] 著者名を '{current_authors}' に短縮しました。")
        
        temp_filename_base_after_author_shorten = f"{prefix}{current_title} {current_authors}"
        total_length_after_author_shorten = len(temp_filename_base_after_author_shorten) + len(".pdf")

        if total_length_after_author_shorten > MAX_FILENAME_LENGTH:
            oversize = total_length_after_author_shorten - MAX_FILENAME_LENGTH
            
            if len(current_title) > oversize + 3:
                current_title = current_title[:len(current_title) - oversize - 3] + "..."
                logger(f"[ファイル名生成] タイトルを '{current_title}' に短縮しました。")
            else:
                logger(f"[ファイル名生成] タイトルと著者を短縮しましたが、長すぎます。")
    
    new_filename = f"{prefix}{current_title} {current_authors}.pdf".strip() 
    info_dict = {
        "年": final_year,
        "グレード": grade,
        "引用数": info.get("citation_count"),
        "タイトル": final_title,
        "著者": final_authors,
        "DOI": doi
    }

    try:
        os.rename(pdf_path, os.path.join(os.path.dirname(pdf_path), new_filename))
        logger(f"[ファイル操作] ファイル名を変更しました: {new_filename}")
        return new_filename, info_dict
    except Exception as e:
        err = f"[ファイル操作エラー] ファイル名の変更に失敗しました: {e}"
        logger(err)
        return None, {"エラー": err}

class FileItemWidget(QWidget):
    def __init__(self, file_path, max_label_width, remove_callback):
        super().__init__()
        self.file_path = file_path
        self.remove_callback = remove_callback
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(10)
        self.label = QLabel(file_path)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.label.setMaximumWidth(max_label_width)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.label, 6)
        layout.addStretch()
        self.remove_button = QPushButton()
        self.remove_button.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.remove_button.setToolTip("削除")
        self.remove_button.setFixedWidth(30)
        layout.addWidget(self.remove_button, 0)
        self.remove_button.clicked.connect(self.on_remove)

    def on_remove(self):
        if self.remove_callback:
            self.remove_callback(self)


# --- メインウィンドウ ---

class MainWindow(QMainWindow):
    TABLE_COLUMN_RATIOS = [
        0.15, # "元のファイル名"
        0.05, # "年"
        0.05, # "グレード"
        0.10, # "引用数"
        0.30, # "タイトル"
        0.25, # "著者"
        0.10  # "DOI"
    ]

    def __init__(self):
        super().__init__()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path   = os.path.join(current_dir, "icon.ico")
        window_title = f"Namecle : Quick Article Renaming v{__version__}"
        self.setWindowTitle(window_title)
        self.setWindowIcon(QIcon(icon_path))
        self.resize(900, 700)
        self.setAcceptDrops(True)
        self.setup_ui()

    def setup_ui(self):
        main_font = QFont("メイリオ", 10)
        code_font = QFont("Consolas", 10)
        central  = QWidget()
        central.setFont(main_font)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # タイトル
        lbl_title = QLabel("Namecle : Quick Article Renaming")
        lbl_title.setFont(QFont("メイリオ", 16, QFont.Bold))
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        # 説明
        lbl_desc = QLabel("PDF をドラッグ＆ドロップするか、[参照] ボタンでファイルを追加してください。")
        lbl_desc.setFont(main_font)
        lbl_desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_desc)

        # ファイルリスト
        grp_files = QGroupBox("論文PDF")
        grp_files.setFont(main_font)
        vbox = QVBoxLayout()
        self.file_list = QListWidget()
        self.file_list.setFont(main_font)
        self.file_list.setMinimumHeight(300)
        vbox.addWidget(self.file_list)
        grp_files.setLayout(vbox)
        layout.addWidget(grp_files)

        # ボタンとチェックボックス
        hbox = QHBoxLayout()
        self.browse_btn = QPushButton("参照")
        self.browse_btn.setFont(main_font)
        self.browse_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.auto_btn   = QPushButton("オートモード処理")
        self.auto_btn.setFont(main_font)
        self.auto_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.manual_btn = QPushButton("マニュアルモード処理")
        self.manual_btn.setFont(main_font)
        self.manual_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        self.auto_title_cb = QCheckBox("PDFから題目を自動抽出 ※精度が低下する可能性があります")
        self.auto_title_cb.setChecked(False)
        hbox.addWidget(self.browse_btn)
        hbox.addWidget(self.auto_btn)
        hbox.addWidget(self.manual_btn)
        hbox.addWidget(self.auto_title_cb)
        layout.addLayout(hbox)

        # ログ表示
        grp_log = QGroupBox("ログ")
        grp_log.setFont(main_font)
        log_box = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setFont(code_font)
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(225)
        log_box.addWidget(self.log_text)
        grp_log.setLayout(log_box)
        layout.addWidget(grp_log)

        # 結果
        grp_result = QGroupBox("変更後ファイル名情報")
        grp_result.setFont(main_font)
        res_box = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["元のファイル名", "年", "グレード", "引用数", "タイトル", "著者", "DOI"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setMinimumHeight(450)
        res_box.addWidget(self.table)
        grp_result.setLayout(res_box)
        layout.addWidget(grp_result)

        self.status = QStatusBar()
        self.status.setFont(main_font)
        self.progress = QProgressBar()
        self.progress.setFont(main_font)
        self.progress.setMaximum(100)
        self.status.addPermanentWidget(self.progress)
        self.setStatusBar(self.status)

        self.browse_btn.clicked.connect(self.browse_files)
        self.auto_btn.clicked.connect(lambda: self._process_files(manual=False))
        self.manual_btn.clicked.connect(lambda: self._process_files(manual=True))

    def log(self, msg):
        self.log_text.append(msg)
        self.status.showMessage(msg, 5000)

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "PDF ファイルを選択", "", "PDF Files (*.pdf)"
        )
        for f in files:
            self.add_file(f)

    def add_file(self, path):
        for i in range(self.file_list.count()):
            w = self.file_list.itemWidget(self.file_list.item(i))
            if w and w.file_path == path:
                return
        item = QListWidgetItem()

        widget = FileItemWidget(path, int(self.file_list.viewport().width() * 0.9), self.remove_file)
        item.setSizeHint(widget.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, widget)

    def remove_file(self, widget):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if self.file_list.itemWidget(item) is widget:
                self.file_list.takeItem(i)
                break

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        for url in e.mimeData().urls():
            fp = url.toLocalFile()
            if fp.lower().endswith(".pdf"):
                self.add_file(fp)
        e.acceptProposedAction()

    def _get_manual_title_input(self, file_path):
        """手動で題目入力ダイアログを表示し、結果を返す"""
        title, ok = QInputDialog.getText(
            self, "題目手動入力",
            f"ファイル「{os.path.basename(file_path)}」の題目を入力してください:"
        )
        if ok and title.strip():
            return title.strip()
        return None

    def _process_single_file(self, file_path, manual_mode_enabled):
        """単一のPDFファイルを処理するロジック"""
        manual_title = None
        orig_filename = os.path.basename(file_path)

        if manual_mode_enabled:
            # マニュアルモード
            manual_title = self._get_manual_title_input(file_path)
            if manual_title is None:
                self.log(f"[スキップ] 題目未入力によりスキップ: {orig_filename}")
                return None, {"エラー": "題目未入力"}
            self.log(f"[手動モード] 題目を '{manual_title}' に設定して処理します。")
        else:
            # オートモード
            _, _, _, doi_extracted, err = extract_pdf_info(file_path)
            if err:
                self.log(f"[PDF抽出エラー] {err} (ファイル: {orig_filename})")
                # DOI抽出に失敗、自動抽出OFFならば手動入力
                if not self.auto_title_cb.isChecked():
                    manual_title = self._get_manual_title_input(file_path)
                    if manual_title is None:
                        self.log(f"[スキップ] 題目未入力によりスキップ: {orig_filename}")
                        return None, {"エラー": "題目未入力"}
                    self.log(f"[手動モード] PDF情報抽出失敗（自動抽出オフ）: 題目を '{manual_title}' に設定して処理します。")
                else:
                    self.log(f"[オートモード] PDF情報抽出失敗（自動抽出オン）: 可能な限り自動で処理を続行します。")

            # DOIが抽出できた場合、手動タイトルは不要
            if doi_extracted:
                manual_title = None
                self.log(f"[PDF抽出] DOIを検出しました: {doi_extracted}")
            elif not self.auto_title_cb.isChecked():
                pass
            else:
                manual_title = None
                self.log(f"[オートモード] DOIを検出できませんでした。PDFからのタイトル自動抽出を試みます。")

        new_name, info = process_file(file_path, self.log, manual_title)
        return new_name, info

    def _process_files(self, manual=False):
        count = self.file_list.count()
        if count == 0:
            self.log("処理する PDF ファイルがありません。")
            return

        self.table.setRowCount(0)
        self.progress.setValue(0)
        step = 100 // count if count else 100

        for idx in range(count):
            item   = self.file_list.item(idx)
            widget = self.file_list.itemWidget(item)
            if not widget:
                continue
            fp = widget.file_path
            orig_filename = os.path.basename(fp)

            new_name, info = self._process_single_file(fp, manual)

            if new_name:
                new_fp = os.path.join(os.path.dirname(fp), new_name)
                widget.file_path = new_fp
                widget.label.setText(new_fp)

                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(orig_filename))
                self.table.setItem(row, 1, QTableWidgetItem(str(info.get("年", "N/A"))))
                self.table.setItem(row, 2, QTableWidgetItem(str(info.get("グレード", "N/A"))))
                self.table.setItem(row, 3, QTableWidgetItem(str(info.get("引用数", "N/A"))))
                self.table.setItem(row, 4, QTableWidgetItem(info.get("タイトル", "N/A")))
                self.table.setItem(row, 5, QTableWidgetItem(info.get("著者", "N/A")))
                self.table.setItem(row, 6, QTableWidgetItem(info.get("DOI", "N/A") or ""))
            else:
                row = self.table.rowCount()
                self.table.insertRow(row)
                err_msg = info.get('エラー', '不明なエラー')
                err_text = f"{orig_filename} - エラー: {err_msg}"
                it = QTableWidgetItem(err_text)
                it.setForeground(QBrush(QColor('red')))
                self.table.setItem(row, 0, it)
                self.table.setSpan(row, 0, 1, self.table.columnCount())

            self.progress.setValue((idx + 1) * step)

        self.progress.setValue(100)
        self.log("全てのファイルの処理が完了しました。")
        self.adjust_table_columns()

    def adjust_table_columns(self):
        w = self.table.viewport().width()
        for i, r in enumerate(self.TABLE_COLUMN_RATIOS):
            self.table.setColumnWidth(i, int(w * r))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.adjust_table_columns()

        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            widget = self.file_list.itemWidget(item)
            if widget:
                widget.label.setMaximumWidth(int(self.file_list.viewport().width() * 0.9))
                item.setSizeHint(widget.sizeHint())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    wnd = MainWindow()
    wnd.show()
    sys.exit(app.exec_())
