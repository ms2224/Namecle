import sys
import os
import re
import urllib.parse
import requests
import time
import fitz
import json
import difflib
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QFileDialog, 
    QListWidgetItem, QHBoxLayout, QStyle, QLabel, QMessageBox, 
    QTableWidgetItem, QInputDialog, QHeaderView, QProgressBar, QTableWidget
)
from PyQt5 import uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QWaitCondition, QBuffer, QIODevice
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QBrush, QIcon, QImage, QPixmap
import qtawesome as qta
import base64

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False

MODERN_STYLESHEET = """
QMainWindow {
    background-color: #F3F4F6;
}
QWidget {
    font-family: "Yu Gothic UI", "Meiryo UI", "Segoe UI", sans-serif;
    color: #1F2937;
}

QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    margin-top: 1.2em;
    padding-top: 10px;
    font-weight: bold;
    color: #4B5563;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 20px;
    padding: 0 5px;
    color: #6B7280;
    font-size: 14px;
}

QLineEdit {
    background-color: #F9FAFB;
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #3B82F6;
}
QLineEdit:focus {
    border: 2px solid #3B82F6;
    background-color: #FFFFFF;
}
QLineEdit:read-only {
    background-color: #F3F4F6;
    color: #9CA3AF;
    border: 1px solid #E5E7EB;
}

QTextEdit {
    background-color: #F9FAFB;
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    padding: 8px;
    font-size: 12px;
    color: #374151;
}

QListWidget {
    background-color: #F9FAFB;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    padding: 4px;
    font-size: 12px;
    outline: none;
}
QListWidget::item {
    border-radius: 4px;
    padding: 0px;
    margin-bottom: 2px;
}
QListWidget::item:selected {
    background-color: #EFF6FF;
    color: #1D4ED8;
    border: 1px solid #BFDBFE;
}
QListWidget::item:hover {
    background-color: #F3F4F6;
}

QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    color: #374151;
}
QPushButton:hover {
    background-color: #F9FAFB;
    border-color: #9CA3AF;
}
QPushButton:pressed {
    background-color: #E5E7EB;
    padding-top: 10px;
    padding-bottom: 6px;
}

QPushButton#btn_auto {
    background-color: #2563EB;
    color: white;
    border: none;
    font-size: 15px;
    padding: 12px 24px;
    border-radius: 10px;
}
QPushButton#btn_auto:hover {
    background-color: #1D4ED8;
    margin-top: 0px;
}
QPushButton#btn_auto:pressed {
    background-color: #1E40AF;
    padding-top: 14px;
    padding-bottom: 10px;
}
QPushButton#btn_auto:disabled {
    background-color: #93C5FD;
}

QRadioButton {
    spacing: 8px;
    color: #374151;
}
QRadioButton::indicator {
    width: 18px;
    height: 18px;
}

QTableWidget {
    background-color: #FFFFFF;
    gridline-color: #F3F4F6;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    selection-background-color: #EFF6FF;
    selection-color: #1E3A8A;
    outline: none;
}
QHeaderView::section {
    background-color: #F9FAFB;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #E5E7EB;
    font-weight: bold;
    color: #6B7280;
    font-size: 12px;
}
QTableWidget::item {
    padding: 5px;
    border-bottom: 1px solid #F3F4F6;
}
QScrollBar:vertical {
    border: none;
    background: #F3F4F6;
    width: 10px;
    margin: 0px 0px 0px 0px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #D1D5DB;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #9CA3AF;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QStatusBar {
    background: #FFFFFF;
    color: #6B7280;
    border-top: 1px solid #E5E7EB;
}
"""

__version__ = "2.0.0"

APP_DATA_DIR = os.path.join(os.getenv('LOCALAPPDATA'), "Namecle")
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR)

SETTINGS_FILE = os.path.join(APP_DATA_DIR, "settings.json")

