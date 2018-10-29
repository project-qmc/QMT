#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import os.path
import sys
from ipaddress import ip_address
from urllib.parse import urlsplit

from bitcoin import b58check_to_hex, bin_dbl_sha256, dbl_sha256, decode_sig, ecdsa_raw_sign, ecdsa_raw_verify, \
    encode_sig, privkey_to_pubkey

from qmc_hashing.qmc_b58 import b58decode
from qmc_hashing.qmc_hashlib import wif_to_privkey

sys.path.append(os.path.join(os.path.dirname(__file__), '.'))
import time
from PyQt5.QtCore import QObject, pyqtSignal
from constants import USER_DIR, LOG_FILE, MASTERNODES_FILE, RPC_FILE, CACHE_FILE, \
    DEFAULT_CACHE, DEFAULT_MN_CONF, DEFAULT_RPC_CONF, HOME_DIR


def append_to_logfile(text):
    try:
        logFile = open(LOG_FILE, 'a+')
        logFile.write(text)
        logFile.close()
    except Exception as e:
        print(e)


def clean_for_html(text):
    if text is None:
        return ""
    return text.replace("<", "{").replace(">", "}")


def clear_screen():
    os.system('clear')


def getCallerName():
    try:
        return sys._getframe(2).f_code.co_name
    except Exception:
        return None


def getFunctionName():
    try:
        return sys._getframe(1).f_code.co_name
    except Exception:
        return None


def getRemoteQMTversion():
    import requests
    resp = requests.get("https://raw.githubusercontent.com/project-qmc/QMT/master/src/version.txt")
    if resp.status_code == 200:
        data = resp.json()
        return data['number']
    else:
        print("Invalid response getting version from GitHub\n")
        return "0.0.0"


def getQMTVersion():
    import simplejson as json
    version_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'version.txt')
    with open(version_file) as data_file:
        data = json.load(data_file)

    return data


def getTxidTxidn(txid, txidn):
    if txid is None or txidn is None:
        return None
    else:
        return txid + '-' + str(txidn)


def highlight_textbox(element, label=None):
    element.setStyleSheet('color: rgb(255, 0, 0);')
    if label:
        label.setStyleSheet('color: rgb(255, 0, 0);')
        element.textChanged.connect(lambda _: label.setStyleSheet(''))
    element.textChanged.connect(lambda _: element.setStyleSheet(''))
    element.textChanged.connect(lambda _: element.textChanged.disconnect())


def ipport(ip, port):
    if ip is None or port is None:
        return None
    elif ip.endswith('.onion'):
        return ip + ':' + port
    else:
        ipAddr = ip_address(ip)
        if ipAddr.version == 4:
            return ip + ':' + port
        elif ipAddr.version == 6:
            return "[" + ip + "]:" + port
        else:
            raise Exception("invalid IP version number")


def is_hex(s):
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


def loadMNConfFile(fileName):
    hot_masternodes = []
    try:
        with open(fileName) as f:
            for line in f:
                confline = line.strip()

                # skip blank lines
                if len(confline) == 0:
                    continue

                # skip comments
                if confline[0] == '#':
                    continue

                configs = confline.split(' ')
                # check number of keys
                if len(configs) != 5:
                    printDbg("wrong number of parameters in masternode.conf")
                    return None

                new_mn = {'name': configs[0]}

                ipaddr = configs[1].split(':')
                if len(ipaddr) != 2:
                    printDbg("wrong ip:address in masternode.conf")
                    return None

                new_mn['ip'] = ipaddr[0]
                new_mn['port'] = int(ipaddr[1])
                new_mn['mnPrivKey'] = configs[2]
                new_mn['isHardware'] = False
                collateral = {'txid': configs[3], 'txidn': int(configs[4])}
                new_mn['collateral'] = collateral

                hot_masternodes.append(new_mn)

        return hot_masternodes

    except Exception as e:
        errorMsg = "error loading MN file"
        printException(getCallerName(), getFunctionName(), errorMsg, e.args)


def now():
    return int(time.time())


def printDbg_msg(what):
    what = clean_for_html(what)
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now()))
    log_line = '<b style="color: yellow">{}</b> : {}<br>'.format(timestamp, what)
    return log_line


def printDbg(what):
    log_line = printDbg_msg(what)
    append_to_logfile(log_line)
    print(log_line)


