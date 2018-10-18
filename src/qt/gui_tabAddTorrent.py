from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QLabel, QComboBox, QPushButton


class TabAddTorrent_gui(QWidget):
    def __init__(self, caller):
        QWidget.__init__(self)

        self.caller = caller

        vertical_group = QVBoxLayout()

        horizontal_group_1 = QHBoxLayout()
        self.fileNameLabel = QLabel("File name:")
        self.fileNameTextBox = QLineEdit()
        horizontal_group_1.addWidget(self.fileNameLabel)
        horizontal_group_1.addWidget(self.fileNameTextBox)
        vertical_group.addLayout(horizontal_group_1)

        horizontal_group_2 = QHBoxLayout()
        self.magnetUriLabel = QLabel("Magnet URI:")
        self.magnetUriTextBox = QLineEdit()

        horizontal_group_2.addWidget(self.magnetUriLabel)
        horizontal_group_2.addWidget(self.magnetUriTextBox)
        vertical_group.addLayout(horizontal_group_2)

        horizontal_group_22 = QHBoxLayout()
        self.paymentLabel = QLabel("QMC Payment Address:")
        self.paymentTextBox = QLineEdit()

        horizontal_group_22.addWidget(self.paymentLabel)
        horizontal_group_22.addWidget(self.paymentTextBox)
        vertical_group.addLayout(horizontal_group_22)

        horizontal_group_3 = QHBoxLayout()
        self.categoryLabel = QLabel("Category:")
        self.categorySelect = QComboBox()
        self.categorySelect.addItem("Video")
        self.categorySelect.addItem("Audio")
        self.categorySelect.addItem("App")
        self.categorySelect.addItem("Game")
        self.categorySelect.addItem("eBook")
        self.categorySelect.addItem("Document")
        self.categorySelect.addItem("Leak")
        self.categorySelect.addItem("Other")

        horizontal_group_3.addWidget(self.categoryLabel)
        horizontal_group_3.addWidget(self.categorySelect)
        vertical_group.addLayout(horizontal_group_3)

        horizontal_group_4 = QHBoxLayout()
        self.submitBtn = QPushButton("Submit torrent")
        horizontal_group_4.addWidget(self.submitBtn)
        vertical_group.addLayout(horizontal_group_4)

        horizontal_group_5 = QHBoxLayout()
        self.torrentWarningLabel = QLabel("""Submission requires 3 confirmations to process.\nDo not close the tool until 3 blocks pass since your last submission !\n\nAlso be aware that this function is in beta stage,\none known issue is submitting multiple links too fast.\nTry to only submit multipled by the same number of cores your device has and waiting for 3 blocks.""")
        horizontal_group_5.addWidget(self.torrentWarningLabel)
        vertical_group.addLayout(horizontal_group_5)

        self.setLayout(vertical_group)