CONFIG = {
    "PDF_PREVIEW_PAGES": 5,
    "TITLE_FONT_SIZE_THRESHOLD": 15,
    "MIN_TITLE_LENGTH": 5,
    "MAX_AUTHORS": 5,
    "GRADE_THRESHOLDS": {"SSS": 1000, "AAA": 100, "BBB": 10},
    "MAX_FILENAME_LENGTH": 255,
    "MODEL_PATH": "gemma-2-2b-it-Q4_K_M.gguf",
    "TITLE_SIMILARITY_THRESHOLD": 0.75
}

class GemmaSmartExtractor:
    def __init__(self, model_path):

        self.llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1, 
            n_threads=None,
            n_batch=512,
            n_ctx=2048,
            verbose=False
        )

    def _get_text_with_layout_hints(self, pdf_path):
        try:
            doc = fitz.open(pdf_path)
            page = doc[0]
            blocks = page.get_text("dict")["blocks"]
        except Exception:
            return ""
        finally:
            if doc:
                doc.close()

        max_font_size = 0
        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    if s["size"] > max_font_size:
                        max_font_size = s["size"]

        annotated_text = []
        title_threshold = max_font_size * 0.9 if max_font_size > 0 else 0

        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                line_text = "".join([s["text"] for s in l["spans"]]).strip()
                if not line_text: continue
                
                line_max_size = 0
                if l["spans"]:
                    line_max_size = max([s["size"] for s in l["spans"]])

                if line_max_size >= title_threshold:
                    line_text = f"<Title>{line_text}</Title>"
                
                annotated_text.append(line_text)

        return "\n".join(annotated_text)[:2500]

    def extract(self, pdf_path):
        input_text = self._get_text_with_layout_hints(pdf_path)
        if not input_text: return None

        prompt = f"""<start_of_turn>user
You are a bibliography extraction assistant.
Extract the paper title, author names, and publication year from the text below.

Important Rules:
- The text contains layout tags like <Title>...</Title>. The text inside these tags is highly likely to be the Title.
- Ignore generic headers like "Original Article" or journal names if they are not the main title.
- Format the output as a valid JSON object.

Output Format:
{{
  "title": "The exact title of the paper",
  "authors": "Author 1, Author 2, ...",
  "year": "YYYY"
}}

Text:
{input_text}<end_of_turn>
<start_of_turn>model
```json
"""
        output = self.llm(
            prompt, max_tokens=300, temperature=0.1,
            stop=["<end_of_turn>", "```"], echo=False
        )
        
        try:
            raw = output['choices'][0]['text'].strip()
            json_str = raw.replace("```json", "").replace("```", "").strip()
            if not json_str.endswith("}"): json_str += "}"
            return json.loads(json_str)
        except:
            return None

class ArticleFetcher:
    @staticmethod
    def search(title: str = None, doi: str = None, author: str = None):
        if doi:
            res = ArticleFetcher._query_semantic_scholar(doi=doi)
            if res: return res
            res = ArticleFetcher._query_crossref(doi=doi)
            if res: return res
        if title:
            if author:
                res = ArticleFetcher._query_semantic_scholar(title=title, author=author)
                if res: return res

                res = ArticleFetcher._query_crossref(title=title, author=author)
                if res: return res

            res = ArticleFetcher._query_semantic_scholar(title=title, author=None)
            if res: return res
            
            res = ArticleFetcher._query_crossref(title=title, author=None)
            if res: return res

        return None, None, None, "検索で見つかりませんでした。"

    @staticmethod
    def _query_semantic_scholar(title=None, doi=None, author=None):
        base_url = "https://api.semanticscholar.org/graph/v1/paper/"
        params = {"fields": "title,authors,citationCount,year"}
        if doi:
            url = base_url + (doi if doi.upper().startswith("DOI:") else f"DOI:{doi}")
        else:
            url = base_url + "search"
            if author:
                clean_author = author.split(",")[0]
                params["query"] = f"{title} {clean_author}"
            else:
                params["query"] = title
            params["limit"] = 1

        try:
            time.sleep(1)
            response = requests.get(url, params=params)
            if response.status_code != 200: return None
            data = response.json()
            if "data" in data:
                if not data["data"]:
                    return None
                paper = data["data"][0]
            else:
                paper = data
            if not paper: return None
            authors = ", ".join([a.get("name", "") for a in paper.get("authors", [])])
            info = {
                "title": paper.get("title"), "authors": authors,
                "year": paper.get("year"), "citation_count": paper.get("citationCount")
            }
            return paper.get("citationCount"), paper.get("year"), authors, info
        except: return None

    @staticmethod
    def _query_crossref(title=None, doi=None, author=None):
        base_url = "https://api.crossref.org/works"
        params = {"rows": 1}
        if doi:
            url = base_url + "/" + urllib.parse.quote(doi)
            params = {}
        else:
            url = base_url
            params["query.title"] = title
            if author:
                 clean_author = author.split(",")[0]
                 params["query.author"] = clean_author

        try:
            time.sleep(1)
            response = requests.get(url, params=params)
            if response.status_code != 200: return None
            data = response.json()
            items = data.get("message", {}).get("items", []) if not doi else [data.get("message", {})]
            if not items: return None
            paper = items[0]
            date_parts = paper.get("issued", {}).get("date-parts", [[None]])
            year = date_parts[0][0]
            authors = ", ".join(f"{a.get('given','')} {a.get('family','')}".strip() for a in paper.get("author", []))
            info = {
                "title": paper.get("title", [None])[0], "authors": authors,
                "year": year, "citation_count": paper.get("is-referenced-by-count")
            }
            return info["citation_count"], year, authors, info
        except: return None

