#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from utils import checkQmcAddr, compose_tx_locking_script
from qmc_hashlib import generate_privkey, pubkey_to_address
from bitcoin import privkey_to_pubkey
from bitcoin.main import b58check_to_hex

class TestUtilsMethods(unittest.TestCase):
    
    def test_checkQmcAddr(self):
        # Generate Valid QMC address
        pK = privkey_to_pubkey(generate_privkey())
        qmcAddr = pubkey_to_address(pK)
        # Check valid address
        self.assertTrue(checkQmcAddr(qmcAddr))
        # Check malformed address 1: change leading char
        qmcAddr2 = self.getRandomChar() + qmcAddr[1:]
        while qmcAddr2[0] == 'D':
            qmcAddr2 = self.getRandomChar() + qmcAddr[1:]
        self.assertFalse(checkQmcAddr(qmcAddr2))
        # Check malformed address 1: add random chars
        qmcAddr3 = qmcAddr
        for _ in range(10):
            qmcAddr3 += self.getRandomChar()
        self.assertFalse(checkQmcAddr(qmcAddr3))
        
        
        
    def test_compose_tx_locking_script(self):
        # check with P2PKH addresses
        # Generate Valid QMC address
        pK = privkey_to_pubkey(generate_privkey())
        qmcAddr = pubkey_to_address(pK)
        # compose TX script
        result = compose_tx_locking_script(qmcAddr)
        print(result)
        # check OP_DUP
        self.assertEqual(result[0], int('76', 16))
        # check OP_HASH160
        self.assertEqual(result[1], int('A9', 16))
        pubkey_hash = bytearray.fromhex(b58check_to_hex(qmcAddr))
        self.assertEqual(result[2], len(pubkey_hash))
        self.assertEqual(result[3:23], pubkey_hash)
        # check OP_QEUALVERIFY
        self.assertEqual(result[23], int('88', 16))
        # check OP_CHECKSIG
        self.assertEqual(result[24], int('AC', 16))
        
        
        
        
    
    def getRandomChar(self):
        import string
        import random
        return random.choice(string.ascii_letters)
    
    
    
    if __name__ == '__main__':
        unittest.main(verbosity=2)