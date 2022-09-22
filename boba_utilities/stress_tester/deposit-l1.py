# Utility for triggering Bedrock cross-chain L1->L2 deposits

import os,sys
from web3 import Web3
import threading
import signal
import time
from random import *
import queue
import requests,json
from web3.gas_strategies.time_based import fast_gas_price_strategy
from web3.middleware import geth_poa_middleware
from web3.logs import STRICT, IGNORE, DISCARD, WARN
import logging

from utils import Account,Addrs,Context,LoadEnv,lPrint,wPrint

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
assert (w3.isConnected)
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

print("Starting at block", w3.eth.blockNumber)

addr=Web3.toChecksumAddress("0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266")
key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

# deposit_contract_address from .devnet/rollup.json
dest=Web3.toChecksumAddress("0x6900000000000000000000000000000000000001")

cc = True
while cc:
  tx = {
      'nonce': w3.eth.get_transaction_count(addr),
      'from':addr,
      'to':dest,
      'gas':210000,
      'chainId': 900,
      'value': 12345
  }
  if w3.eth.gasPrice > 1000000:
    tx['gasPrice'] = w3.eth.gasPrice
  else:
    tx['gasPrice'] = Web3.toWei(1, 'gwei')
  
  signed_txn =w3.eth.account.sign_transaction(tx, key)
  T0 = time.time()
  ret = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
  print("\nSubmitted TX", Web3.toHex(ret))
  rcpt = w3.eth.wait_for_transaction_receipt(ret)
  print("Got receipt in block", rcpt.blockNumber, "status", rcpt.status, "time", time.time() - T0, "gasPrice", rcpt.effectiveGasPrice)
  #print(rcpt)
  assert(rcpt.status == 1)
  time.sleep(1)