def printException_msg(
        caller_name,
        function_name,
        err_msg,
        errargs=None):
    VERSION = getQMTVersion()
    msg = '<b style="color: red">EXCEPTION</b><br>'
    msg += '<span style="color:white">version</span> : %s-%s<br>' % (VERSION['number'], VERSION['tag'])
    msg += '<span style="color:white">caller</span>   : %s<br>' % caller_name
    msg += '<span style="color:white">function</span> : %s<br>' % function_name
    msg += '<span style="color:red">'
    if errargs:
        msg += 'err: %s<br>' % str(errargs[0])

    msg += '===> %s</span><br>' % err_msg
    return msg


def printException(caller_name,
                   function_name,
                   err_msg,
                   errargs=None):
    text = printException_msg(caller_name, function_name, err_msg, errargs)
    append_to_logfile(text)
    print(text)


def printOK(what):
    msg = '<b style="color: #cc33ff">===> ' + what + '</b><br>'
    append_to_logfile(msg)
    print(msg)


def splitString(text, n):
    arr = [text[i:i + n] for i in range(0, len(text), n)]
    return '\n'.join(arr)


def readCacheFile():
    try:
        import simplejson as json
        cache_file = os.path.join(USER_DIR, CACHE_FILE)
        if os.path.exists(cache_file):
            with open(cache_file) as data_file:
                cache = json.load(data_file)

        else:
            writeToFile(DEFAULT_CACHE, CACHE_FILE)
            raise Exception("No cache file found. Creating new.")

    except Exception as e:
        printDbg(e.args[0])
        return DEFAULT_CACHE

    # Fix missing data in cache
    newKeys = False
    for key in DEFAULT_CACHE:
        if key not in cache:
            cache[key] = DEFAULT_CACHE[key]
            newKeys = True
    if newKeys:
        writeToFile(cache, CACHE_FILE)

    return cache


def readMNfile():
    try:
        import simplejson as json
        mn_file = os.path.join(USER_DIR, MASTERNODES_FILE)
        if os.path.exists(mn_file):
            with open(mn_file) as data_file:
                mnList = json.load(data_file)

        else:
            # save default config (empty list) and return it
            writeToFile([], MASTERNODES_FILE)
            raise Exception("No masternodes file found. Creating new.")

    except Exception as e:
        printDbg(e.args[0])
        return []

    # Fix missing data
    newKeys = False
    for key in DEFAULT_MN_CONF:
        for node in mnList:
            if key not in node:
                node[key] = DEFAULT_MN_CONF[key]
                newKeys = True
    if newKeys:
        writeToFile(mnList, MASTERNODES_FILE)

    return mnList


def readRPCfile():
    def inject_conf(path):
        with open(os.path.join(appdata_dir, shard), 'r') as conf:
            lines = conf.readlines()
            settings = dict(map(lambda s: s.split('='), lines))
            DEFAULT_RPC_CONF['rpc_user'] = settings['rpcuser'].strip()
            DEFAULT_RPC_CONF['rpc_password'] = settings['rpcpassword'].strip()

    try:
        appdata_dir = os.environ['APPDATA']
        shard = 'QMC2/qmc2.conf'

        inject_conf(os.path.join(appdata_dir, shard))
    except:
        try:
            path = os.path.join(HOME_DIR, '.qmc2/qmc2.conf')
            inject_conf(path)
        except:
            pass

    try:
        import simplejson as json
        config_file = os.path.join(USER_DIR, RPC_FILE)
        if os.path.exists(config_file):
            with open(config_file) as data_file:
                rpc_config = json.load(data_file)

            # Check for malformed data
            urlstring = "http://%s:%s@%s:%d" % (
                rpc_config.get('rpc_user'), rpc_config.get('rpc_password'),
                rpc_config.get('rpc_ip'), int(rpc_config.get('rpc_port')))
            if not checkRPCstring(urlstring):
                # save default config and return it
                resetRPCfile()
                rpc_config = DEFAULT_RPC_CONF

        else:
            printDbg("No rpcServer.json found.")
            # save default config and return it
            resetRPCfile()
            rpc_config = DEFAULT_RPC_CONF

    except Exception as e:
        printDbg(e.args[0])

    rpc_ip = rpc_config.get('rpc_ip')
    rpc_port = int(rpc_config.get('rpc_port'))
    rpc_user = rpc_config.get('rpc_user')
    rpc_password = rpc_config.get('rpc_password')

    return rpc_ip, rpc_port, rpc_user, rpc_password


def resetRPCfile():
    printDbg("Creating default rpcServer.json")
    writeToFile(DEFAULT_RPC_CONF, RPC_FILE)


