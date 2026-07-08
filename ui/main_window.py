from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton
)

from agents.ui_event_agent import (
    register_transcript_callback
)

import server.meeting_state as meeting_state


class MainWindow(QWidget):
    def update_transcript(self, text):

        self.transcript_box.append(text)

    def start_meeting(self):

        if self.meeting_running:
            return

        if not meeting_state.begin_meeting():
            return

        self.meeting_running = True
        self.status_label.setText(
            "🎤 Listening..."
        )

        meeting_state.start_runtime()
        print("Meeting Started")


    def stop_meeting(self):

        if not self.meeting_running:
            return

        self.meeting_running = False
        meeting_state.end_meeting()

        self.status_label.setText(
            "Idle"
        )

        print("Meeting Stopped")

    def __init__(self):

        super().__init__()

        self.meeting_running = False

        self.setWindowTitle(
            "AI Meeting Assistant"
        )

        self.resize(900, 600)

        self.setStyleSheet("""

        QWidget{

            font-size:14px;

        }

        QPushButton{

            padding:10px;

            font-weight:bold;

        }

        QTextEdit{

            background:white;

        }

        QLabel{

            font-weight:bold;

        }

        """)

        layout = QVBoxLayout()

        title = QLabel(
            "AI Meeting Assistant"
        )

        layout.addWidget(title)

        transcript_label = QLabel(
            "🎙 Live Transcript"
        )

        layout.addWidget(
            transcript_label
        )

        button_layout = QHBoxLayout()

        self.start_button = QPushButton(
            "🎤 Start Meeting"
        )

        self.stop_button = QPushButton(
            "⏹ Stop Meeting"
        )

        button_layout.addWidget(
            self.start_button
        )

        button_layout.addWidget(
            self.stop_button
        )

        layout.addLayout(
            button_layout
        )

        self.transcript_box = QTextEdit()

        self.transcript_box.setReadOnly(
            True
        )

        status_title = QLabel(
            "🤖 AI Status"
        )

        layout.addWidget(
            status_title
        )

        self.status_label = QLabel(
            "Idle"
        )

        layout.addWidget(
            self.status_label
        )

        layout.addWidget(
            self.transcript_box
        )

        self.transcript_box.append(
            "Create Employee Management System"
        )

        self.transcript_box.append(
            "Add Dashboard"
        )

        self.transcript_box.append(
            "Add Search Bar"
        )

        self.start_button.clicked.connect(
            self.start_meeting
        )

        self.stop_button.clicked.connect(
            self.stop_meeting
        )

        self.setLayout(layout)

        register_transcript_callback(
            self.update_transcript
        )