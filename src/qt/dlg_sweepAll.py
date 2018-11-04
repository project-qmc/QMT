#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os.path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,\
    QAbstractScrollArea, QHeaderView, QLineEdit, QFormLayout, QDoubleSpinBox, QMessageBox,\
    QApplication, QProgressBar, QCheckBox
from PyQt5.Qt import QLabel
from PyQt5.QtCore import pyqtSlot
from threads import ThreadFuns
from constants import MPATH, cache_File, MINIMUM_FEE
from hwdevice import DisconnectedException
from utils import checkQmcAddr
from misc import printDbg, writeToFile, getCallerName, getFunctionName, printException
import simplejson as json

class SweepAll_dlg(QDialog):
    def __init__(self, main_tab):
        QDialog.__init__(self, parent=main_tab.ui)
        self.main_tab = main_tab
        self.setWindowTitle('Sweep All Rewards')
        ##--- Initialize GUI
        self.setupUI()
        self.suggestedFee = MINIMUM_FEE
        # load last used destination from cache
        self.ui.edt_destination.setText(self.main_tab.caller.parent.cache.get("lastAddress"))
        # load useSwiftX check from cache
        if self.main_tab.caller.parent.cache.get("useSwiftX"):
            self.ui.swiftxCheck.setChecked(True)
        self.updateFee()
        # Connect GUI buttons
        self.connectButtons()
        
        
    def load_data(self):
        ThreadFuns.runInThread(self.load_utxos_thread, (), self.display_utxos)
        
    
    
    def connectButtons(self):
        self.ui.buttonSend.clicked.connect(lambda: self.onButtonSend())
        self.ui.buttonCancel.clicked.connect(lambda: self.onButtonCancel())
        self.ui.swiftxCheck.clicked.connect(lambda: self.updateFee())
    
    
        
    def setupUI(self):
        self.ui = Ui_SweepAllDlg()
        self.ui.setupUi(self)
        
    
    
    def display_utxos(self):
        def item(value):
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.NoItemFlags)
            return item
        
        if len(self.rewards) == 0:
            self.ui.lblMessage.setText("Unable to get raw TX from RPC server\nPlease wait for full synchronization and try again.")
            
        else:
            self.ui.tableW.setRowCount(len(self.rewards))
            numOfInputs = 0
            for row, mnode in enumerate(self.rewards):
                self.ui.tableW.setItem(row, 0, item(mnode['name']))
                self.ui.tableW.setItem(row, 1, item(mnode['addr']))
                newInputs = len(mnode['utxos'])
                numOfInputs += newInputs
                rewards_line = "%s QMC (%d payments)" % (mnode['total_rewards'], newInputs)
                self.ui.tableW.setItem(row, 2, item(rewards_line))
            
            self.ui.tableW.resizeColumnsToContents()
            self.ui.lblMessage.setVisible(False)
            self.ui.tableW.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            
            total = sum([float(mnode['total_rewards']) for mnode in self.rewards])
            self.ui.totalLine.setText("<b>%s</b>" % str(round(total,8)))
            
            # update fee
            estimatedTxSize = (44+numOfInputs*148)*1.0 / 1000   # kB
            self.suggestedFee = round(self.feePerKb * estimatedTxSize, 8)
            self.updateFee()
            
            
    
       
        
    def load_utxos_thread(self, ctrl):
        self.rewards = []
        collaterals = []
        self.rawtransactions = {}
        mnlist = [x for x in self.main_tab.caller.masternode_list if x['isHardware']]
        for mn in mnlist:
            mnode = {}
            addy = mn['collateral'].get('address')
            mnode['name'] = mn['name']
            mnode['addr'] = addy
            mnode['path'] = MPATH + "%d'/0/%d" % (mn['hwAcc'], mn['collateral'].get('spath'))
            # get UTXOs of current masternode
            mnode['utxos'] = self.main_tab.caller.apiClient.getAddressUtxos(addy)['unspent_outputs']
            # remove collateral and immature rewards
            mnode['utxos'] = [x for x in mnode['utxos'] if (x['tx_hash'] != mn['collateral'].get('txid') and
                                                            x['confirmations'] > 100) ]
            
            # compute total rewards
            total = sum([int(x['value']) for x in mnode['utxos']])
            mnode['total_rewards'] = str(round(total/1e8, 8))                
            self.rewards.append(mnode)   
            
        # get raw transactions
            for utxo in mnode['utxos']:
                rawtx = self.main_tab.caller.rpcClient.getRawTransaction(utxo['tx_hash'])
                self.rawtransactions[utxo['tx_hash']] = rawtx
                if rawtx is None:
                    print("Unable to get raw TX from RPC server\n")
                    self.rewards = []
                    return
        # update fee
        self.feePerKb = self.main_tab.caller.rpcClient.getFeePerKb()        
    
    
    
    @pyqtSlot()
    def onButtonCancel(self):
        self.AbortSend()
        self.close()
        
        
        

    @pyqtSlot()
    def onButtonSend(self):
        try:
            self.dest_addr = self.ui.edt_destination.text().strip()
            self.currFee = self.ui.feeLine.value() * 1e8
             
             # Check RPC & dongle  
            if not self.main_tab.caller.rpcConnected or self.main_tab.caller.hwStatus != 2:
                self.main_tab.caller.myPopUp2(QMessageBox.Critical, 'QMT - hw/rpc device check', "Connect to RPC server and HW device first")
                return None
            
            # Check destination Address      
            if not checkQmcAddr(self.dest_addr):
                self.main_tab.caller.myPopUp2(QMessageBox.Critical, 'QMT - QMC address check', "The destination address is missing, or invalid.")
                return None

            # LET'S GO
            if len(self.rawtransactions) > 0:
                printDbg("Preparing transaction. Please wait...")
                self.ui.loadingLine.show()
                self.ui.loadingLinePercent.show()
                QApplication.processEvents()
                
                # save last destination address and swiftxCheck to cache
                self.main_tab.caller.parent.cache["lastAddress"] = self.dest_addr
                self.main_tab.caller.parent.cache["useSwiftX"] = self.useSwiftX()
                writeToFile(self.main_tab.caller.parent.cache, cache_File)
                    
                # re-connect signals
                try:
                    self.main_tab.caller.hwdevice.sigTxdone.disconnect()
                except:
                    pass
                try:
                    self.main_tab.caller.hwdevice.sigTxabort.disconnect()
                except:
                    pass
                try:
                    self.main_tab.caller.hwdevice.tx_progress.disconnect()
                except:
                    pass
                self.main_tab.caller.hwdevice.sigTxdone.connect(self.FinishSend)
                self.main_tab.caller.hwdevice.sigTxabort.connect(self.AbortSend)
                self.main_tab.caller.hwdevice.tx_progress.connect(self.updateProgressPercent)
    
                self.txFinished = False
                self.main_tab.caller.hwdevice.prepare_transfer_tx_bulk(self.main_tab.caller, self.rewards, self.dest_addr, self.currFee, self.rawtransactions, self.useSwiftX())
            else:
                self.main_tab.caller.myPopUp2(QMessageBox.Information, 'Transaction NOT sent', "No UTXO to send") 
                
        except DisconnectedException as e:
            self.main_tab.caller.hwStatus = 0
            self.main_tab.caller.updateHWleds()
            self.onButtonCancel()
                
        except Exception as e:
            err_msg = "Exception in onButtonSend"
            printException(getCallerName(), getFunctionName(), err_msg, e.args)
           
            
    
    # Activated by signal sigTxabort from hwdevice
    def AbortSend(self):
        self.ui.loadingLine.hide()
        self.ui.loadingLinePercent.setValue(0)
        self.ui.loadingLinePercent.hide()
    
    
    
    # Activated by signal sigTxdone from hwdevice       
    #@pyqtSlot(bytearray, str)  
    def FinishSend(self, serialized_tx, amount_to_send):
        self.AbortSend()
        QApplication.processEvents()
        if not self.txFinished:
            try:
                self.txFinished = True
                self.close()
                tx_hex = serialized_tx.hex()
                printDbg("Raw signed transaction: " + tx_hex)
                printDbg("Amount to send :" + amount_to_send)
                
                if len(tx_hex) > 90000:
                    mess = "Transaction's length exceeds 90000 bytes. Select less UTXOs and try again."
                    self.main_tab.caller.myPopUp2(QMessageBox.Warning, 'transaction Warning', mess)
                
                else:
                    decodedTx = self.main_tab.caller.rpcClient.decodeRawTransaction(tx_hex)
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
                        txid = self.main_tab.caller.rpcClient.sendRawTransaction(tx_hex, self.useSwiftX())
                        mess2_text = "<p>Transaction successfully sent.</p><p>(Note that the selected rewards will remain displayed in the app until the transaction is confirmed.)</p>"
                        mess2 = QMessageBox(QMessageBox.Information, 'transaction Sent', mess2_text)
                        mess2.setDetailedText(txid)
                        mess2.exec_()
                        
                    else:
                        self.main_tab.caller.myPopUp2(QMessageBox.Information, 'Transaction NOT sent', "Transaction NOT sent")
                    
            except Exception as e:
                err_msg = "Exception in FinishSend"
                printException(getCallerName(), getFunctionName(), err_msg, e.args)

    
    
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
        self.ui.loadingLinePercent.setValue(percent)
        QApplication.processEvents()
        
    
    def useSwiftX(self):
        return self.ui.swiftxCheck.isChecked()        
        
   