class PDFProcessor:
    
    @staticmethod
    def extract_basic_info(pdf_path):
        try:
            doc = fitz.open(pdf_path)
            text = "".join([page.get_text() for page in doc[:CONFIG["PDF_PREVIEW_PAGES"]]])
            
            doi_match = re.search(r'(?i)\b(?:https?://doi\.org/|doi[:\s]*)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b', text)
            doi = doi_match.group(1) if doi_match else None
            
            doc.close()
            return text, doi
        except Exception as e:
            return None, None

    @staticmethod
    def extract_heuristics(pdf_path):
        try:
            doc = fitz.open(pdf_path)
            title = None
            if len(doc) > 0:
                for block in doc[0].get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        for span in line["spans"]:
                            if span["size"] > CONFIG["TITLE_FONT_SIZE_THRESHOLD"] and len(span["text"].strip()) > CONFIG["MIN_TITLE_LENGTH"]:
                                title = span["text"].strip(); break
                        if title: break
                    if title: break

            text = "".join([page.get_text() for page in doc[:CONFIG["PDF_PREVIEW_PAGES"]]])
            authors_match = re.findall(r'(?i)([A-Z]\.[A-Z]?\.?\s?[A-Z][a-z]+|[A-Z][a-z]+\s[A-Z][a-z]+)', text)
            authors = ", ".join(dict.fromkeys(authors_match[:CONFIG["MAX_AUTHORS"]]))
            year_match = re.search(r'(20\d{2}|19\d{2})', text)
            year = year_match.group(0) if year_match else None
            doc.close()
            return title, authors, year
        except:
            return None, None, None

    @staticmethod
    def generate_filename(info_dict):
        grade = "ccc"
        c_count = info_dict.get("citation_count")
        if c_count:
            if c_count >= CONFIG["GRADE_THRESHOLDS"]["SSS"]: grade = "sss"
            elif c_count >= CONFIG["GRADE_THRESHOLDS"]["AAA"]: grade = "aaa"
            elif c_count >= CONFIG["GRADE_THRESHOLDS"]["BBB"]: grade = "bbb"
        
        info_dict["グレード"] = grade
        def clean(s): return re.sub(r'[\\/*?:"<>|]', '_', str(s or ""))
        
        title = clean(info_dict.get("title"))
        authors = clean(info_dict.get("authors"))
        year = info_dict.get("year")
        
        prefix = f"{year} " if year else ""
        prefix += f"{grade} "
        base_name = f"{prefix}{title} {authors}"
        ext = ".pdf"
        
        if len(base_name) + len(ext) > CONFIG["MAX_FILENAME_LENGTH"]:
            authors = authors.split(',')[0].strip() + " et al."
            base_name = f"{prefix}{title} {authors}"
            overflow = (len(base_name) + len(ext)) - CONFIG["MAX_FILENAME_LENGTH"]
            if overflow > 0:
                title = title[:-(overflow + 4)] + "..."
                base_name = f"{prefix}{title} {authors}"
        return base_name + ext
    
    @staticmethod
    def check_similarity(str1, str2):
        if not str1 or not str2: return 0.0
        s1 = re.sub(r'\W+', '', str1.lower())
        s2 = re.sub(r'\W+', '', str2.lower())
        return difflib.SequenceMatcher(None, s1, s2).ratio()

