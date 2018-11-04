#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from queue import Queue
from time import gmtime, strftime

import os.path
from PyQt5.Qt import QLabel, QSplitter, QTabWidget
from PyQt5.QtCore import QThread, Qt, pyqtSlot
from PyQt5.QtGui import QColor, QPalette, QPixmap, QTextCursor
from PyQt5.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, \
    QWidget

from apiClient import ApiClient
from constants import log_File, masternodes_File, starting_height
from hwdevice import HWdevice
from misc import WriteStream, WriteStreamReceiver, getCallerName, getFunctionName, getRemoteQMTversion, loadMNConfFile, \
    now, printDbg, printException, printOK, writeToFile
from qt.guiHeader import GuiHeader
from rpcClient import RpcClient
from tabAddTorrent import TabAddTorrent
from tabGovernance import TabGovernance
from tabMNConf import TabMNConf
from tabMain import TabMain
from tabRewards import TabRewards
from threads import ThreadFuns
from watchdogThreads import RpcWatchdog


class MainWindow(QWidget):

    def __init__(self, parent, masternode_list, imgDir):
        super(QWidget, self).__init__(parent)
        self.parent = parent
        self.imgDir = imgDir
        self.runInThread = ThreadFuns.runInThread
        ###-- Masternode list 
        self.masternode_list = masternode_list
        ###-- Create clients and statuses
        self.hwdevice = None
        self.hwStatus = 0
        self.hwStatusMess = "Not Connected"
        self.rpcClient = None
        self.rpcConnected = False
        self.rpcStatusMess = "Not Connected"
        self.isBlockchainSynced = False

        ###-- Load icons & images
        self.loadIcons()
        ###-- Create main layout
        self.layout = QVBoxLayout()
        self.header = GuiHeader(self)
        self.initConsole()
        self.layout.addWidget(self.header)
        ###-- Create RPC Whatchdog
        self.rpc_watchdogThread = QThread()
        self.myRpcWd = RpcWatchdog(self)
        self.myRpcWd.moveToThread(self.rpc_watchdogThread)
        self.rpc_watchdogThread.started.connect(self.myRpcWd.run)

        ###-- Create Queues and redirect stdout and stderr
        self.queue = Queue()
        self.queue2 = Queue()
        sys.stdout = WriteStream(self.queue)
        sys.stderr = WriteStream(self.queue2)

        ###-- Init last logs
        logFile = open(log_File, 'w+')
        timestamp = strftime('%Y-%m-%d %H:%M:%S', gmtime(now()))
        log_line = '<b style="color: blue">{}</b><br>'.format('STARTING QMT at ' + timestamp)
        logFile.write(log_line)
        logFile.close()

        ###-- Create the thread to update console log for stdout
        self.consoleLogThread = QThread()
        self.myWSReceiver = WriteStreamReceiver(self.queue)
        self.myWSReceiver.mysignal.connect(self.append_to_console)
        self.myWSReceiver.moveToThread(self.consoleLogThread)
        self.consoleLogThread.started.connect(self.myWSReceiver.run)
        self.consoleLogThread.start()
        printDbg("Console Log thread started")
        ###-- Create the thread to update console log for stderr
        self.consoleLogThread2 = QThread()
        self.myWSReceiver2 = WriteStreamReceiver(self.queue2)
        self.myWSReceiver2.mysignal.connect(self.append_to_console)
        self.myWSReceiver2.moveToThread(self.consoleLogThread2)
        self.consoleLogThread2.started.connect(self.myWSReceiver2.run)
        self.consoleLogThread2.start()
        printDbg("Console Log thread 2 started")

        ###-- Initialize tabs
        self.tabs = QTabWidget()
        self.t_main = TabMain(self)
        self.t_mnconf = TabMNConf(self)
        self.t_rewards = TabRewards(self)
        self.t_governance = TabGovernance(self)
        self.t_add_torrent = TabAddTorrent(self)

        ###-- Add tabs
        self.tabs.addTab(self.tabGovernance, "Search Torrents")
        self.tabs.addTab(self.tabAddTorrent, "Add Torrents")