class Ui_SweepAllDlg(object):
    def setupUi(self, SweepAllDlg):
        SweepAllDlg.setModal(True)
        layout = QVBoxLayout(SweepAllDlg)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel("<b><i>Sweep Rewards From All Masternodes</i></b>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        self.lblMessage = QLabel(SweepAllDlg)
        self.lblMessage.setText("Loading rewards...")
        self.lblMessage.setWordWrap(True)
        layout.addWidget(self.lblMessage)
        self.tableW = QTableWidget(SweepAllDlg)
        self.tableW.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.tableW.setShowGrid(True)
        self.tableW.setColumnCount(3)
        self.tableW.setRowCount(0)
        self.tableW.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tableW.verticalHeader().hide()
        item = QTableWidgetItem()
        item.setText("Name")
        item.setTextAlignment(Qt.AlignCenter)
        self.tableW.setHorizontalHeaderItem(0, item)
        item = QTableWidgetItem()
        item.setText("Address")
        item.setTextAlignment(Qt.AlignCenter)
        self.tableW.setHorizontalHeaderItem(1, item)
        item = QTableWidgetItem()
        item.setText("Rewards")
        item.setTextAlignment(Qt.AlignCenter)
        self.tableW.setHorizontalHeaderItem(2, item)
        layout.addWidget(self.tableW)
        myForm = QFormLayout()
        myForm.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        hBox = QHBoxLayout()
        self.totalLine = QLabel("<b>0 QMC</b>")
        hBox.addWidget(self.totalLine)
        self.loadingLine = QLabel("<b style='color:red'>Preparing TX.</b> Completed: ")
        self.loadingLinePercent = QProgressBar()
        self.loadingLinePercent.setMaximumWidth(200)
        self.loadingLinePercent.setMaximumHeight(10)
        self.loadingLinePercent.setRange(0, 100)
        hBox.addWidget(self.loadingLine)
        hBox.addWidget(self.loadingLinePercent)
        self.loadingLine.hide()
        self.loadingLinePercent.hide()
        myForm.addRow(QLabel("Total Rewards: "), hBox)
        hBox = QHBoxLayout()
        self.edt_destination = QLineEdit()
        self.edt_destination.setToolTip("QMC address to transfer rewards to")
        hBox.addWidget(self.edt_destination)
        hBox.addWidget(QLabel("Fee"))
        self.feeLine = QDoubleSpinBox()
        self.feeLine.setDecimals(8)
        self.feeLine.setPrefix("QMC  ")
        self.feeLine.setToolTip("Insert a small fee amount")
        self.feeLine.setFixedWidth(120)
        self.feeLine.setSingleStep(0.001)
        hBox.addWidget(self.feeLine)
        self.swiftxCheck = QCheckBox()
        self.swiftxCheck.setToolTip("check for SwiftX instant transaction (flat fee rate of 0.01 QMC)")
        hBox.addWidget(QLabel("Use SwiftX"))
        hBox.addWidget(self.swiftxCheck)
        myForm.addRow(QLabel("Destination Address"), hBox)       
        myForm.addRow(hBox)
        layout.addLayout(myForm)
        hBox = QHBoxLayout()
        self.buttonCancel = QPushButton("Cancel")
        hBox.addWidget(self.buttonCancel)
        self.buttonSend = QPushButton("Send")
        hBox.addWidget(self.buttonSend)
        layout.addLayout(hBox)
        SweepAllDlg.resize(650, 257)
