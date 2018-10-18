#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os.path
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QAbstractItemView, QHeaderView, \
    QTableWidget, QTableWidgetItem, QHBoxLayout, QPushButton, QCheckBox, QLabel, QProgressBar, \
    QSpinBox, QScrollArea, QDialog, QLineEdit
from PyQt5.Qt import QPixmap, QIcon


class TabGovernance_gui(QWidget):
    def __init__(self, caller, *args, **kwargs):
        QWidget.__init__(self)
        self.caller = caller
        self.initLayout()
        self.loadIcons()
        self.refreshTorrents_btn.setIcon(self.refresh_icon)
        self.budgetProjection_btn.setIcon(self.list_icon)
        self.timeIconLabel.setPixmap(self.time_icon.scaledToHeight(20, Qt.SmoothTransformation))
        self.questionLabel.setPixmap(self.question_pixmap.scaledToHeight(15, Qt.SmoothTransformation))
        self.loadCacheData()
        
        
    def initLayout(self):
        layout = QVBoxLayout()
        #layout.setContentsMargins(10, 10, 10, 10)
        #layout.setSpacing(13)
        #layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        
        ## -- ROW 1
        row = QHBoxLayout()
        self.search_label = QLabel("<b><i>Search:<i></b>")
        self.search_label.setStyleSheet('color: #003366')
        self.search_textbox = QLineEdit()
        #self.search_textbox.setFixedWidth(300)
        self.is_regex_label = QLabel("Regex?")
        self.is_regex_checkbox = QCheckBox()
        row.addWidget(self.search_label)
        row.addWidget(self.search_textbox)
        row.addWidget(self.is_regex_label)
        row.addWidget(self.is_regex_checkbox)
        self.refreshTorrents_btn = QPushButton()
        self.refreshTorrents_btn.setToolTip("Refresh Proposal List")
        row.addWidget(self.refreshTorrents_btn)
        self.budgetProjection_btn = QPushButton()
        row.addStretch(1)
        self.refreshingLabel = QLabel("<em><b style='color:red'>Searching magnet db...</b></em>")
        self.refreshingLabel.hide()
        row.addWidget(self.refreshingLabel)
        row.addStretch(1)
        self.budgetProjection_btn.setToolTip("Check Budget Projection...")
        row.addWidget(self.budgetProjection_btn)
        self.selectMN_btn = QPushButton("Select Masternodes...")
        row.addWidget(self.selectMN_btn)
        self.selectedMNlabel = QLabel("<em>0 masternodes selected for voting</em>")
        row.addWidget(self.selectedMNlabel)
        self.mnCountLabel = QLabel()
        row.addWidget(self.mnCountLabel)

        self.toggleExpiring_btn = QPushButton("Hide Expiring")
        self.toggleExpiring_btn.setToolTip("Hide expiring torrents (yellow background) from list")
        row.addWidget(self.toggleExpiring_btn)
        layout.addLayout(row)


        ## -- ROW 2
        self.torrentBox = QTableWidget()
        self.torrentBox.setMinimumHeight(280)
        self.torrentBox.setSelectionMode(QAbstractItemView.MultiSelection)
        self.torrentBox.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.torrentBox.setShowGrid(True)
        self.torrentBox.setColumnCount(9)
        self.torrentBox.setRowCount(0)
        self.torrentBox.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.torrentBox.setSortingEnabled(True)
        self.torrentBox.column_name = 0
        self.torrentBox.column_play = 1
        self.torrentBox.column_dl = 2
        self.torrentBox.column_qmc_per_month = 3
        self.torrentBox.column_payments = 4
        self.torrentBox.column_votes = 5
        self.torrentBox.column_sl = 6
        self.torrentBox.column_hash = 7
        self.torrentBox.column_url = 8
        #self.torrentBox.verticalHeader().hide
        self.setTorrentBoxHeader()
        self.torrentBox.setColumnWidth(self.torrentBox.column_name, 100)
        self.torrentBox.setColumnWidth(self.torrentBox.column_play, 50)
        self.torrentBox.setColumnWidth(self.torrentBox.column_dl, 50)
        self.torrentBox.setColumnWidth(self.torrentBox.column_qmc_per_month, 100)
        self.torrentBox.setColumnWidth(self.torrentBox.column_payments, 150)
       # self.torrentBox.setColumnWidth(6, 120)
        self.torrentBox.setColumnWidth(self.torrentBox.column_votes, 50)
        self.torrentBox.setColumnHidden(self.torrentBox.column_hash, True)
        self.torrentBox.setColumnHidden(self.torrentBox.column_url, True)
        layout.addWidget(self.torrentBox)

        ## -- ROW 3
        row = QHBoxLayout()      
        self.timeIconLabel = QLabel()
        self.timeIconLabel.setToolTip("Check to add a randomized time offset (positive or negative) to enhance privacy")
        row.addWidget(self.timeIconLabel)
        self.randomDelayCheck = QCheckBox()
        self.randomDelayCheck.setToolTip("Check to add a randomized time offset when voting (max +5/-5 hrs)")
        row.addWidget(self.randomDelayCheck)
        self.randomDelayNeg_edt = QSpinBox()
        self.randomDelayNeg_edt.setPrefix('- ')
        self.randomDelayNeg_edt.setSuffix(" secs")
        self.randomDelayNeg_edt.setToolTip("Maximum random time (in seconds) subtracted from each vote timestamp")
        self.randomDelayNeg_edt.setFixedWidth(100)
        self.randomDelayNeg_edt.setMaximum(18000)
        self.randomDelayNeg_edt.setValue(0)
        row.addWidget(self.randomDelayNeg_edt)
        self.randomDelayPos_edt = QSpinBox()
        self.randomDelayPos_edt.setPrefix("+ ")
        self.randomDelayPos_edt.setSuffix(" secs")
        self.randomDelayPos_edt.setToolTip("Maximum random time (in seconds) added to each vote timestamp")
        self.randomDelayPos_edt.setFixedWidth(100)
        self.randomDelayPos_edt.setMaximum(18000)
        self.randomDelayPos_edt.setValue(300)
        row.addWidget(self.randomDelayPos_edt)
        row.addStretch(1)
        self.loadingLine = QLabel("<b style='color:red'>Vote Signatures.</b> Completed: ")
        self.loadingLinePercent = QProgressBar()
        self.loadingLinePercent.setMaximumWidth(200)
        self.loadingLinePercent.setMaximumHeight(10)
        self.loadingLinePercent.setRange(0, 100)
        row.addWidget(self.loadingLine)
        row.addWidget(self.loadingLinePercent)
        self.loadingLine.hide()
        self.loadingLinePercent.hide()
        row.addStretch(1)
        self.selectedPropLabel = QLabel("<em>0 torrents selected</em>")
        row.addWidget(self.selectedPropLabel)
        self.questionLabel = QLabel()
        message = "Refresh torrents.\n"
        message += "GREEN: torrent passing\n"
        message += "WHITE: missing votes in order to pass\n"
        message += "RED: torrent not passing\n"
        message += "YELLOW: torrent expiring (last payment block)\n"
        self.questionLabel.setToolTip(message)
        row.addWidget(self.questionLabel)
        layout.addLayout(row)

        ## -- ROW 4
        row = QHBoxLayout()
        self.voteYes_btn = QPushButton("Vote Good!")
        self.voteYes_btn.setToolTip("Vote this as a quality torrent")
        row.addWidget(self.voteYes_btn)
        #self.voteAbstain_btn = QPushButton("Vote ABSTAIN")
        #self.voteAbstain_btn.setToolTip("Vote ABSTAIN on selected torrents [currently disabled]")
        #row.addWidget(self.voteAbstain_btn)
        self.voteNo_btn = QPushButton("Vote Bad!")
        self.voteNo_btn.setToolTip("Vote this for spam, low quality or highly offensive files")
        row.addWidget(self.voteNo_btn)
        layout.addLayout(row)

        self.setLayout(layout)
    
    
    
    def loadCacheData(self):
        if self.caller.parent.cache.get("votingDelayCheck"):
            negative_delay = self.caller.parent.cache.get("votingDelayNeg")
            positive_delay = self.caller.parent.cache.get("votingDelayPos")
            self.randomDelayCheck.setChecked(True)
            self.randomDelayNeg_edt.setValue(negative_delay)
            self.randomDelayPos_edt.setValue(positive_delay)
    
    
    def setTorrentBoxHeader(self):
        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)
        item.setText("Name")
        item.setToolTip("Torrent Name")
        self.torrentBox.setHorizontalHeaderItem(self.torrentBox.column_name, item)

        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)
        item.setText("P")
        self.torrentBox.setHorizontalHeaderItem(self.torrentBox.column_play, item)

        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)
        item.setText("D")
        self.torrentBox.setHorizontalHeaderItem(self.torrentBox.column_dl, item)

        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)
        item.setText("QMC/month")
        item.setToolTip("Monthly QMC Payment requested")
        self.torrentBox.setHorizontalHeaderItem(self.torrentBox.column_qmc_per_month, item)
        
        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)
        item.setText("Payments")
        item.setToolTip("Remaining Payment Count / Total Payment Count")
        self.torrentBox.setHorizontalHeaderItem(self.torrentBox.column_payments, item)
        
        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)
        item.setText("Votes")
        item.setToolTip("Network Votes: Good/ABSTAINS/Bad")
        self.torrentBox.setHorizontalHeaderItem(self.torrentBox.column_votes, item)

        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)
        item.setText("Hash")
        item.setToolTip("Not supported yet")
        self.torrentBox.setHorizontalHeaderItem(self.torrentBox.column_sl, item)
        
        
    def loadIcons(self):
        self.refresh_icon = QIcon(os.path.join(self.caller.imgDir, 'icon_refresh.png'))
        self.time_icon = QPixmap(os.path.join(self.caller.imgDir, 'icon_clock.png'))
        self.link_icon = QIcon(os.path.join(self.caller.imgDir, 'icon_link.png'))
        self.search_icon = QIcon(os.path.join(self.caller.imgDir, 'icon_search.png'))
        self.list_icon = QIcon(os.path.join(self.caller.imgDir, 'icon_list.png'))
        self.question_pixmap = QPixmap(os.path.join(self.caller.imgDir, 'icon_question.png'))
        self.question_icon = QIcon(os.path.join(self.caller.imgDir, 'icon_question.png'))
        
        
        
        
class ScrollMessageBox(QDialog):
    def __init__(self, main_wnd, message):
        QDialog.__init__(self, parent=main_wnd)
        self.setWindowTitle("Confirm Votes")
        scroll = QScrollArea()
        scroll.setMinimumHeight(280)
        scroll.setMaximumHeight(280)
        scroll.setMinimumWidth(500)
        scroll.setWidget(QLabel(message))
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        lay = QVBoxLayout()
        lay.addWidget(scroll)
        row = QHBoxLayout()
        self.yes_btn = QPushButton("Yes")
        self.no_btn = QPushButton("No")
        self.yes_btn.clicked.connect(lambda: self.accept())
        self.no_btn.clicked.connect(lambda: self.reject())
        row.addWidget(self.yes_btn)
        row.addWidget(self.no_btn)
        lay.addLayout(row)
        self.setLayout(lay)
        
        
