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

l2 = Web3(Web3.HTTPProvider("http://127.0.0.1:9545"))
assert (l2.isConnected)
l2.middleware_onion.inject(geth_poa_middleware, layer=0)

print("Starting at blocks", w3.eth.blockNumber, l2.eth.blockNumber)

#addr=Web3.toChecksumAddress("0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266")
#key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

addr=Web3.toChecksumAddress("0xb0bA04c08d8f1471bcA20C12a64DcCa17B01d96f")
key="c9776e5eb09b348dfde140019e21142503d3c2a5c6d2019d0b30f5099ff2c8dd"

# deposit_contract_address from .devnet/rollup.json
dest=Web3.toChecksumAddress("0x6900000000000000000000000000000000000001")

with open("../../optimism/packages/contracts-bedrock/artifacts/contracts/boba/BOBA.sol/BOBA.json") as f:
  abi = json.loads(f.read())['abi']
boba_l1 = w3.eth.contract(address="0x154C5E3762FbB57427d6B03E7302BDA04C497226", abi=abi)

with open("../../optimism/packages/contracts-bedrock/artifacts/contracts/universal/OptimismMintableERC20.sol/OptimismMintableERC20.json") as f:
  abi = json.loads(f.read())['abi']

boba_l2 = l2.eth.contract(address=Web3.toChecksumAddress("0x42000000000000000000000000000000000000fe"), abi=abi)

with open("../../optimism/packages/contracts-bedrock/artifacts/contracts/L1/L1StandardBridge.sol/L1StandardBridge.json") as f:
  abi = json.loads(f.read())['abi']
l1sb = w3.eth.contract(address="0x6900000000000000000000000000000000000003", abi=abi)

if boba_l1.functions.allowance(addr,l1sb.address).call() == 0:
  print("Approving bridge contract")
  tx = boba_l1.functions.approve(l1sb.address, Web3.toInt(hexstr="0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")).buildTransaction({
      'nonce': w3.eth.get_transaction_count(addr),
      'from':addr,
      'chainId': 900
     })
  signed_txn =w3.eth.account.sign_transaction(tx, key)
  ret = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
  rcpt = w3.eth.wait_for_transaction_receipt(ret)
  assert(rcpt.status == 1)
  print("Approval done")

cc = True
addr2 = Web3.toChecksumAddress("0x42000000000000000000000000000000000000fe")

ethBalance = l2.eth.getBalance(addr)
bobaBalance = boba_l2.functions.balanceOf(addr).call()
print("Starting L2 ETH balance:", Web3.fromWei(ethBalance,'ether'))
print("Starting L2 BOBA balance:", Web3.fromWei(bobaBalance, 'ether'))

while cc:
  n = w3.eth.get_transaction_count(addr)
  tx = {
      'nonce': n,
      'from':addr,
      'to':dest,
      'gas':210000,
      'chainId': 900,
      'value': Web3.toWei(1.001, 'ether')
  }
  if w3.eth.gasPrice > 1000000:
    tx['gasPrice'] = w3.eth.gasPrice
  else:
    tx['gasPrice'] = Web3.toWei(1, 'gwei')
  
  signed_txn =w3.eth.account.sign_transaction(tx, key)
  T0 = time.time()
  ret = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
  print("\nSubmitted ETH TX", Web3.toHex(ret))
  rcpt = w3.eth.wait_for_transaction_receipt(ret)
  print("Got ETH receipt in block", rcpt.blockNumber, "status", rcpt.status, "time", time.time() - T0, "gasPrice", rcpt.effectiveGasPrice)
  assert(rcpt.status == 1)
  time.sleep(1)
  
  n += 1
  
  tx = l1sb.functions.depositERC20(
  	boba_l1.address,
    	addr2,
	Web3.toWei(1.2345678, 'ether'),
	4000000,
	"").buildTransaction({
          'nonce': n,
          'from':addr,
          'chainId': 900
	})
  signed_txn =w3.eth.account.sign_transaction(tx, key)
  ret2 = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
  print("Submitted BOBA TX", Web3.toHex(ret2))
  	
  rcpt = w3.eth.wait_for_transaction_receipt(ret2)
  print("Got BOBA receipt in block", rcpt.blockNumber, "status", rcpt.status, "time", time.time() - T0, "gasPrice", rcpt.effectiveGasPrice)
  assert(rcpt.status == 1)
 
  time.sleep(1)

  # It takes time to process deposits so these will lag. 
  ethBalance = l2.eth.getBalance(addr)
  bobaBalance = boba_l2.functions.balanceOf(addr).call()

  print()
  print("L2 ETH balance:", Web3.fromWei(ethBalance,'ether'))
  print("L2 BOBA balance:", Web3.fromWei(bobaBalance, 'ether'))
  time.sleep(1)