def checkRPCstring(urlstring, action_msg="Resetting default credentials"):
    if urlsplit(urlstring).netloc != urlstring[7:]:
        error_msg = "Unable to parse URL: %s [urllib parsed: %s]" % (urlstring[7:], urlsplit(urlstring).netloc)
        printException(getCallerName(), getFunctionName(), action_msg, [error_msg])
        return False
    else:
        return True


def sec_to_time(seconds):
    days = seconds // 86400
    seconds -= days * 86400
    hrs = seconds // 3600
    seconds -= hrs * 3600
    mins = seconds // 60
    seconds -= mins * 60
    return "{} days, {} hrs, {} mins, {} secs".format(days, hrs, mins, seconds)


def updateSplash(label, i):
    if i == 10:
        progressText = "Loading configuration data..."
        label.setText(progressText)
    elif i == 30:
        progressText = "Creating the user interface..."
        label.setText(progressText)
    elif i == 59:
        progressText = "Releasing the watchdogs..."
        label.setText(progressText)
    elif i == 89:
        progressText = "Enjoy the freedom !"
        label.setText(progressText)
    elif i == 99:
        time.sleep(0.8)


def writeToFile(data, filename):
    try:
        import simplejson as json
        datafile_name = os.path.join(USER_DIR, filename)
        with open(datafile_name, 'w+') as data_file:
            json.dump(data, data_file)

    except Exception as e:
        errorMsg = "error writing file %s" % filename
        printException(getCallerName(), getFunctionName(), errorMsg, e.args)


# Stream object to redirect sys.stdout and sys.stderr to a queue
class WriteStream(object):
    def __init__(self, queue):
        self.queue = queue

    def write(self, text):
        self.queue.put(text)

    def flush(self):
        pass


# QObject (to be run in QThread) that blocks until data is available
# and then emits a QtSignal to the main thread.
class WriteStreamReceiver(QObject):
    mysignal = pyqtSignal(str)

    def __init__(self, queue, *args, **kwargs):
        QObject.__init__(self, *args, **kwargs)
        self.queue = queue

    def run(self):
        while True:
            text = self.queue.get()
            self.mysignal.emit(text)


OP_DUP = b'\x76'
OP_HASH160 = b'\xA9'
OP_QEUALVERIFY = b'\x88'
OP_CHECKSIG = b'\xAC'
OP_EQUAL = b'\x87'
OP_RETURN = b'\x6a'
P2PKH_PREFIXES = ['D']
P2SH_PREFIXES = ['7']


def b64encode(text):
    return base64.b64encode(bytearray.fromhex(text)).decode('utf-8')


def checkQmcAddr(address):
    try:
        # check leading char 'D'
        if address[0] != 'D':
            return False

        # decode and verify checksum
        addr_bin = bytes.fromhex(b58decode(address).hex())
        addr_bin_check = bin_dbl_sha256(addr_bin[0:-4])[0:4]
        if addr_bin[-4:] != addr_bin_check:
            return False

        return True
    except Exception:
        return False


def compose_tx_locking_script(dest_address):
    """
    Create a Locking script (ScriptPubKey) that will be assigned to a transaction output.
    :param dest_address: destination address in Base58Check format
    :return: sequence of opcodes and its arguments, defining logic of the locking script
    """
    pubkey_hash = bytearray.fromhex(b58check_to_hex(dest_address))  # convert address to a public key hash
    if len(pubkey_hash) != 20:
        raise Exception('Invalid length of the public key hash: ' + str(len(pubkey_hash)))

    if dest_address[0] in P2PKH_PREFIXES:
        # sequence of opcodes/arguments for p2pkh (pay-to-public-key-hash)
        scr = OP_DUP + \
              OP_HASH160 + \
              int.to_bytes(len(pubkey_hash), 1, byteorder='little') + \
              pubkey_hash + \
              OP_QEUALVERIFY + \
              OP_CHECKSIG
    elif dest_address[0] in P2SH_PREFIXES:
        # sequence of opcodes/arguments for p2sh (pay-to-script-hash)
        scr = OP_HASH160 + \
              int.to_bytes(len(pubkey_hash), 1, byteorder='little') + \
              pubkey_hash + \
              OP_EQUAL
    else:
        raise Exception('Invalid dest address prefix: ' + dest_address[0])
    return scr


def compose_tx_locking_script_OR(message):
    """
    Create a Locking script (ScriptPubKey) that will be assigned to a transaction output.
    :param message: data for the OP_RETURN
    :return: sequence of opcodes and its arguments, defining logic of the locking script
    """

    scr = OP_RETURN + int.to_bytes(len(data), 1, byteorder='little') + message.encode()

    return scr


