#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os.path

MPATH = "44'/77'/"
WIF_PREFIX = 212 # 212 = d4
MAGIC_BYTE = 30
TESTNET_WIF_PREFIX = 239
TESTNET_MAGIC_BYTE = 139
DEFAULT_PROTOCOL_VERSION = 70913
MINIMUM_FEE = 0.0001    # minimum QMC/kB
starting_width = 933
starting_height = 666
APPDATA_DIRNAME = ".QMCTorrentTool"
home_dir = os.path.expanduser('~')
user_dir = os.path.join(home_dir, APPDATA_DIRNAME)
log_File = os.path.join(user_dir, 'lastLogs.html')
masternodes_File = 'masternodes.json'
rpc_File = 'rpcServer.json'
cache_File = 'cache.json'
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
    "window_width": starting_width,
    "window_height": starting_height,
    "splitter_sizes": [342, 133],
    "mnList_order": {},
    "useSwiftX": False,
    "votingMasternodes": [],
    "votingDelayCheck": False,
    "votingDelayNeg": 0,
    "votingDelayPos": 300
    }
