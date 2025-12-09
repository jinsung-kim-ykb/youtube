import sys
import requests
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QLabel, QMessageBox, QScrollArea)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import yt_dlp

# ----------------------------------------------
# 1. 영상 정보를 가져오는 쓰레드 (검색용) - 기존과 동일
# ----------------------------------------------
class InfoWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        ydl_opts = {'quiet': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                video_data = {
                    'title': info.get('title', '제목 없음'),
                    'thumbnail_url': info.get('thumbnail', ''),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'url': self.url
                }
                if video_data['thumbnail_url']:
                    response = requests.get(video_data['thumbnail_url'])
                    if response.status_code == 200:
                        image = QImage()
                        image.loadFromData(response.content)
                        video_data['image_data'] = image
                    else:
                        video_data['image_data'] = None
                self.finished.emit(video_data)
        except Exception as e:
            self.error.emit(str(e))

# ----------------------------------------------
# 2. 영상을 다운로드하는 쓰레드 (수정됨: 1080p 우선)
# ----------------------------------------------
class DownloadWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        # 현재 실행 파일이 있는 폴더 경로
        save_path = os.getcwd()

        ydl_opts = {
            # 파일명 형식: 제목.확장자
            'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'),
            
            # [화질 설정 핵심 부분]
            # bestvideo[height<=1080]: 높이가 1080 이하인 것 중 최고 화질 (즉, 4K는 제외하고 1080p, 없으면 720p 선택)
            # +bestaudio: 최고 음질 선택
            # merge_output_format: 최종 결과물을 mp4로 합침
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'merge_output_format': 'mp4',
            
            # 진행 상황 표시용 (콘솔 출력 끄기)
            'quiet': True,
            'no_warnings': True,
        }

        try:
            self.progress.emit("다운로드 시작... (고화질 변환 중)")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.progress.emit("다운로드 완료!")
            self.finished.emit()
        except Exception as e:
            self.progress.emit(f"에러 발생: {str(e)}")
            self.finished.emit()

# ----------------------------------------------
# 3. 메인 윈도우 UI - 기존과 동일
# ----------------------------------------------
class YoutubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.current_url = ""

    def initUI(self):
        main_layout = QVBoxLayout()
        
        # 상단
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("유튜브 링크를 붙여넣으세요")
        self.search_btn = QPushButton("조회")
        self.search_btn.clicked.connect(self.start_search)
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.search_btn)
        main_layout.addLayout(input_layout)

        # 중단
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setMinimumHeight(200)
        self.thumbnail_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        self.thumbnail_label.setText("썸네일 영역")
        main_layout.addWidget(self.thumbnail_label)

        self.title_label = QLabel("제목: -")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.title_label.setWordWrap(True)
        main_layout.addWidget(self.title_label)

        self.stats_label = QLabel("조회수: - / 좋아요: -")
        main_layout.addWidget(self.stats_label)

        # 하단
        self.download_btn = QPushButton("다운로드 (Full HD)")
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet("background-color: #ff0000; color: white; font-weight: bold; padding: 10px;")
        self.download_btn.clicked.connect(self.start_download)
        main_layout.addWidget(self.download_btn)

        self.status_label = QLabel("대기 중")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)
        self.setWindowTitle('유튜브 고화질 다운로더')
        self.resize(400, 500)
        self.show()

    def start_search(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "경고", "주소를 입력해주세요!")
            return
        self.status_label.setText("정보 조회 중...")
        self.search_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.info_worker = InfoWorker(url)
        self.info_worker.finished.connect(self.on_search_finished)
        self.info_worker.error.connect(self.on_search_error)
        self.info_worker.start()

    def on_search_finished(self, data):
        self.current_url = data['url']
        self.title_label.setText(f"제목: {data['title']}")
        views = f"{data['view_count']:,}" if data['view_count'] else "0"
        likes = f"{data['like_count']:,}" if data['like_count'] else "정보 없음"
        self.stats_label.setText(f"조회수: {views}회 / 좋아요: {likes}")
        if data['image_data']:
            pixmap = QPixmap.fromImage(data['image_data'])
            scaled_pixmap = pixmap.scaled(self.thumbnail_label.width(), self.thumbnail_label.height(), 
                                          Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled_pixmap)
            self.thumbnail_label.setText("")
        else:
            self.thumbnail_label.setText("썸네일 없음")
        self.status_label.setText("조회 완료")
        self.search_btn.setEnabled(True)
        self.download_btn.setEnabled(True)

    def on_search_error(self, err_msg):
        self.status_label.setText("에러")
        QMessageBox.critical(self, "에러", f"실패: {err_msg}")
        self.search_btn.setEnabled(True)

    def start_download(self):
        self.status_label.setText("다운로드 시작...")
        self.download_btn.setEnabled(False)
        self.search_btn.setEnabled(False)
        self.download_worker = DownloadWorker(self.current_url)
        self.download_worker.progress.connect(self.update_status)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.start()

    def update_status(self, msg):
        self.status_label.setText(msg)

    def on_download_finished(self):
        self.download_btn.setEnabled(True)
        self.search_btn.setEnabled(True)
        QMessageBox.information(self, "완료", "다운로드가 완료되었습니다.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = YoutubeDownloader()
    sys.exit(app.exec_())