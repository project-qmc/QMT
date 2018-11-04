#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from misc import printDbg, printException, getCallerName, getFunctionName, writeToFile
from threads import ThreadFuns
from utils import checkQmcAddr
from apiClient import ApiClient
from constants import MPATH, MINIMUM_FEE, cache_File
from hwdevice import DisconnectedException

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.Qt import QTableWidgetItem, QHeaderView, QItemSelectionModel, QApplication
from PyQt5.QtWidgets import QMessageBox

from qt.gui_tabRewards import TabRewards_gui
import simplejson as json


class TabRewards():
    def __init__(self, caller):
        self.caller = caller
        ##--- Initialize Selection
        self.rewards = None
        self.selectedRewards = None
        self.rawtransactions = {}
        self.feePerKb = MINIMUM_FEE
        ##--- Initialize GUI
        self.ui = TabRewards_gui()
        self.caller.tabRewards = self.ui
        self.suggestedFee = MINIMUM_FEE
        # load last used destination from cache
        self.ui.destinationLine.setText(self.caller.parent.cache.get("lastAddress")) 
        # load useSwiftX check from cache
        if self.caller.parent.cache.get("useSwiftX"):
            self.ui.swiftxCheck.setChecked(True)
        self.updateFee()
        # Connect GUI buttons
        self.ui.mnSelect.currentIndexChanged.connect(lambda: self.onChangeSelectedMN())
        self.ui.btn_toggleCollateral.clicked.connect(lambda: self.onToggleCollateral())
        self.ui.rewardsList.box.itemClicked.connect(lambda: self.updateSelection())
        self.ui.btn_selectAllRewards.clicked.connect(lambda: self.onSelectAllRewards())
        self.ui.btn_deselectAllRewards.clicked.connect(lambda: self.onDeselectAllRewards())
        self.ui.swiftxCheck.clicked.connect(lambda: self.updateFee())
        self.ui.btn_sendRewards.clicked.connect(lambda: self.onSendRewards())
        self.ui.btn_Cancel.clicked.connect(lambda: self.onCancel())

        
        
        
    def display_utxos(self):
        if self.rewards is not None:
            def item(value):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                return item
    
            self.ui.rewardsList.box.setRowCount(len(self.rewards))
            for row, utxo in enumerate(self.rewards):
                txId = utxo.get('tx_hash', None)
    
                qmcAmount = round(int(utxo.get('value', 0))/1e8, 8)
                self.ui.rewardsList.box.setItem(row, 0, item(str(qmcAmount)))
                self.ui.rewardsList.box.setItem(row, 1, item(str(utxo.get('confirmations', None))))
                self.ui.rewardsList.box.setItem(row, 2, item(txId))
                self.ui.rewardsList.box.setItem(row, 3, item(str(utxo.get('tx_ouput_n', None))))
                self.ui.rewardsList.box.showRow(row)
                # MARK COLLATERAL UTXO
                if txId == self.curr_txid:
                    for i in range(0,4):
                        self.ui.rewardsList.box.item(row, i).setFont(QFont("Arial", 9, QFont.Bold))
                    self.ui.rewardsList.box.collateralRow = row
                
                # make immature rewards unselectable
                if utxo.get('confirmations') < 101:
                    for i in range(0,4):
                        self.ui.rewardsList.box.item(row, i).setFlags(Qt.NoItemFlags)
                        self.ui.rewardsList.box.item(row, i).setToolTip("Immature - 100 confirmations required")
                    
            if self.ui.rewardsList.box.collateralRow is not None:
                    self.ui.rewardsList.box.hideRow(self.ui.rewardsList.box.collateralRow)    
                   
            if len(self.rewards) > 1:  # (collateral is a reward)
                self.ui.rewardsList.box.resizeColumnsToContents()
                self.ui.rewardsList.statusLabel.setVisible(False)
                self.ui.rewardsList.box.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
                                
            else:
                if not self.caller.rpcConnected:
                    self.ui.rewardsList.statusLabel.setText('<b style="color:purple">QMC wallet not connected</b>')
                else:
                    if self.apiConnected:
                        self.ui.rewardsList.statusLabel.setText('<b style="color:red">Found no Rewards for %s</b>' % self.curr_addr)
                    else:
                        self.ui.rewardsList.statusLabel.setText('<b style="color:purple">Unable to connect to API provider</b>')
                self.ui.rewardsList.statusLabel.setVisible(True)
              
        
            
            
            
    def getSelection(self):
        items = self.ui.rewardsList.box.selectedItems()
        # Save row indexes to a set to avoid repetition
        rows = set()
        for i in range(0, len(items)):
            row = items[i].row()
            rows.add(row)
        rowList = list(rows)  
        return [self.rewards[row] for row in rowList]
            

       
            
            
    def loadMnSelect(self):
        self.ui.mnSelect.clear()            
        for x in self.caller.masternode_list:
            if x['isHardware']:
                name = x['name']
                address = x['collateral'].get('address')
                txid = x['collateral'].get('txid')
                hwAcc = x['hwAcc']
                spath = x['collateral'].get('spath')
                path = MPATH + "%d'/0/%d" % (hwAcc, spath)
                self.ui.mnSelect.addItem(name, [address, txid, path])
                     
           
    
    
    def load_utxos_thread(self, ctrl):
        self.apiConnected = False
        try:
            if not self.caller.rpcConnected:
                self.rewards = []
                printDbg('QMC daemon not connected')
            
            else:
                try:
                    if self.caller.apiClient.getStatus() != 200:
                        return
                    
                    self.apiConnected = True
                    self.blockCount = self.caller.rpcClient.getBlockCount()
                    self.rewards = self.caller.apiClient.getAddressUtxos(self.curr_addr)['unspent_outputs']
                    
                    for utxo in self.rewards:
                        rawtx = self.caller.rpcClient.getRawTransaction(utxo['tx_hash'])
                        self.rawtransactions[utxo['tx_hash']] = rawtx
                        if rawtx is None:
                            print("Unable to get raw TX from RPC server\n")
                            
                    self.feePerKb = self.caller.rpcClient.getFeePerKb()
                            
                except Exception as e:
                    self.errorMsg = 'Error occurred while calling getaddressutxos method: ' + str(e)
                    printDbg(self.errorMsg)
                    
        except Exception as e:
            print(e)
            pass
        
    
    
    
    #@pyqtSlot()
    def onCancel(self):
        self.selectedRewards = None
        self.ui.selectedRewardsLine.setText("0.0")
        self.ui.mnSelect.setCurrentIndex(0)
        self.suggestedFee = MINIMUM_FEE
        self.updateFee()
        self.ui.btn_toggleCollateral.setText("Show Collateral")
        self.ui.collateralHidden = True
        self.onChangeSelectedMN()
        self.AbortSend()
    
    
    
        
    @pyqtSlot()
    def onChangeSelectedMN(self):
        if self.ui.mnSelect.currentIndex() >= 0:
            self.curr_addr = self.ui.mnSelect.itemData(self.ui.mnSelect.currentIndex())[0]
            self.curr_txid = self.ui.mnSelect.itemData(self.ui.mnSelect.currentIndex())[1]
            self.curr_path = self.ui.mnSelect.itemData(self.ui.mnSelect.currentIndex())[2] 
            if self.curr_addr is not None:
                result = self.caller.apiClient.getBalance(self.curr_addr)
                self.ui.addrAvailLine.setText("<i>%s QMCs</i>" % result)
            self.ui.selectedRewardsLine.setText("0.0")
            self.ui.rewardsList.box.clearSelection()
            self.ui.rewardsList.box.collateralRow = None
            self.ui.collateralHidden = True
            self.ui.btn_toggleCollateral.setText("Show Collateral")
            if result is not None:
                self.runInThread = ThreadFuns.runInThread(self.load_utxos_thread, (), self.display_utxos)
            
      
        
        
    @pyqtSlot()
    def onSelectAllRewards(self):
        self.ui.rewardsList.box.selectAll()
        self.updateSelection() 


            
    @pyqtSlot()
    def onDeselectAllRewards(self):
        self.ui.rewardsList.box.clearSelection()
        self.updateSelection()
    
            
            
            
    @pyqtSlot()
    def onSendRewards(self):
        self.dest_addr = self.ui.destinationLine.text().strip() 
    
        # Check dongle
        printDbg("Checking HW device")
        if self.caller.hwStatus != 2:
            self.caller.myPopUp2(QMessageBox.Critical, 'QMT - hw device check', "Connect to HW device first")
            printDbg("Unable to connect to hardware device. The device status is: %d" % self.caller.hwStatus)
            return None
        
        # Check destination Address      
        if not checkQmcAddr(self.dest_addr):
            self.caller.myPopUp2(QMessageBox.Critical, 'QMT - QMC address check', "The destination address is missing, or invalid.")
            return None
        
        # Check spending collateral
        if (not self.ui.collateralHidden and
                self.ui.rewardsList.box.collateralRow is not None and
                self.ui.rewardsList.box.item(self.ui.rewardsList.box.collateralRow, 0).isSelected() ): 
            warning1 = "Are you sure you want to transfer the collateral?"
            warning2 = "Really?"
            warning3 = "Take a deep breath. Do you REALLY want to transfer your collateral?"
            ans = self.caller.myPopUp(QMessageBox.Warning, 'QMT - warning', warning1)
            if ans == QMessageBox.No:
                return None
            else:
                ans2 = self.caller.myPopUp(QMessageBox.Warning, 'QMT - warning', warning2)
                if ans2 == QMessageBox.No:
                    return None
                else:
                    ans3 = self.caller.myPopUp(QMessageBox.Critical, 'QMT - warning', warning3)
                    if ans3 == QMessageBox.No:
                        return None
                    
        # LET'S GO    
        if self.selectedRewards: 
            printDbg("Sending from QMC address  %s  to QMC address  %s " % (self.curr_addr, self.dest_addr))
            printDbg("Preparing transaction. Please wait...")
            self.ui.loadingLine.show()
            self.ui.loadingLinePercent.show()
            QApplication.processEvents()            
            
            # save last destination address and swiftxCheck to cache
            self.caller.parent.cache["lastAddress"] = self.dest_addr
            self.caller.parent.cache["useSwiftX"] = self.useSwiftX()
            writeToFile(self.caller.parent.cache, cache_File)            
            
            self.currFee = self.ui.feeLine.value() * 1e8            

            try:
                self.txFinished = False
                self.caller.hwdevice.prepare_transfer_tx(self.caller, self.curr_path, self.selectedRewards, self.dest_addr, self.currFee, self.rawtransactions, self.useSwiftX())
            
            except DisconnectedException as e:
                self.caller.hwStatus = 0
                self.caller.updateHWleds()
                
            except Exception as e:
                err_msg = "Error while preparing transaction. <br>"
                err_msg += "Probably Blockchain wasn't synced when trying to fetch raw TXs.<br>" 
                err_msg += "<b>Wait for full synchronization</b> then hit 'Clear/Reload'"
                printException(getCallerName(), getFunctionName(), err_msg, e.args)
        else:
            self.caller.myPopUp2(QMessageBox.Information, 'Transaction NOT sent', "No UTXO to send")         
                    
            
            
    @pyqtSlot()
    def onToggleCollateral(self):
        if(self.rewards is not None):
            
            if len(self.rewards) and self.ui.rewardsList.box.collateralRow is not None:
                if not self.ui.collateralHidden:
                    try:
                        if self.ui.rewardsList.box.item(self.ui.rewardsList.box.collateralRow, 0).isSelected():
                            self.ui.rewardsList.box.selectRow(self.ui.rewardsList.box.collateralRow)
                    except Exception as e:
                        err_msg = "Error toggling collateral"
                        printException(getCallerName(), getFunctionName(), err_msg, e.args)
                    
                    self.ui.rewardsList.box.hideRow(self.ui.rewardsList.box.collateralRow)
                    self.ui.btn_toggleCollateral.setText("Show Collateral")
                    self.ui.collateralHidden = True
                    self.updateSelection()
                else:
                    self.ui.rewardsList.box.showRow(self.ui.rewardsList.box.collateralRow)
                    self.ui.btn_toggleCollateral.setText("Hide Collateral")
                    self.ui.collateralHidden = False
                    self.updateSelection()
                    self.ui.rewardsList.box.resizeColumnsToContents()
                    self.ui.rewardsList.box.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            
        else:
            self.caller.myPopUp2(QMessageBox.Information, 'No Collateral', "No collateral selected")
            
            
            

    # Activated by signal sigTxdone from hwdevice       
    #@pyqtSlot(bytearray, str)            
    def FinishSend(self, serialized_tx, amount_to_send):
        self.AbortSend()
        if not self.txFinished:
            try:
                self.txFinished = True
                tx_hex = serialized_tx.hex()
                printDbg("Raw signed transaction: " + tx_hex)
                printDbg("Amount to send :" + amount_to_send)
                
                if len(tx_hex) > 90000:
                    mess = "Transaction's length exceeds 90000 bytes. Select less UTXOs and try again."
                    self.caller.myPopUp2(QMessageBox.Warning, 'transaction Warning', mess)
                
                else:
                    decodedTx = self.caller.rpcClient.decodeRawTransaction(tx_hex)
                    destination = decodedTx.get("vout")[0].get("scriptPubKey").get("addresses")[0]
                    amount = decodedTx.get("vout")[0].get("value")
                    message = '<p>Broadcast signed transaction?</p><p>Destination address:<br><b>%s</b></p>' % destination
                    message += '<p>Amount: <b>%s</b> QMC<br>' % str(amount)
                    message += 'Fees: <b>%s</b> QMC <br>Size: <b>%d</b> Bytes</p>' % (str(round(self.currFee / 1e8, 8) ), len(tx_hex)/2)
                    
                    mess1 = QMessageBox(QMessageBox.Information, 'Send transaction', message)
                    mess1.setDetailedText(json.dumps(decodedTx, indent=4, sort_keys=False))
                    mess1.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    reply = mess1.exec_()
                    if reply == QMessageBox.Yes:                
                        txid = self.caller.rpcClient.sendRawTransaction(tx_hex, self.useSwiftX())
                        mess2_text = "<p>Transaction successfully sent.</p><p>(Note that the selected rewards will remain displayed in the app until the transaction is confirmed.)</p>"
                        mess2 = QMessageBox(QMessageBox.Information, 'transaction Sent', mess2_text)
                        mess2.setDetailedText(txid)
                        mess2.exec_()
                        self.onCancel()
                        
                    else:
                        self.caller.myPopUp2(QMessageBox.Information, 'Transaction NOT sent', "Transaction NOT sent")
                        self.onCancel()
                        
            except Exception as e:
                err_msg = "Exception in FinishSend"
                printException(getCallerName(), getFunctionName(), err_msg, e.args)
                
    
    # Activated by signal sigTxabort from hwdevice
    def AbortSend(self):
        self.ui.loadingLine.hide()
        self.ui.loadingLinePercent.setValue(0)
        self.ui.loadingLinePercent.hide()
        
        
        
    @pyqtSlot()
    def updateFee(self):
        if self.useSwiftX():
            self.ui.feeLine.setValue(0.01)
            self.ui.feeLine.setEnabled(False)
        else:
            self.ui.feeLine.setValue(self.suggestedFee)
            self.ui.feeLine.setEnabled(True)
        
        
             
    # Activated by signal tx_progress from hwdevice
    #@pyqtSlot(str)
    def updateProgressPercent(self, percent):
        self.ui.loadingLinePercent.setValue(int(percent))
        QApplication.processEvents()
        
 
 
    def updateSelection(self, clicked_item=None):
        total = 0
        self.selectedRewards = self.getSelection()
        numOfInputs = len(self.selectedRewards)
        if numOfInputs:
            for i in range(0, numOfInputs):
                total += int(self.selectedRewards[i].get('value'))
                                    
            # update suggested fee and selected rewards
            estimatedTxSize = (44+numOfInputs*148)*1.0 / 1000   # kB
            self.suggestedFee = round(self.feePerKb * estimatedTxSize, 8)
            printDbg("estimatedTxSize is %s kB" % str(estimatedTxSize))
            printDbg("suggested fee is %s QMC (%s QMC/kB)" % (str(self.suggestedFee), str(self.feePerKb)))
            
            self.ui.selectedRewardsLine.setText(str(round(total/1e8, 8)))
            
        else:
            self.ui.selectedRewardsLine.setText("")
        
        self.updateFee()
            
            
            
    def useSwiftX(self):
        return self.ui.swiftxCheck.isChecked()
        