def ecdsa_sign(msg, priv):
    """
    Based on project: https://github.com/chaeplin/dashmnb.
    """
    v, r, s = ecdsa_raw_sign(electrum_sig_hash(msg), priv)
    sig = encode_sig(v, r, s)
    pubkey = privkey_to_pubkey(wif_to_privkey(priv))

    ok = ecdsa_raw_verify(electrum_sig_hash(msg), decode_sig(sig), pubkey)
    if not ok:
        raise Exception('Bad signature!')
    return sig


def electrum_sig_hash(message):
    """
    Based on project: https://github.com/chaeplin/dashmnb.
    """
    padded = b'\x18DarkNet Signed Message:\n' + num_to_varint(len(message)) + from_string_to_bytes(message)
    return dbl_sha256(padded)


def extract_pkh_from_locking_script(script):
    if len(script) == 25:
        if script[0:1] == OP_DUP and script[1:2] == OP_HASH160:
            if read_varint(script, 2)[0] == 20:
                return script[3:23]
            else:
                raise Exception('Non-standard public key hash length (should be 20)')
    raise Exception('Non-standard locking script type (should be P2PKH)')


def from_string_to_bytes(a):
    return a if isinstance(a, bytes) else bytes(a, 'utf-8')


def ipmap(ip, port):
    try:
        ipv6map = ''

        if len(ip) > 6 and ip.endswith('.onion'):
            pchOnionCat = bytearray([0xFD, 0x87, 0xD8, 0x7E, 0xEB, 0x43])
            vchAddr = base64.b32decode(ip[0:-6], True)
            if len(vchAddr) != 16 - len(pchOnionCat):
                raise Exception('Invalid onion %s' % s)
            return pchOnionCat.hex() + vchAddr.hex() + int(port).to_bytes(2, byteorder='big').hex()

        ipAddr = ip_address(ip)

        if ipAddr.version == 4:
            ipv6map = '00000000000000000000ffff'
            ip_digits = map(int, ipAddr.exploded.split('.'))
            for i in ip_digits:
                ipv6map += i.to_bytes(1, byteorder='big')[::-1].hex()

        elif ipAddr.version == 6:
            ip_hextets = map(str, ipAddr.exploded.split(':'))
            for a in ip_hextets:
                ipv6map += a

        else:
            raise Exception("invalid version number (%d)" % version)

        ipv6map += int(port).to_bytes(2, byteorder='big').hex()
        if len(ipv6map) != 36:
            raise Exception("Problems! len is %d" % len(ipv6map))
        return ipv6map

    except Exception as e:
        err_msg = "error in ipmap"
        printException(getCallerName(), getFunctionName(), err_msg, e.args)


def num_to_varint(a):
    """
    Based on project: https://github.com/chaeplin/dashmnb
    """
    x = int(a)
    if x < 253:
        return x.to_bytes(1, byteorder='big')
    elif x < 65536:
        return int(253).to_bytes(1, byteorder='big') + x.to_bytes(2, byteorder='little')
    elif x < 4294967296:
        return int(254).to_bytes(1, byteorder='big') + x.to_bytes(4, byteorder='little')
    else:
        return int(255).to_bytes(1, byteorder='big') + x.to_bytes(8, byteorder='little')


def read_varint(buffer, offset):
    if buffer[offset] < 0xfd:
        value_size = 1
        value = buffer[offset]
    elif buffer[offset] == 0xfd:
        value_size = 3
        value = int.from_bytes(buffer[offset + 1: offset + 3], byteorder='little')
    elif buffer[offset] == 0xfe:
        value_size = 5
        value = int.from_bytes(buffer[offset + 1: offset + 5], byteorder='little')
    elif buffer[offset] == 0xff:
        value_size = 9
        value = int.from_bytes(buffer[offset + 1: offset + 9], byteorder='little')
    else:
        raise Exception("Invalid varint size")
    return value, value_size


def serialize_input_str(tx, prevout_n, sequence, script_sig):
    """
    Based on project: https://github.com/chaeplin/dashmnb.
    """
    s = ['CTxIn(', 'COutPoint(%s, %s)' % (tx, prevout_n), ', ']
    if tx == '00' * 32 and prevout_n == 0xffffffff:
        s.append('coinbase %s' % script_sig)

    else:
        script_sig2 = script_sig
        if len(script_sig2) > 24:
            script_sig2 = script_sig2[0:24]
        s.append('scriptSig=%s' % script_sig2)

    if sequence != 0xffffffff:
        s.append(', nSequence=%d' % sequence)

    s.append(')')
    return ''.join(s)
