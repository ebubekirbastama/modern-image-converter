#!/usr/bin/env python3
"""
EBS Modern Resim Dönüştürücü - PyQt5 (Metro Tasarım + Dark/Light Tema + Boyut Optimizasyonu)
Özellikler:
- Sürükle & bırak veya dosya / klasör ekleme
- Toplu dönüştürme
- Kalite ayarı ve alfa gömme
- Dosya boyutunu optimize etme (maksimum boyuta göre küçültme)
- Dark / Light tema geçişi
- Emoji / Metro ikonları
- İlerleme çubuğu ve sonuç kutusu
"""

import sys, os
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from PyQt5 import QtCore, QtGui, QtWidgets

SUPPORTED_EXT = ["png", "jpg", "jpeg", "bmp", "gif", "tiff", "webp"]

class ConverterWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal(list)
    def __init__(self, tasks, out_dir, target_format, quality, flatten_alpha, optimize_size):
        super().__init__()
        self.tasks, self.out_dir = tasks, out_dir
        self.target_format, self.quality = target_format.lower(), int(quality)
        self.flatten_alpha = flatten_alpha
        self.optimize_size = optimize_size

    def run(self):
        results = []
        total = len(self.tasks)
        for i, path in enumerate(self.tasks, 1):
            try:
                img = Image.open(path)
                out_name = Path(path).stem + "." + self.target_format
                out_path = Path(self.out_dir) / out_name
                save_kwargs = {}

                if self.target_format in ("jpg","jpeg"):
                    # Alfa kanalı varsa beyaza gömme
                    if img.mode in ("RGBA","LA") or (img.mode=="P" and "transparency" in img.info):
                        if self.flatten_alpha:
                            background = Image.new("RGB", img.size, (255,255,255))
                            if img.mode=="RGBA":
                                background.paste(img, mask=img.split()[3])
                            else:
                                background.paste(img)
                            img = background
                        else:
                            img = img.convert("RGB")
                    else:
                        img = img.convert("RGB")
                    save_kwargs["quality"]=self.quality
                    save_kwargs["subsampling"]=0
                    if self.optimize_size:
                        save_kwargs["optimize"]=True
                    img.save(out_path, format="JPEG", **save_kwargs)

                elif self.target_format=="webp":
                    save_kwargs["quality"]=self.quality
                    if self.optimize_size: save_kwargs["method"]=6
                    img.save(out_path, format="WEBP", **save_kwargs)

                else:
                    if self.optimize_size:
                        save_kwargs["optimize"]=True
                    img.save(out_path, format=self.target_format.upper(), **save_kwargs)

                results.append((path,str(out_path),None))

            except UnidentifiedImageError:
                results.append((path,None,"Tanımlanamayan resim veya desteklenmeyen dosya"))
            except Exception as e:
                results.append((path,None,str(e)))

            self.progress.emit(int((i/total)*100))
        self.finished.emit(results)

class DropListWidget(QtWidgets.QListWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True); self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dragMoveEvent(self,event): event.acceptProposedAction()
    def dropEvent(self,event):
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if os.path.isdir(path):
                for root,_,files in os.walk(path):
                    for f in files:
                        if f.split('.')[-1].lower() in SUPPORTED_EXT: self.addItem(os.path.join(root,f))
            else:
                if Path(path).suffix.lower().lstrip('.') in SUPPORTED_EXT: self.addItem(path)