#        self.tabs.addTab(self.tabMain, "Masternode Control")
#        self.tabs.addTab(self.tabMNConf, "MN Configuration")   # We will put these back later, just with RPC instead of messy key handling which we don't need or want anyway !
#        self.tabs.addTab(self.tabRewards, "Transfer Rewards")

        ###-- Connect change action
        self.tabs.currentChanged.connect(lambda: self.onTabChange())
        ###-- Draw Tabs 
        self.splitter = QSplitter(Qt.Vertical)
        ###-- Add tabs and console to Layout        
        self.splitter.addWidget(self.tabs)
        self.splitter.addWidget(self.console)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes(self.parent.cache.get("splitter_sizes"))
        self.layout.addWidget(self.splitter)

        ###-- Set Layout
        self.setLayout(self.layout)
        ###-- Let's go
        self.mnode_to_change = None
        printOK("Hello! Welcome to " + parent.title)

        ###-- Hide console if it was previously hidden
        if self.parent.cache.get("console_hidden"):
            self.onToggleConsole()

        ##-- Check version
        self.onCheckVersion()

        ##-- init Api Client
        self.apiClient = ApiClient()

    @pyqtSlot(str)
    def append_to_console(self, text):
        self.consoleArea.moveCursor(QTextCursor.End)
        self.consoleArea.insertHtml(text)

    def initConsole(self):
        self.console = QGroupBox()
        self.console.setTitle("Console Log")
        layout = QVBoxLayout()
        self.btn_consoleToggle = QPushButton('Hide')
        self.btn_consoleToggle.setToolTip('Show/Hide console')
        self.btn_consoleToggle.clicked.connect(lambda: self.onToggleConsole())
        consoleHeader = QHBoxLayout()
        consoleHeader.addWidget(self.btn_consoleToggle)
        self.consoleSaveButton = QPushButton('Save')
        self.consoleSaveButton.clicked.connect(lambda: self.onSaveConsole())
        consoleHeader.addWidget(self.consoleSaveButton)
        self.btn_consoleClean = QPushButton('Clean')
        self.btn_consoleClean.setToolTip('Clean console log area')
        self.btn_consoleClean.clicked.connect(lambda: self.onCleanConsole())
        consoleHeader.addWidget(self.btn_consoleClean)
        consoleHeader.addStretch(1)
        self.versionLabel = QLabel("--")
        self.versionLabel.setOpenExternalLinks(True)
        consoleHeader.addWidget(self.versionLabel)
        self.btn_checkVersion = QPushButton("Check QMT version")
        self.btn_checkVersion.setToolTip("Check latest stable release of QMT")
        self.btn_checkVersion.clicked.connect(lambda: self.onCheckVersion())
        consoleHeader.addWidget(self.btn_checkVersion)
        layout.addLayout(consoleHeader)
        self.consoleArea = QTextEdit()
        almostBlack = QColor(40, 40, 40)
        palette = QPalette()
        palette.setColor(QPalette.Base, almostBlack)
        green = QColor(0, 255, 0)
        palette.setColor(QPalette.Text, green)
        self.consoleArea.setPalette(palette)
        layout.addWidget(self.consoleArea)
        self.console.setLayout(layout)

    def isMasternodeInList(self, mn_alias):
        return (mn_alias in [x['name'] for x in self.masternode_list])

    def loadIcons(self):
        # Load Icons        
        self.ledPurpleH_icon = QPixmap(os.path.join(self.imgDir, 'icon_purpleLedH.png')).scaledToHeight(17,
                                                                                                        Qt.SmoothTransformation)
        self.ledGrayH_icon = QPixmap(os.path.join(self.imgDir, 'icon_grayLedH.png')).scaledToHeight(17,
                                                                                                    Qt.SmoothTransformation)
        self.ledHalfPurpleH_icon = QPixmap(os.path.join(self.imgDir, 'icon_halfPurpleLedH.png')).scaledToHeight(17,
                                                                                                                Qt.SmoothTransformation)
        self.ledRedV_icon = QPixmap(os.path.join(self.imgDir, 'icon_redLedV.png')).scaledToHeight(17,
                                                                                                  Qt.SmoothTransformation)
        self.ledGrayV_icon = QPixmap(os.path.join(self.imgDir, 'icon_grayLedV.png')).scaledToHeight(17,
                                                                                                    Qt.SmoothTransformation)
        self.ledGreenV_icon = QPixmap(os.path.join(self.imgDir, 'icon_greenLedV.png')).scaledToHeight(17,
                                                                                                      Qt.SmoothTransformation)

    def loadMNConf(self, fileName):
        hot_masternodes = loadMNConfFile(fileName)
        if hot_masternodes == None:
            messText = "Unable to load data from file '%s'" % fileName
            self.myPopUp2(QMessageBox.Warning, "QMT - warning", messText)
        else:
            # Append new masternodes to list
            new_masternodes = []
            skip_masternodes = []
            for x in hot_masternodes:
                if not self.isMasternodeInList(x['name']):
                    self.masternode_list.append(x)
                    new_masternodes.append(x)
                else:
                    skip_masternodes.append(x)

            # Show new list
            for new_masternode in new_masternodes:
                name = new_masternode['name']
                self.tabMain.insert_mn_list(name, new_masternode['ip'], new_masternode['port'], None, isHardware=False)
                self.tabMain.btn_remove[name].clicked.connect(lambda: self.t_main.onRemoveMN())

            # print number of nodes added
            new_nodes = len(new_masternodes)
            final_message = ""
            if new_nodes == 0:
                final_message = "No External Masternode "
            elif new_nodes == 1:
                final_message = "1 External Masternode "
            else:
                final_message = "%d External Masternodes " % new_nodes
            final_message += "added to the list. "
            if new_nodes > 0:
                final_message += str([x['name'] for x in new_masternodes]) + ".  "
            if len(skip_masternodes) > 0:
                final_message += "Following entries skipped due to duplicate names:"
                final_message += str([x['name'] for x in skip_masternodes]) + ".  "
            printDbg(final_message)

            if new_nodes > 0:
                # update files
                printDbg("saving MN configuration file")
                writeToFile(self.masternode_list, masternodes_File)
                printDbg("saved")
                # Clear voting masternodes configuration and update cache
                self.t_governance.clear()

    def myPopUp(self, messType, messTitle, messText, defaultButton=QMessageBox.No):
        mess = QMessageBox(messType, messTitle, messText, defaultButton, parent=self)
        mess.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        mess.setDefaultButton(defaultButton)
        return mess.exec_()

    def myPopUp2(self, messType, messTitle, messText, singleButton=QMessageBox.Ok):
        mess = QMessageBox(messType, messTitle, messText, singleButton, parent=self)
        mess.setStandardButtons(singleButton | singleButton)
        return mess.exec_()

    @pyqtSlot()
    def onCheckHw(self):
        printDbg("Checking for HW device...")
        self.updateHWstatus(None)
        self.showHWstatus()

    @pyqtSlot()
    def onCheckRpc(self):
        printDbg("Checking RPC server...")
        self.runInThread(self.updateRPCstatus, (), self.showRPCstatus)

    @pyqtSlot()
    def onCheckVersion(self):
        printDbg("Checking QMT version...")
        self.versionLabel.setText("--")
        self.runInThread(self.checkVersion, (), self.updateVersion)

    def checkVersion(self, ctrl):
        local_version = self.parent.version['number'].split('.')
        remote_version = getRemoteQMTversion().split('.')

        if (remote_version[0] > local_version[0]) or \
                (remote_version[0] == local_version[0] and remote_version[1] > local_version[1]) or \
                (remote_version[0] == local_version[0] and remote_version[1] == local_version[1] and remote_version[2] >
                 local_version[2]):
            self.versionMess = '<b style="color:red">New Version Available:</b> %s.%s.%s  ' % (
            remote_version[0], remote_version[1], remote_version[2])
            self.versionMess += '(<a href="https://github.com/project-qmc/QMT/releases/">download</a>)'
        else:
            self.versionMess = "You have the latest version of QMT"

    def updateVersion(self):
        if self.versionMess is not None:
            self.versionLabel.setText(self.versionMess)

    @pyqtSlot()
    def onCleanConsole(self):
        self.consoleArea.clear()

    @pyqtSlot()
    def onSaveConsole(self):
        timestamp = strftime('%Y-%m-%d_%H-%M-%S', gmtime(now()))
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(self, "Save Logs to file", "QMT_Logs_%s.txt" % timestamp,
                                                  "All Files (*);; Text Files (*.txt)", options=options)
        try:
            if fileName:
                printOK("Saving logs to %s" % fileName)
                log_file = open(fileName, 'w+')
                log_text = self.consoleArea.toPlainText()
                log_file.write(log_text)
                log_file.close()

        except Exception as e:
            err_msg = "error writing Log file"
            printException(getCallerName(), getFunctionName(), err_msg, e.args)

    @pyqtSlot()
    def onTabChange(self):
        # reload (and re-sort)masternode list in tabs
        if self.tabs.currentWidget() == self.tabRewards:
            # reload last used address
            self.tabRewards.destinationLine.setText(self.parent.cache.get("lastAddress"))
            # get new order
            mnOrder = {}
            mnList = self.tabMain.myList
            for i in range(mnList.count()):
                mnName = mnList.itemWidget(mnList.item(i)).alias
                mnOrder[mnName] = i
            self.parent.cache['mnList_order'] = mnOrder
            # Sort masternode list (by alias if no previous order set)
            if self.parent.cache.get('mnList_order') != {}:
                self.masternode_list.sort(key=self.parent.extract_order)
            self.t_rewards.loadMnSelect()
            self.t_rewards.selectedRewards = None

        # reload torrent and voting masternode list
        if self.tabs.currentWidget() == self.tabGovernance:
            self.t_governance.updateSelectedMNlabel()

    @pyqtSlot()
    def onToggleConsole(self):
        if self.btn_consoleToggle.text() == 'Hide':
            self.btn_consoleToggle.setText('Show')
            self.consoleArea.hide()
            self.console.setMinimumHeight(70)
            self.console.setMaximumHeight(70)
        else:
            self.console.setMinimumHeight(70)
            self.console.setMaximumHeight(starting_height)
            self.btn_consoleToggle.setText('Hide')
            self.consoleArea.show()

    def showHWstatus(self):
        self.updateHWleds()
        self.myPopUp2(QMessageBox.Information, 'QMT - hw check', "%s" % self.hwStatusMess, QMessageBox.Ok)

    def showRPCstatus(self):
        self.updateRPCled()
        self.myPopUp2(QMessageBox.Information, 'QMT - rpc check', "%s" % self.rpcStatusMess, QMessageBox.Ok)

    def updateHWleds(self):
        if self.hwStatus == 1:
            self.header.hwLed.setPixmap(self.ledHalfPurpleH_icon)
        elif self.hwStatus == 2:
            self.header.hwLed.setPixmap(self.ledPurpleH_icon)
        else:
            self.header.hwLed.setPixmap(self.ledGrayH_icon)
        self.header.hwLed.setToolTip(self.hwStatusMess)

    def updateHWstatus(self, ctrl):
        if self.hwdevice is not None:
            if hasattr(self.hwdevice, 'dongle'):
                self.hwdevice.dongle.close()

        self.hwdevice = HWdevice()

        statusCode, statusMess = self.hwdevice.getStatus()
        printDbg("mess: %s" % statusMess)
        if statusCode != 2:
            # If is not connected try again
            try:
                if hasattr(self.hwdevice, 'dongle'):
                    self.hwdevice.dongle.close()
                self.hwdevice = HWdevice()
                self.hwdevice.initDevice()
                statusCode, statusMess = self.hwdevice.getStatus()

            except Exception as e:
                err_msg = "error in checkHw"
                printException(getCallerName(), getFunctionName(), err_msg, e.args)

        self.hwStatus = statusCode
        self.hwStatusMess = statusMess

        # if all is good connect the signals
        if statusCode == 2:
            self.hwdevice.sigTxdone.connect(self.t_rewards.FinishSend)
            self.hwdevice.sigTxabort.connect(self.t_rewards.onCancel)
            self.hwdevice.tx_progress.connect(self.t_rewards.updateProgressPercent)

    def updateLastBlockLabel(self):
        text = '--'
        if self.rpcLastBlock == 1:
            text = "Loading block index..."
        elif self.rpcLastBlock > 0 and self.rpcConnected:
            text = str(self.rpcLastBlock)
            text += " ("
            if not self.isBlockchainSynced:
                text += "Synchronizing"
            else:
                text += "Synced"
            text += ")"

        self.header.lastBlockLabel.setText(text)

    def updateRPCled(self):
        if self.rpcConnected:
            self.header.rpcLed.setPixmap(self.ledPurpleH_icon)
        else:
            if self.rpcLastBlock == 1:
                self.header.rpcLed.setPixmap(self.ledHalfPurpleH_icon)
            else:
                self.header.rpcLed.setPixmap(self.ledGrayH_icon)

        self.header.rpcLed.setToolTip(self.rpcStatusMess)
        self.updateLastBlockLabel()

    def updateRPCstatus(self, ctrl):
        if self.rpcClient is None:
            self.rpcClient = RpcClient()

        status, statusMess, lastBlock = self.rpcClient.getStatus()

        self.rpcConnected = status
        self.rpcLastBlock = lastBlock
        self.rpcStatusMess = statusMess
        self.isBlockchainSynced = self.rpcClient.isBlockchainSynced()

        # If is not connected try again
        if not status:
            self.rpcClient = RpcClient()
