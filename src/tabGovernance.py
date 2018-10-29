#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import io
import os.path
import sys

from PyQt5 import QtCore, QtWidgets
from PyQt5.Qt import QDesktopServices, QFont, QUrl

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox, QPushButton

from itertools import product
from qt.gui_tabGovernance import TabGovernance_gui, ScrollMessageBox
from qt.dlg_selectMNs import SelectMNs_dlg
from qt.dlg_budgetProjection import BudgetProjection_dlg
from misc import printException, getCallerName, getFunctionName, printDbg, writeToFile, highlight_textbox
from qmt_threading.threads import ThreadFuns
import json
import time
import random
import re
import requests
from torrent_tracker_scraper import scraper as torrent_scraper
from constants import CACHE_FILE


class Torrent:
    def __init__(self, name, URL, Hash, FeeHash, BlockStart, BlockEnd, TotalPayCount, RemainingPayCount,
                 PayMentAddress, Yeas, Nays, Abstains, TotalPayment, MonthlyPayment):
        self.name = name
        self.URL = URL if URL.startswith('magnet') or URL.startswith('magnet') else '' + URL
        self.Hash = Hash
        self.FeeHash = FeeHash
        self.BlockStart = int(BlockStart)
        self.BlockEnd = int(BlockEnd)
        self.TotalPayCount = int(TotalPayCount)
        self.RemainingPayCount = int(RemainingPayCount)
        self.PaymentAddress = PayMentAddress
        self.Yeas = int(Yeas)
        self.Nays = int(Nays)
        self.Abstains = int(Abstains)
        self.ToalPayment = TotalPayment
        self.MonthlyPayment = MonthlyPayment
        ## list of personal masternodes voting
        self.MyYeas = []
        self.MyAbstains = []
        self.MyNays = []


