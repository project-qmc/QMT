#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest

import bitcoin

from qmc_b58 import b58decode
from qmc_hashlib import generate_privkey, pubkey_to_address


class TestQmc_hashlibMethods(unittest.TestCase):

    def test_generate_privkey(self):
        # generate random private key
        randomKey = generate_privkey()
        # check length
        self.assertEqual(len(randomKey), 51)
        # check leading char '8'
        self.assertEqual(randomKey[0], '8')
        # decode and verify checksum
        randomKey_bin = bytes.fromhex(b58decode(randomKey).hex())
        randomKey_bin_check = bitcoin.bin_dbl_sha256(randomKey_bin[0:-4])[0:4]
        self.assertEqual(randomKey_bin[-4:], randomKey_bin_check)

    def test_pubkey_to_address(self):
        # generate random private key and convert to public
        randomPubKey = bitcoin.privkey_to_pubkey(generate_privkey())
        # compute address
        randomQmcAddr = pubkey_to_address(randomPubKey)
        # check leading char 'D'
        self.assertEqual(randomQmcAddr[0], 'D')
        # decode and verify checksum
        randomQmcAddr_bin = bytes.fromhex(b58decode(randomQmcAddr).hex())
        randomQmcAddr_bin_check = bitcoin.bin_dbl_sha256(randomQmcAddr_bin[0:-4])[0:4]
        self.assertEqual(randomQmcAddr_bin[-4:], randomQmcAddr_bin_check)

    if __name__ == '__main__':
        unittest.main(verbosity=2)
