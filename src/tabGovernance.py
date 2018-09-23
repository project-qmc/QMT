#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

import os.path
from PyQt5.Qt import QDesktopServices, QFont, QUrl

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import QTableWidgetItem, QPushButton, QWidget, QHBoxLayout, \
    QMessageBox

from itertools import product
from qt.gui_tabGovernance import TabGovernance_gui, ScrollMessageBox
from qt.dlg_selectMNs import SelectMNs_dlg
from qt.dlg_budgetProjection import BudgetProjection_dlg
from misc import printException, getCallerName, getFunctionName, printDbg, printOK, writeToFile, highlight_textbox
from threads import ThreadFuns
import json
import time
import random
import re
import requests
from utils import ecdsa_sign
from constants import cache_File


class Torrent():
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


class TabGovernance():
    def __init__(self, caller):
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
        self.ui.refreshTorrents_btn.clicked.connect(lambda: self.onRefreshTorrents())
        self.ui.toggleExpiring_btn.clicked.connect(lambda: self.onToggleExpiring())
        self.ui.selectMN_btn.clicked.connect(lambda: SelectMNs_dlg(self).exec_())
        self.ui.budgetProjection_btn.clicked.connect(lambda: BudgetProjection_dlg(self).exec_())
        self.ui.torrentBox.itemClicked.connect(lambda: self.updateSelection())
        self.ui.voteYes_btn.clicked.connect(lambda: self.onVote(1))
