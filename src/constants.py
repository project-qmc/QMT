#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os.path

MPATH = "44'/77'/"
WIF_PREFIX = 0xd4
MAGIC_BYTE = 30
TESTNET_WIF_PREFIX = 239
TESTNET_MAGIC_BYTE = 139
DEFAULT_PROTOCOL_VERSION = 70913
MINIMUM_FEE = 0.0001  # minimum QMC/kB
STARTING_WIDTH = 933
STARTING_HEIGHT = 666
APPDATA_DIRNAME = ".QMCTorrentTool"
HOME_DIR = os.path.expanduser('~')
USER_DIR = os.path.join(HOME_DIR, APPDATA_DIRNAME)
LOG_FILE = os.path.join(USER_DIR, 'lastLogs.html')
MASTERNODES_FILE = 'masternodes.json'
RPC_FILE = 'rpcServer.json'
CACHE_FILE = 'cache.json'
DEFAULT_RPC_CONF = {
    "rpc_ip": "127.0.0.1",
    "rpc_port": 55777,
    "rpc_user": "myUsername",
    "rpc_password": "myPassword"
}
DEFAULT_MN_CONF = {
    "name": "",
    "ip": "",
    "port": 51472,
    "mnPrivKey": "",
    "isTestnet": 0,
    "isHardware": True,
    "hwAcc": 0,
    "collateral": {}
}
DEFAULT_CACHE = {
    "lastAddress": "",
    "window_width": STARTING_WIDTH,
    "window_height": STARTING_HEIGHT,
    "splitter_sizes": [342, 133],
    "mnList_order": {},
    "useSwiftX": False,
    "votingMasternodes": [],
    "votingDelayCheck": False,
    "votingDelayNeg": 0,
    "votingDelayPos": 300
}