class TabGovernance(QtCore.QObject):
    def __init__(self, caller):
        super().__init__()
        self.caller = caller
        self.torrents = []  # list of Torrent Objects
        self.selectedTorrents = []
        self.votingMasternodes = self.caller.parent.cache.get("votingMasternodes")
        self.successVotes = 0
        self.failedVotes = 0
        ##--- Initialize GUI
        self.ui = TabGovernance_gui(caller)
        self.updateSelectedMNlabel()
        self.caller.tabGovernance = self.ui
        # Connect GUI buttons
        self.vote_codes = ["abstains", "yes", "no"]

        self.ui.refreshTorrents_btn.pressed.connect(lambda: self.onRefreshTorrents())
        self.ui.toggleExpiring_btn.pressed.connect(lambda: self.onToggleExpiring())
        self.ui.selectMN_btn.pressed.connect(lambda: SelectMNs_dlg(self).exec_())
        self.ui.budgetProjection_btn.pressed.connect(lambda: BudgetProjection_dlg(self).exec_())
        self.ui.torrentBox.itemSelectionChanged.connect(lambda: self.updateSelection())
        self.ui.voteYes_btn.pressed.connect(lambda: self.onVote(1))
        self.ui.voteNo_btn.pressed.connect(lambda: self.onVote(2))
        self.ui.search_textbox.returnPressed.connect(lambda: self.onRefreshTorrents())

    def clear(self):
        # Clear voting masternodes configuration and update cache
        self.votingMasternodes = []
        self.caller.parent.cache['votingMasternodes'] = []
        writeToFile(self.caller.parent.cache, CACHE_FILE)

    def countMyVotes(self):
        for prop in self.torrents:
            mnList = self.caller.masternode_list
            budgetVotes = self.caller.rpcClient.getBudgetVotes(prop.name)
            budgetYeas = [[x['mnId'], x['nTime']] for x in budgetVotes if x['Vote'] == "YES"]
            budgetAbstains = [[x['mnId'], x['nTime']] for x in budgetVotes if x['Vote'] == "ABSTAIN"]
            budgetNays = [[x['mnId'], x['nTime']] for x in budgetVotes if x['Vote'] == "NO"]
            prop.MyYeas = [[mn['name'], vote] for mn in mnList for vote in budgetYeas if
                           mn['collateral'].get('txid') == vote[0]]
            prop.MyAbstains = [[mn['name'], vote] for mn in mnList for vote in budgetAbstains if
                               mn['collateral'].get('txid') == vote[0]]
            prop.MyNays = [[mn['name'], vote] for mn in mnList for vote in budgetNays if
                           mn['collateral'].get('txid') == vote[0]]

    def countMyVotes_thread(self, ctrl):
        self.countMyVotes()

    @pyqtSlot()
    def download_selected(self):
        selected_row = next(iter(self.getSelection().keys()))
        url = self.ui.torrentBox.item(selected_row, 6).text()

        QDesktopServices.openUrl(QUrl(str(url)))

    @pyqtSlot()
    def play_selected(self):
        selected_row = next(iter(self.getSelection().keys()))
        url = "https://instant.io/#" + str(self.ui.torrentBox.item(selected_row, 6).text())

        QDesktopServices.openUrl(QUrl(str(url)))

    def display_error(self, message):
        QtWidgets.QMessageBox.critical(
            self.caller,
            'Error',
            message,
            QtWidgets.QMessageBox.Ok,
            QtWidgets.QMessageBox.Ok
        )

    def displayTorrents(self):
        self.ui.refreshingLabel.hide()
        self.ui.search_textbox.setReadOnly(False)

        if len(self.torrents) == 0:
            return

        def item(value):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            return item

        self.ui.mnCountLabel.setText("Total MN Count: <em>%d</em>" % self.mnCount)
        search_criteria = self.ui.search_textbox.text()
        search_regex = self.ui.is_regex_checkbox.isChecked()

        if search_regex:
            try:
                re.search(search_criteria, '')
            except re.error as E:
                # Invalid regex
                search_criteria = ''
                self.ui.search_textbox.setToolTip(str(E))
                self.ui.search_textbox.connect(lambda _: self.ui.search_textbox.setToolTip('Search for downloads'))
                highlight_textbox(self.ui.search_textbox, self.ui.search_label)

        filtered_torrents = []
        for prop in self.torrents:
            not_expired = True
            matches_criteria = True
            if self.ui.toggleExpiring_btn.text() == "Hide Expiring":
                not_expired = not prop.RemainingPayCount == 0
            if search_criteria:
                search_criteria = re.sub(r"\s+", '.*', search_criteria)
                fulfills_regex = re.search(search_criteria.upper(), prop.name.upper()) if not search_regex else False
                fulfills_simple = re.fullmatch(search_criteria.upper(), prop.name.upper()) if search_regex else False
                if not (fulfills_simple or fulfills_regex):
                    matches_criteria = False

            if not_expired and matches_criteria:
                filtered_torrents.append(prop)

        if search_criteria or search_regex:
            filtered_torrents = filtered_torrents[:50]

        self.ui.torrentBox.setRowCount(len(filtered_torrents))
        for row, prop in enumerate(filtered_torrents):
            self.ui.torrentBox.setItem(row, self.ui.torrentBox.column_name, item(prop.name))
            self.ui.torrentBox.item(row, self.ui.torrentBox.column_name).setFont(QFont("Arial", 9, QFont.Bold))
            # self.ui.torrentBox.setCellWidget(row, 1, itemButton("https://instant.io/#" + prop.URL, 1))
            # self.ui.torrentBox.setCellWidget(row, 2, itemButton(prop.URL, 0))

            monthlyPay = item(prop.MonthlyPayment)
            monthlyPay.setData(Qt.EditRole, int(round(prop.MonthlyPayment)))
            self.ui.torrentBox.setItem(row, self.ui.torrentBox.column_qmc_per_month, monthlyPay)

            payments = "%d / %d" % (prop.RemainingPayCount, prop.TotalPayCount)
            self.ui.torrentBox.setItem(row, self.ui.torrentBox.column_payments, item(payments))

            net_votes = "%d / %d" % (prop.Yeas, prop.Nays)
            votes = item(net_votes)
            if (prop.Yeas - prop.Nays) > 0.1 * self.mnCount:
                votes.setBackground(Qt.green)
            elif (prop.Yeas - prop.Nays) < 0:
                votes.setBackground(Qt.red)
            elif prop.RemainingPayCount == 0:
                votes.setBackground(Qt.yellow)
            self.ui.torrentBox.setItem(row, self.ui.torrentBox.column_votes, votes)

            self.ui.torrentBox.setItem(row, self.ui.torrentBox.column_hash, item(prop.Hash))
            self.ui.torrentBox.setItem(row, self.ui.torrentBox.column_url, item(prop.URL))

        # Sort by Votes descending
        self.ui.torrentBox.setSortingEnabled(True)
        self.ui.torrentBox.sortByColumn(self.ui.torrentBox.column_votes, Qt.DescendingOrder)

    def getSelection(self):
        items = self.ui.torrentBox.selectedItems()

        rows = set()
        for i in range(len(items)):
            row = items[i].row()
            rows.add(row)

        url_map = {row: self.ui.torrentBox.item(row, self.ui.torrentBox.column_url).text() for row in rows}

        return url_map

    @pyqtSlot()
    def onRefreshTorrents(self):
        self.ui.refreshingLabel.show()
        self.ui.torrentBox.setRowCount(0)
        self.torrents = []
        self.selectedTorrents = []
        self.ui.torrentBox.setSortingEnabled(False)
        ThreadFuns.runInThread(self.loadTorrents_thread, (), on_thread_finish=self.displayTorrents)

    @pyqtSlot()
    def onToggleExpiring(self):
        if self.ui.toggleExpiring_btn.text() == "Hide Expiring":
            # Hide expiring torrents
            for row in range(0, self.ui.torrentBox.rowCount()):
                if self.ui.torrentBox.item(row, 5).background() == Qt.yellow:
                    self.ui.torrentBox.hideRow(row)
            # Update button
            self.ui.toggleExpiring_btn.setToolTip("Show expiring torrents (yellow background) in list")
            self.ui.toggleExpiring_btn.setText("Show Expiring")

        else:
            # Show expiring torrents
            for row in range(0, self.ui.torrentBox.rowCount()):
                if self.ui.torrentBox.item(row, 5).background() == Qt.yellow:
                    self.ui.torrentBox.showRow(row)
                    # Update button
            self.ui.toggleExpiring_btn.setToolTip("Hide expiring torrents (yellow background) from list")
            self.ui.toggleExpiring_btn.setText("Hide Expiring")

    @pyqtSlot(str)
    def onVote(self, vote_code):
        if len(self.selectedTorrents) == 0:
            printDbg("NO PROPOSAL SELECTED. Select torrents from the list.")
            return
        if len(self.votingMasternodes) == 0:
            printDbg("NO MASTERNODE SELECTED FOR VOTING. Click on 'Select Masternodes...'")
            return

        reply = self.summaryDlg(vote_code)

        if reply == 1:
            ThreadFuns.runInThread(self.vote_thread, ([vote_code]), self.vote_thread_end)

    def summaryDlg(self, voteR_code):
        message = "Voting <b>%s</b> on the following torrent(s):<br><br>" % str(self.vote_codes[vote_code]).upper()
        for prop in self.selectedTorrents:
            message += "&nbsp; - <b>%s</b><br>&nbsp; &nbsp; (<em>%s</em>)<br><br>" % (prop.name, prop.Hash)
        message += "<br>with following masternode(s):<br><br>"

        for mn in self.votingMasternodes:
            message += "&nbsp; - <b>%s</b><br>" % mn[1]

        dlg = ScrollMessageBox(self.caller, message)

        return dlg.exec_()
        # self.caller.myPopUp(QMessageBox.Question, 'Confirm VOTE', message, QMessageBox.Yes)

    @pyqtSlot(object)
    def loadTorrents_thread(self, ctrl):
        if not self.caller.rpcConnected:
            printException(getCallerName(), getFunctionName(), "RPC server not connected", "")
            return
        self.ui.search_textbox.setReadOnly(True)
        self.torrents = self.caller.rpcClient.getTorrents()
        num_of_masternodes = self.caller.rpcClient.getMasternodeCount()

        if num_of_masternodes is None:
            printDbg("Total number of masternodes not available. Background coloring not accurate")
            self.mnCount = 1
        else:
            self.mnCount = num_of_masternodes.get("total")

        # self.countMyVotes()
        # This shit takes forever: the worst implementation of such a thing I've ever seen.

    def updateSelectedMNlabel(self):
        selected_MN = len(self.votingMasternodes)
        if selected_MN == 1:
            label = "<em><b>1</b> masternode selected for voting</em>"
        else:
            label = "<em><b>%d</b> masternodes selected for voting</em>" % selected_MN
        self.ui.selectedMNlabel.setText(label)

    def updateSelection(self):
        self.selectedTorrents = self.getSelection()
        if len(self.selectedTorrents) == 1:
            self.ui.selectedPropLabel.setText("<em><b>1</b> torrent selected")
        else:
            self.ui.selectedPropLabel.setText("<em><b>%d</b> torrents selected" % len(self.selectedTorrents))

        if not len(self.selectedTorrents):
            return

        def create_url_button(url, kind):
            result = QPushButton()
            url_opener = lambda: QDesktopServices.openUrl(QUrl(str(url)))
            if kind == 'Download':
                result.setIcon(self.ui.link_icon)
                result.setToolTip('Download Torrent')
            elif kind == 'Play':
                result.setIcon(self.ui.search_icon)
                result.setToolTip('Play with instant.io')
            result.clicked.connect(url_opener)

            return result

        def create_sl_button(row, hash):
            result = QPushButton()
            result.setIcon(self.ui.question_icon)
            result.setToolTip('Get seeders and leechers')

            def sl_button_clicked(ctrl):
                saved_log = torrent_scraper.logger.log
                null_func = lambda _, __, ___: None

                torrent_scraper.logger.log = null_func

                saved_stdout = sys.stdout
                sys.stdout = io.StringIO()

                uri_extractor = r'urn\:btih\:([^&]+)'
                magnet_uri = re.findall(uri_extractor, hash)
                if not magnet_uri:
                    return
                magnet_uri = magnet_uri[0]
                try:
                    _, s, l, __ = torrent_scraper.scrape(magnet_uri,
                                                         'tracker.openbittorrent.com',
                                                         80)
                except ValueError:
                    torrent_scraper.logger.log = saved_log
                    return

                self.ui.torrentBox.removeCellWidget(row, self.ui.torrentBox.column_sl)
                self.ui.torrentBox.setItem(row, self.ui.torrentBox.column_sl,
                                           QTableWidgetItem(f'{s} / {l}'))
                torrent_scraper.logger.log = saved_log
                sys.stdout = saved_stdout

            result.clicked.connect(lambda: ThreadFuns.runInThread(sl_button_clicked, ()))

            return result

        for row, hash in self.selectedTorrents.items():
            if not self.ui.torrentBox.cellWidget(row, self.ui.torrentBox.column_play):
                self.ui.torrentBox.setCellWidget(
                    row,
                    self.ui.torrentBox.column_play, create_url_button(
                        "https://instant.io/#" + self.ui.torrentBox.item(row, self.ui.torrentBox.column_url).text(),
                        'Play'
                    ))

            if not self.ui.torrentBox.cellWidget(row, self.ui.torrentBox.column_dl):
                self.ui.torrentBox.setCellWidget(
                    row,
                    self.ui.torrentBox.column_dl, create_url_button(
                        self.ui.torrentBox.item(row, self.ui.torrentBox.column_url).text(),
                        'Download'
                    ))

            if (
                    not self.ui.torrentBox.cellWidget(row, self.ui.torrentBox.column_sl) and
                    not self.ui.torrentBox.item(row, self.ui.torrentBox.column_sl)
            ):
                self.ui.torrentBox.setCellWidget(row, self.ui.torrentBox.column_sl, create_sl_button(row, hash))

    @staticmethod
    def prepare_vote_data(hash, masternode_name, vote):
        json_object = {
            'jsonrpc': 1.0,
            'id': 'qmt',
            'method': 'mnbudgetvote',
            'params': [
                'alias',
                hash,
                vote,
                masternode_name
            ]
        }
        return json.dumps(json_object)

    @pyqtSlot(object, str)
    def vote_thread(self, ctrl, vote_code):
        if not isinstance(vote_code, int) or vote_code not in range(3):
            raise Exception("Wrong vote_code %s" % str(vote_code))

        # Uncomment when needed
        # self.successVotes = 0
        # self.failedVotes = 0

        # save delay check data to cache
        self.caller.parent.cache["votingDelayCheck"] = self.ui.randomDelayCheck.isChecked()
        self.caller.parent.cache["votingDelayNeg"] = self.ui.randomDelayNeg_edt.value()
        self.caller.parent.cache["votingDelayPos"] = self.ui.randomDelayPos_edt.value()
        writeToFile(self.caller.parent.cache, CACHE_FILE)

        server_url = "http://{}:{}".format(self.caller.rpcClient.rpc_ip, self.caller.rpcClient.rpc_port)
        auth_pair = self.caller.rpcClient.rpc_user, self.caller.rpcClient.rpc_passwd

        for prop, mn in product(self.selectedTorrents, self.votingMasternodes):
            try:
                v_res = requests.post(url=server_url,
                                      auth=auth_pair,
                                      data=self.prepare_vote_data(prop.Hash,
                                                                  mn[1],
                                                                  ["ABSTAIN", "yes", "no"][vote_code]))

                response = json.loads(v_res.content)
                if 'error' in response:
                    self.display_error(response['error']['message'])
                    continue
            except Exception as e:
                printException(getCallerName(),
                               getFunctionName(),
                               'Submitting a vote failed',
                               e.args + (prop.Hash, mn[1], ["ABSTAIN", "yes", "no"][vote_code]))
                continue

            if self.ui.randomDelayCheck.isChecked():
                time.sleep(random.randint(
                    -int(self.ui.randomDelayNeg_edt.value()),
                    int(self.ui.randomDelayPos_edt.value())
                ))

    def vote_thread_end(self):
        message = '<p>Votes sent</p>'
        if self.successVotes > 0:
            message += '<p>Successful Votes: <b>%d</b></p>' % self.successVotes
        if self.failedVotes > 0:
            message += '<p>Failed Votes: <b>%d</b>' % self.failedVotes
        self.caller.myPopUp2(QMessageBox.Information, 'Vote Finished', message)
        # refresh torrents
        self.ui.torrentBox.setRowCount(0)
        self.ui.torrentBox.setSortingEnabled(False)
        self.ui.refreshingLabel.show()
        self.ui.selectedPropLabel.setText("<em><b>0</b> torrents selected")
        ThreadFuns.runInThread(self.countMyVotes_thread, (), self.displayTorrents)