#        self.ui.voteAbstain_btn.clicked.connect(lambda: self.onVote(0))
        self.ui.voteNo_btn.clicked.connect(lambda: self.onVote(2))
        self.ui.search_textbox.returnPressed.connect(lambda: self.onRefreshTorrents())

    def clear(self):
        # Clear voting masternodes configuration and update cache
        self.votingMasternodes = []
        self.caller.parent.cache['votingMasternodes'] = []
        writeToFile(self.caller.parent.cache, cache_File)

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

        def itemButton(value, icon_num):
            pwidget = QWidget()
            btn = QPushButton()
            if icon_num == 0:
                btn.setIcon(self.ui.link_icon)
                btn.setToolTip("Download Torrent")
                btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(str(value))))
            else:
                btn.setIcon(self.ui.search_icon)
                btn.setToolTip("Play with instant.io")
                btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(str(value))))

            pLayout = QHBoxLayout()
            pLayout.addWidget(btn)
            pLayout.setContentsMargins(0, 0, 0, 0)
            pwidget.setLayout(pLayout)
            return pwidget

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

        self.ui.torrentBox.setRowCount(len(filtered_torrents))
        for row, prop in enumerate(filtered_torrents):
            self.ui.torrentBox.setItem(row, 0, item(prop.name))
            self.ui.torrentBox.item(row, 0).setFont(QFont("Arial", 9, QFont.Bold))

            hash = item(prop.Hash)
            hash.setToolTip(prop.Hash)
            self.ui.torrentBox.setItem(row, 6, hash)

            self.ui.torrentBox.setCellWidget(row, 2, itemButton(prop.URL, 0))

            monthlyPay = item(prop.MonthlyPayment)
            monthlyPay.setData(Qt.EditRole, int(round(prop.MonthlyPayment)))
            self.ui.torrentBox.setItem(row, 3, monthlyPay)

            payments = "%d / %d" % (prop.RemainingPayCount, prop.TotalPayCount)
            self.ui.torrentBox.setItem(row, 4, item(payments))

            net_votes = "%d / %d / %d" % (prop.Yeas, prop.Abstains, prop.Nays)
            votes = item(net_votes)
            if (prop.Yeas - prop.Nays) > 0.1 * self.mnCount:
                votes.setBackground(Qt.green)
            if (prop.Yeas - prop.Nays) < 0:
                votes.setBackground(Qt.red)
            if prop.RemainingPayCount == 0:
                votes.setBackground(Qt.yellow)
            self.ui.torrentBox.setItem(row, 5, votes)

            #my_votes = "%d / %d / %d" % (len(prop.MyYeas), len(prop.MyAbstains), len(prop.MyNays))
            #self.ui.torrentBox.setItem(row, 6, item(my_votes))
            self.ui.torrentBox.setCellWidget(row, 1, itemButton("https://instant.io/#" + prop.URL, 1))

        # Sort by Votes descending
        self.ui.torrentBox.setSortingEnabled(True)
        self.ui.torrentBox.sortByColumn(5, Qt.DescendingOrder)

    def getSelection(self):
        items = self.ui.torrentBox.selectedItems()
        # Save row indexes to a set to avoid repetition
        rows = set()
        for i in range(0, len(items)):
            row = items[i].row()
            rows.add(row)
        rowsList = list(rows)
        hashesList = [self.ui.torrentBox.item(row, 6).text() for row in rowsList]
        # print("Selected: " + str([p.name for p in self.torrents if p.name in namesList]))
        return [p for p in self.torrents if p.Hash in hashesList]

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

    def summaryDlg(self, vote_code):
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
        writeToFile(self.caller.parent.cache, cache_File)

        server_url = "http://{}:{}".format(self.caller.rpcClient.rpc_ip, self.caller.rpcClient.rpc_port)
        auth_pair = self.caller.rpcClient.rpc_user, self.caller.rpcClient.rpc_passwd

        for prop, mn in product(self.selectedTorrents, self.votingMasternodes):
            try:
                v_res = requests.post(url=server_url,
                                      auth=auth_pair,
                                      data=self.prepare_vote_data(prop.Hash,
                                                                  mn[1],
                                                                  ["ABSTAIN", "yes", "no"][vote_code]))
                printDbg(v_res) # Vote status is not processed yet
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


    @pyqtSlot(object, str)
    def _vote_thread_old(self, ctrl, vote_code):
        # Left for reference
        # vote_code index for ["yes", "abstain", "no"]
        if not isinstance(vote_code, int) or vote_code not in range(3):
            raise Exception("Wrong vote_code %s" % str(vote_code))
        self.successVotes = 0
        self.failedVotes = 0

        # save delay check data to cache
        self.caller.parent.cache["votingDelayCheck"] = self.ui.randomDelayCheck.isChecked()
        self.caller.parent.cache["votingDelayNeg"] = self.ui.randomDelayNeg_edt.value()
        self.caller.parent.cache["votingDelayPos"] = self.ui.randomDelayPos_edt.value()
        writeToFile(self.caller.parent.cache, cache_File)

        for prop in self.selectedTorrents:
            for mn in self.votingMasternodes:
                vote_sig = ''
                serialize_for_sig = ''
                sig_time = int(time.time())

                try:
                    # Get mnPrivKey
                    currNode = next(x for x in self.caller.masternode_list if x['name'] == mn[1])
                    if currNode is None:
                        raise Exception("currNode not found for current voting masternode %s" % mn[1])
                    mnPrivKey = currNode['mnPrivKey']
                    printDbg("we have a key\n")
                    # Add random delay offset
                    if self.ui.randomDelayCheck.isChecked():
                        minuns_max = int(self.ui.randomDelayNeg_edt.value())
                        plus_max = int(self.ui.randomDelayPos_edt.value())
                        delay_secs = random.randint(-minuns_max, plus_max)
                        sig_time += delay_secs

                    # Print Debug line to console
                    mess = "Processing '%s' vote on behalf of masternode [%s]" % (self.vote_codes[vote_code], mn[1])
                    mess += " for the torrent {%s}" % prop.name
                    if self.ui.randomDelayCheck.isChecked():
                        mess += " with offset of %d seconds" % delay_secs
                    printDbg(mess)
                    # Serialize vote
                    serialize_for_sig = mn[0][:64] + '-' + str(currNode['collateral'].get('txidn'))
                    printDbg(serialize_for_sig)
                    serialize_for_sig += prop.Hash + str(vote_code) + str(sig_time)
                    printDbg("searlized\n")
                    printDbg(serialize_for_sig)
                    printDbg(mnPrivKey)
                    # Sign vote
                    vote_sig = ecdsa_sign(serialize_for_sig, mnPrivKey)
                    printDbg("signed\n")
                    # Broadcast the vote
                    v_res = self.caller.rpcClient.mnBudgetRawVote(
                        mn_tx_hash=currNode['collateral'].get('txid'),
                        mn_tx_index=int(currNode['collateral'].get('txidn')),
                        torrent_hash=prop.Hash,
                        vote=self.vote_codes[vote_code],
                        time=sig_time,
                        vote_sig=vote_sig)
                    printDbg("boradcast?\n")
                    printOK(v_res)

                    if v_res == 'Voted successfully':
                        self.successVotes += 1
                    else:
                        self.failedVotes += 1

                except Exception as e:
                    err_msg = "Exception in vote_thread - check MN privKey"
                    printException(getCallerName(), getFunctionName(), err_msg, e.args)
                    printDbg(err_msg)
                    printDbg(e.args)

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