class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🖼️ EBS Modern Resim Dönüştürücü — Metro UI")
        self.setMinimumSize(780,520)
        self.setWindowIcon(QtGui.QIcon())
        self.dark_mode = False
        self.setup_ui()
        self.apply_styles()
        self.output_folder = str(Path.cwd()/ "Donusturulenler")
        Path(self.output_folder).mkdir(parents=True, exist_ok=True)
        self.out_folder_label.setText(self.output_folder)
        self.worker = None

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QLabel("🖼️ EBS Modern Resim Dönüştürücü")
        header.setObjectName("header"); header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(header)
        main = QtWidgets.QHBoxLayout()

        # Sol
        left = QtWidgets.QVBoxLayout()
        self.file_list = DropListWidget()
        left.addWidget(self.file_list)
        file_buttons = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("📁 Dosya Ekle"); add_btn.clicked.connect(self.add_files)
        add_folder = QtWidgets.QPushButton("📂 Klasör Ekle"); add_folder.clicked.connect(self.add_folder)
        remove_btn = QtWidgets.QPushButton("❌ Seçileni Sil"); remove_btn.clicked.connect(self.remove_selected)
        clear_btn = QtWidgets.QPushButton("🧹 Temizle"); clear_btn.clicked.connect(self.file_list.clear)
        file_buttons.addWidget(add_btn); file_buttons.addWidget(add_folder); file_buttons.addWidget(remove_btn); file_buttons.addWidget(clear_btn)
        left.addLayout(file_buttons)
        main.addLayout(left,3)

        # Sağ
        right = QtWidgets.QVBoxLayout()
        card = QtWidgets.QFrame(); card.setObjectName("card"); card_layout = QtWidgets.QVBoxLayout(card)
        fmt_layout = QtWidgets.QHBoxLayout(); fmt_label = QtWidgets.QLabel("🎯 Hedef format:")
        self.format_combo = QtWidgets.QComboBox(); self.format_combo.addItems(["png","jpg","webp","bmp","tiff","gif"])
        fmt_layout.addWidget(fmt_label); fmt_layout.addWidget(self.format_combo); card_layout.addLayout(fmt_layout)

        q_layout = QtWidgets.QHBoxLayout(); q_label = QtWidgets.QLabel("⚡ Kalite:")
        self.quality_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.quality_slider.setRange(10,100); self.quality_slider.setValue(95)
        self.quality_value = QtWidgets.QLabel("95"); self.quality_slider.valueChanged.connect(lambda v:self.quality_value.setText(str(v)))
        q_layout.addWidget(q_label); q_layout.addWidget(self.quality_slider); q_layout.addWidget(self.quality_value); card_layout.addLayout(q_layout)

        self.flatten_check = QtWidgets.QCheckBox("⚪ Alfa kanalı desteklenmeyen formatlarda beyaza göm (JPG)"); self.flatten_check.setChecked(True)
        card_layout.addWidget(self.flatten_check)

        self.optimize_check = QtWidgets.QCheckBox("📉 Dosya boyutunu optimize et"); self.optimize_check.setChecked(False)
        card_layout.addWidget(self.optimize_check)

        out_layout = QtWidgets.QHBoxLayout(); out_label = QtWidgets.QLabel("📂 Çıkış klasörü:")
        self.out_folder_label = QtWidgets.QLabel("")
        out_browse = QtWidgets.QPushButton("📌 Seç"); out_browse.clicked.connect(self.browse_output)
        out_open = QtWidgets.QPushButton("📂 Aç"); out_open.clicked.connect(self.open_output)
        out_layout.addWidget(out_label); out_layout.addWidget(self.out_folder_label); out_layout.addWidget(out_browse); out_layout.addWidget(out_open)
        card_layout.addLayout(out_layout)

        self.convert_btn = QtWidgets.QPushButton("🔄 Dönüştür"); self.convert_btn.setObjectName("primary"); self.convert_btn.clicked.connect(self.start_conversion)
        card_layout.addWidget(self.convert_btn)

        self.theme_btn = QtWidgets.QPushButton("🌙 Dark/Light Tema"); self.theme_btn.clicked.connect(self.toggle_theme)
        card_layout.addWidget(self.theme_btn)

        self.progress = QtWidgets.QProgressBar(); self.progress.setValue(0); card_layout.addWidget(self.progress)
        self.results_box = QtWidgets.QTextEdit(); self.results_box.setReadOnly(True); self.results_box.setFixedHeight(120)
        card_layout.addWidget(self.results_box)

        right.addWidget(card); main.addLayout(right,2)
        layout.addLayout(main)
        footer = QtWidgets.QLabel("📂 Resimleri listeye sürükleyip bırakabilirsiniz. Toplu dönüştürme desteklenir."); footer.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(footer)

    def apply_styles(self):
        base = """
        QWidget{font-family: 'Segoe UI', Tahoma, sans-serif;}
        #header{font-size:20pt; font-weight:600; padding:12px}
        QFrame#card{background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #ffffff, stop:1 #f3f6f8); border-radius:10px; padding:10px}
        QPushButton{padding:8px 12px; border-radius:8px}
        QPushButton#primary{background: #0078d7; color: white; font-weight:600}
        QListWidget{background:#ffffff; border:1px solid #dcdcdc; border-radius:8px}
        QProgressBar{height:16px; border-radius:8px}
        QTextEdit{background:#ffffff; border:1px solid #dcdcdc; border-radius:8px}
        QLabel{font-size:10pt}
        """
        dark = """
        QFrame#card{background:#2e2e2e}
        QListWidget{background:#3e3e3e; color:white}
        QTextEdit{background:#3e3e3e; color:white}
        QLabel{color:white}
        """
        self.setStyleSheet(base + (dark if self.dark_mode else ""))

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_styles()

    def add_files(self):
        files,_ = QtWidgets.QFileDialog.getOpenFileNames(self,"Resim seç",str(Path.home()),"Resimler (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp)")
        for f in files: self.file_list.addItem(f)

    def add_folder(self):
        folder=QtWidgets.QFileDialog.getExistingDirectory(self,"Klasör seç",str(Path.home()))
        if folder:
            for root,_,files in os.walk(folder):
                for f in files:
                    if f.split('.')[-1].lower() in SUPPORTED_EXT: self.file_list.addItem(os.path.join(root,f))

    def remove_selected(self):
        for item in self.file_list.selectedItems(): self.file_list.takeItem(self.file_list.row(item))

    def browse_output(self):
        folder=QtWidgets.QFileDialog.getExistingDirectory(self,"Çıkış klasörü seç",self.output_folder)
        if folder: self.output_folder=folder; self.out_folder_label.setText(folder)

    def open_output(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.output_folder))

    def start_conversion(self):
        items=[self.file_list.item(i).text() for i in range(self.file_list.count())]
        if not items: QtWidgets.QMessageBox.warning(self,"Dosya yok","Lütfen dönüştürülecek resimleri ekleyin."); return
        target_format=self.format_combo.currentText()
        quality=self.quality_slider.value()
        flatten=self.flatten_check.isChecked()
        optimize=self.optimize_check.isChecked()
        Path(self.output_folder).mkdir(parents=True, exist_ok=True)
        self.results_box.clear(); self.progress.setValue(0); self.convert_btn.setEnabled(False)
        self.worker=ConverterWorker(items,self.output_folder,target_format,quality,flatten,optimize)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self,results):
        good=0
        for src,out,err in results:
            if out: self.results_box.append(f"✅ {src} -> {out}"); good+=1
            else: self.results_box.append(f"❌ {src} -> {err}")
        self.results_box.append(f"\nTamamlandı. {good}/{len(results)} başarılı.")
        self.progress.setValue(100)
        self.convert_btn.setEnabled(True)

if __name__=="__main__":
    app=QtWidgets.QApplication(sys.argv)
    win=MainWindow()
    win.show()
    sys.exit(app.exec_())
