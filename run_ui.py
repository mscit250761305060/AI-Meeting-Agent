import sys
import threading

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow

from meeting_engine.whisper_worker import start_whisper_worker

# threading.Thread(
#     target=start_whisper_worker,
#     daemon=True
# ).start()

app = QApplication(sys.argv)

window = MainWindow()

window.show()

app.exec()