class FileItemWidget(QWidget):
    def __init__(self, file_path, remove_callback):
        super().__init__()
        self.file_path = file_path
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 4, 5, 4)
        self.label = QLabel(file_path)
        layout.addWidget(self.label, 1)
        btn = QPushButton()
        btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        btn.setFixedSize(24, 24)
        btn.clicked.connect(lambda: remove_callback(self))
        layout.addWidget(btn, 0, Qt.AlignVCenter)

        btn.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent; /* 背景透明 */
                color: #9CA3AF; /* グレーの文字 */
                font-weight: bold;
                font-size: 16px;
                border-radius: 4px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #FEE2E2; /* ホバー時は薄い赤背景 */
                color: #EF4444; /* 文字は赤 */
            }
        """)

        self.setMinimumHeight(36)

class RenameWorker(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str, dict, str, str) 
    update_file_path_signal = pyqtSignal(str, str) 
    request_manual_input_signal = pyqtSignal(str, str) 

    progress_signal = pyqtSignal(int, int)

    def __init__(self, file_list, use_llm, manual_mode, chk_auto_title, llm_extractor):
        super().__init__()
        self.file_list = file_list
        self.use_llm = use_llm
        self.manual_mode = manual_mode
        self.chk_auto_title = chk_auto_title
        self.llm_extractor = llm_extractor
        
        self.input_mutex = QMutex()
        self.input_condition = QWaitCondition()
        self.manual_input_value = None
        self.abort_flag = False

    def wait_for_manual_input(self, filename, default_text):
        self.input_mutex.lock()
        self.manual_input_value = None
        self.request_manual_input_signal.emit(filename, default_text or "")
        self.input_condition.wait(self.input_mutex)
        val = self.manual_input_value
        self.input_mutex.unlock()
        return val

    def set_manual_input(self, text, ok):
        self.input_mutex.lock()
        self.manual_input_value = (text, ok)
        self.input_condition.wakeAll()
        self.input_mutex.unlock()

    def run(self):
        count = len(self.file_list)
        for i, (widget_ref, file_path) in enumerate(self.file_list):
            if self.abort_flag: break

            self.progress_signal.emit(i + 1, count)
            
            basename = os.path.basename(file_path)
            self.log_signal.emit(f"[{i+1}/{count}] 処理中: {basename}")
            
            _, doi = PDFProcessor.extract_basic_info(file_path)
            info = None
            c_count = None
            
            if doi:
                self.log_signal.emit(f"  > DOI検出: {doi} -> API確認中...")
                c_count, _, _, info = ArticleFetcher.search(doi=doi)
                if isinstance(info, dict):
                    self.log_signal.emit("  > [API成功] DOIで特定しました。AI解析をスキップします。")
                else:
                    self.log_signal.emit(f"  > [API失敗] DOIで見つかりませんでした。AI解析へ移行します。")
                    doi = None

            title, authors, year = None, None, None
            source_is_llm = False
            
            if self.use_llm and not doi:
                self.log_signal.emit("  > AI解析中...")
                llm_res = self.llm_extractor.extract(file_path)
                if llm_res:
                    title = llm_res.get("title")
                    authors = llm_res.get("authors")
                    year = llm_res.get("year")
                    source_is_llm = True
                    self.log_signal.emit(f"  > AI検出(タイトル): {title}")
                    self.log_signal.emit(f"  > AI検出(著者): {authors}")

            if not isinstance(info, dict) and not title:
                if not self.use_llm and self.chk_auto_title:
                    self.log_signal.emit("  > 従来ロジックで解析中...")
                    title, authors, year = PDFProcessor.extract_heuristics(file_path)

            search_title = title
            search_author = authors
            search_doi = doi

            if self.manual_mode:
                text, ok = self.wait_for_manual_input(basename, title)
                if not ok: continue
                search_title = text
                search_author = None
                search_doi = None
                source_is_llm = False
            elif not doi and not title and not isinstance(info, dict):
                self.log_signal.emit(f"  > スキップ: 手掛かりなし")
                self.result_signal.emit(basename, {}, None, "タイトル/DOI不明")
                continue

            if not isinstance(info, dict) and (search_title or search_doi):
                c_count, _, _, info = ArticleFetcher.search(title=search_title, doi=search_doi, author=search_author)

            final_info = {}
            if isinstance(info, dict):
                self.log_signal.emit(f"  > [APIあり] 引用数: {c_count}")
                self.log_signal.emit(f"  >   Title: {info.get('title')}")
                
                if not doi and title and source_is_llm:
                    api_title = info.get("title", "")
                    similarity = PDFProcessor.check_similarity(title, api_title)
                    self.log_signal.emit(f"  > タイトル一致率: {similarity:.2f} (AI vs API)")
                    
                    if similarity < CONFIG["TITLE_SIMILARITY_THRESHOLD"]:
                        self.log_signal.emit("  > ★不一致警告: API結果を破棄し、AI結果を採用します。")
                        final_info = {"title": title, "authors": authors, "year": year, "citation_count": None}
                    else:
                        final_info = {"title": info.get("title"), "authors": info.get("authors"), "year": info.get("year"), "citation_count": c_count}
                else:
                    final_info = {"title": info.get("title"), "authors": info.get("authors"), "year": info.get("year"), "citation_count": c_count}
            elif title and authors:
                self.log_signal.emit("  > API検索失敗。AI抽出情報をそのまま使用します。")
                final_info = {"title": title, "authors": authors, "year": year, "citation_count": None}
            else:
                self.result_signal.emit(basename, {}, None, str(info) if info else "検索失敗")
                continue

            new_filename = PDFProcessor.generate_filename(final_info)
            try:
                dir_name = os.path.dirname(file_path)
                new_path = os.path.join(dir_name, new_filename)

                if os.path.exists(new_path) and os.path.normpath(new_path) != os.path.normpath(file_path):
                    base, ext = os.path.splitext(new_filename)
                    counter = 1
                    while os.path.exists(os.path.join(dir_name, f"{base} ({counter}){ext}")):
                        counter += 1
                    new_filename = f"{base} ({counter}){ext}"
                    new_path = os.path.join(dir_name, new_filename)

                os.rename(file_path, new_path)

                self.update_file_path_signal.emit(file_path, new_path)
                self.result_signal.emit(basename, final_info, new_filename, None)
                self.log_signal.emit(f"  > 成功: {new_filename}")

            except PermissionError:
                msg = "失敗: ファイルが開かれています。閉じてから再試行してください。"
                self.log_signal.emit(f"  > {msg}")
                self.result_signal.emit(basename, final_info, None, "ファイル使用中エラー")
            
            except Exception as e:
                self.log_signal.emit(f"  > リネーム失敗: {e}")
                self.result_signal.emit(basename, {}, None, str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        ui_path = resource_path("Namecle_UI.ui")
        if not os.path.exists(ui_path):
            QMessageBox.critical(self, "エラー", f"ファイルが見つかりません:\n{ui_path}")
            sys.exit()
            
        uic.loadUi(ui_path, self)

        self.setStyleSheet(MODERN_STYLESHEET)

        self.setWindowTitle(f"Namecle : Quick Article Renaming v{__version__}")
        
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)

        self.table.horizontalHeader().setFixedHeight(40)

        icon_path = resource_path(os.path.join("assets", "icon.png"))
        if os.path.exists(icon_path):
             self.setWindowIcon(QIcon(icon_path))

        icon_folder = qta.icon('fa5s.folder-open', color='black')
        self.btn_browse.setIcon(icon_folder)
        self.btn_select_model.setIcon(icon_folder)

        icon_play = qta.icon('fa5s.play', color='white')
        self.btn_auto.setIcon(icon_play)
        
        self.setAcceptDrops(True)
        
        self.settings = self.load_settings()
        self.line_model_path.setText(self.settings.get("model_path", ""))
        self.update_ui_state()

        self.btn_select_model.clicked.connect(self.select_model_file)
        self.btn_browse.clicked.connect(self.browse_files)
        self.btn_auto.clicked.connect(lambda: self.start_processing(manual=False))
        # self.btn_manual.clicked.connect(lambda: self.start_processing(manual=True))

        self.llm_extractor = None
        self.worker = None

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(QHeaderView.Interactive)

        fixed_width = 50
        for i in [1, 2, 3]:
            header.setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, fixed_width)

        for i in [0, 4, 6]:
            header.setSectionResizeMode(i, QHeaderView.Stretch)

        self.table.setColumnWidth(5, 100)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedWidth(200)

        self.statusbar.addPermanentWidget(self.progress_bar)

        self.progress_bar.hide()

        main_title = "Namecle : Quick Article Renaming"
        ver_text = f"v{__version__}"
        icon_path = resource_path(os.path.join("assets", "icon.png"))
        icon_display_size = 40

        if os.path.exists(icon_path):
            image = QImage(icon_path)

            scaled_image = image.scaled(
                icon_display_size * 2, 
                icon_display_size * 2, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )

            ba = QBuffer()
            ba.open(QIODevice.WriteOnly)
            scaled_image.save(ba, "PNG")
            base64_data = base64.b64encode(ba.data()).decode("utf-8")

            html_content = (
                f"<html><head/><body><p align='center'>"
                f"<img src='data:image/png;base64,{base64_data}' width='{icon_display_size}' height='{icon_display_size}' style='vertical-align:middle'/>"
                f"&nbsp;&nbsp;"
                f"<span style='font-size:20pt; font-weight:600; color:#1F2937;'>{main_title}</span>"
                f"&nbsp;"
                f"<span style='font-size:12pt; color:#6B7280;'>{ver_text}</span>"
                f"</p></body></html>"
            )
            self.label_title.setText(html_content)
        else:
            self.label_title.setText(f"{main_title} {ver_text}")

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"model_path": ""}

    def save_settings(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=4)

    def select_model_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "モデルファイルを選択", "", "GGUFモデル (*.gguf)")
        if path:
            self.settings["model_path"] = path
            self.line_model_path.setText(path)
            self.save_settings()
            self.update_ui_state() 
            self.rb_mode_llm.setChecked(True)
            
            self.log(f"モデルパスを保存しました: {path}")
            self.llm_extractor = None

    def update_ui_state(self):
        path = self.line_model_path.text()
        has_valid_path = bool(path and os.path.exists(path))

        self.rb_mode_llm.setEnabled(has_valid_path)

        if not has_valid_path and self.rb_mode_llm.isChecked():
            self.rb_mode_legacy.setChecked(True)

        if not has_valid_path:
            self.rb_mode_llm.setToolTip("モデルファイル (.gguf) を選択すると有効になります")
        else:
            self.rb_mode_llm.setToolTip("")

    def log(self, msg):
        self.log_text.append(msg)
        QApplication.processEvents()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        for url in e.mimeData().urls():
            if url.toLocalFile().lower().endswith(".pdf"):
                self.add_file_item(url.toLocalFile())
        e.acceptProposedAction()

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDF", "", "PDF (*.pdf)")
        for f in files: self.add_file_item(f)

    def add_file_item(self, path):
        norm_path = os.path.normpath(path)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget and os.path.normpath(widget.file_path) == norm_path:
                self.log(f"重複スキップ: {os.path.basename(path)}")
                return
        item = QListWidgetItem()
        widget = FileItemWidget(path, lambda w: self.remove_file_item(w))
        item.setSizeHint(widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def remove_file_item(self, widget):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if self.list_widget.itemWidget(item) is widget:
                self.list_widget.takeItem(i)
                break

    def _prepare_llm(self):
        if not HAS_LLAMA:
            self.log("【エラー】llama-cpp-python がありません。")
            return False
        
        model_path = self.settings.get("model_path")
        if not model_path or not os.path.exists(model_path):
            self.log("【エラー】有効なモデルファイルが選択されていません。")
            QMessageBox.warning(self, "エラー", "先にLLM設定からモデルファイル (.gguf) を選択してください。")
            return False
            
        if not self.llm_extractor:
            self.log("Loading LLM...")
            QApplication.processEvents()
            try:
                self.llm_extractor = GemmaSmartExtractor(model_path)
                self.log("LLM Loaded successfully.")
            except Exception as e:
                self.log(f"Loading failed: {e}")
                return False
        return True

    def start_processing(self, manual=False):
        count = self.list_widget.count()
        if count == 0: return
        self.table.setRowCount(0)

        self.btn_auto.setEnabled(False)
        # self.btn_manual.setEnabled(False)

        use_llm = self.rb_mode_llm.isChecked()

        use_legacy_logic = True

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if use_llm and not self._prepare_llm():
                use_llm = False
                self.rb_mode_legacy.setChecked(True)
                self.log("LLMのロードに失敗したため、Legacyモードで実行します。")
        finally:
            QApplication.restoreOverrideCursor()
        file_list = []
        for i in range(count):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            file_list.append((widget, widget.file_path))

        self.worker = RenameWorker(
            file_list, 
            use_llm, 
            manual, 
            use_legacy_logic,
            self.llm_extractor
        )
        
        self.worker.progress_signal.connect(self.update_progress)

        self.worker.log_signal.connect(self.log)
        self.worker.result_signal.connect(self.add_result_row)
        self.worker.update_file_path_signal.connect(self.update_widget_path)
        self.worker.request_manual_input_signal.connect(self.handle_manual_input)
        self.worker.finished.connect(self.on_process_finished)
        
        self.worker.start()

    def handle_manual_input(self, filename, default_text):
        text, ok = QInputDialog.getText(self, "タイトル入力", f"ファイル: {filename}\nタイトル:", text=default_text)
        if self.worker:
            self.worker.set_manual_input(text, ok)

    def update_widget_path(self, old_path, new_path):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget and widget.file_path == old_path:
                widget.file_path = new_path
                widget.label.setText(new_path)
                break

    def on_process_finished(self):
        self.log("=== 全処理完了 ===")
        self.btn_auto.setEnabled(True)
        # self.btn_manual.setEnabled(True)
        self.progress_bar.hide()
        self.statusbar.showMessage("すべての処理が完了しました。", 5000)
        
        self.worker = None

    def update_progress(self, current, total):
        if self.progress_bar.isHidden():
            self.progress_bar.show()
        
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

        self.statusbar.showMessage(f"処理中... ({current}/{total})")

    def add_result_row(self, original_name, info, new_name, error):
        row = self.table.rowCount()
        self.table.insertRow(row)
        if error:
            item = QTableWidgetItem(f"{original_name} : {error}")
            item.setForeground(QBrush(Qt.red))
            self.table.setItem(row, 0, item)
            self.table.setSpan(row, 0, 1, 7)
        else:
            self.table.setItem(row, 0, QTableWidgetItem(original_name))
            self.table.setItem(row, 1, QTableWidgetItem(str(info.get("year", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(info.get("グレード", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(str(info.get("citation_count", "N/A"))))
            self.table.setItem(row, 4, QTableWidgetItem(info.get("title", "")))
            self.table.setItem(row, 5, QTableWidgetItem(info.get("authors", "")))
            self.table.setItem(row, 6, QTableWidgetItem(str(new_name)))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    wnd = MainWindow()
    wnd.show()
    sys.exit(app.exec_())