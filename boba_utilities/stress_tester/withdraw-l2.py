# Utility for withdrawing L2->L1

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
import rlp

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
assert (w3.isConnected)
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

l2 = Web3(Web3.HTTPProvider("http://127.0.0.1:9545"))
assert (l2.isConnected)
l2.middleware_onion.inject(geth_poa_middleware, layer=0)

addr=Web3.toChecksumAddress("0xb0bA04c08d8f1471bcA20C12a64DcCa17B01d96f")
key="c9776e5eb09b348dfde140019e21142503d3c2a5c6d2019d0b30f5099ff2c8dd"

balStart = w3.eth.getBalance(addr)
print ("L1 Balance Start:", balStart)

with open("../../optimism/packages/contracts-bedrock/artifacts/contracts/L2/L2StandardBridge.sol/L2StandardBridge.json") as f:
  abi = json.loads(f.read())['abi']
l2sb = l2.eth.contract(address="0x4200000000000000000000000000000000000010", abi=abi)

with open("../../optimism/packages/contracts-bedrock/artifacts/contracts/L2/L2ToL1MessagePasser.sol/L2ToL1MessagePasser.json") as f:
  abi = json.loads(f.read())['abi']
l2mp = l2.eth.contract(address="0x4200000000000000000000000000000000000016", abi=abi)

with open("../../optimism/packages/contracts-bedrock/artifacts/contracts/L1/OptimismPortal.sol/OptimismPortal.json") as f:
  abi = json.loads(f.read())['abi']
l1op = w3.eth.contract(address="0x6900000000000000000000000000000000000001", abi=abi)

print("Challenge Period:", l1op.functions.FINALIZATION_PERIOD_SECONDS().call())
ooAddr = l1op.functions.L2_ORACLE().call()

with open("../../optimism/packages/contracts-bedrock/artifacts/contracts/L1/L2OutputOracle.sol/L2OutputOracle.json") as f:
  abi = json.loads(f.read())['abi']
l2oo = w3.eth.contract(address=ooAddr, abi=abi)


print("Starting at blocks", w3.eth.blockNumber, l2.eth.blockNumber)

T0 = time.time()

if False:
  # Basic health check
  tx = {
      'type':2,
      'nonce': l2.eth.get_transaction_count(addr),
      'from':addr,
      'to':addr,
      'gas':21000,
      'maxFeePerGas':Web3.toWei(10, 'gwei'),
      'maxPriorityFeePerGas':Web3.toWei(10, 'gwei'),
      'chainId': 901,
      'value':Web3.toWei(123, 'wei'),
  }
  signed_txn =l2.eth.account.sign_transaction(tx, key)
  ret2 = l2.eth.send_raw_transaction(signed_txn.rawTransaction)
  print("healthcheck tx", Web3.toHex(ret2))
  rcpt = l2.eth.wait_for_transaction_receipt(ret2)
  print("test-send tx", rcpt)
  assert(rcpt.status == 1)

tx = l2mp.functions.initiateWithdrawal(
	addr,
	100000,
	"",
      ).buildTransaction({
       'nonce': l2.eth.get_transaction_count(addr),
       'from':addr,
       'chainId': 901,
       'gas':100000,
       'maxFeePerGas':Web3.toWei(10, 'gwei'),
       'value':Web3.toWei(0.005, 'ether'),
      })

signed_txn =l2.eth.account.sign_transaction(tx, key)
ret2 = l2.eth.send_raw_transaction(signed_txn.rawTransaction)
print("Submitted ETH Withdrawal TX", Web3.toHex(ret2))
      
rcpt = l2.eth.wait_for_transaction_receipt(ret2)
print("Got receipt in block", rcpt.blockNumber, "status", rcpt.status, "time", time.time() - T0, "gasPrice", rcpt.effectiveGasPrice)
if rcpt.status != 1:
  print("FAILED:", rcpt)

assert(rcpt.status == 1)
print("Tx", Web3.toHex(ret2), "BN", rcpt.blockNumber)

log1 = l2mp.events.MessagePassed().processReceipt(rcpt,errors=DISCARD)
wt = log1[0].args
mHash = log1[0].args.withdrawalHash

# print("withdrawal msg",wt)
mTmp = Web3.toHex(mHash) + "0000000000000000000000000000000000000000000000000000000000000000"
mKey = Web3.sha3(hexstr=mTmp)
print("Withdrawal msgHash", Web3.toHex(mHash), "storageKey", Web3.toHex(mKey))

# Hack to test overlapping withdrawal requests
#print("Delaying at", l2.eth.blockNumber)
#time.sleep(75)
#print("Continuing at", l2.eth.blockNumber)

# Wait for an opportunity to construt a proof
atBlock = l2.eth.blockNumber
print("Waiting for proof block.",flush=True,end='')
while atBlock % 20 != 0:
  print(".",flush=True,end='')
  time.sleep(0.5)
  atBlock = l2.eth.blockNumber
print(" done({})".format(atBlock))

bb = l2.eth.getBlock(atBlock)
print("Block stateRoot {} blockHash {}".format(Web3.toHex(bb.stateRoot), Web3.toHex(bb.hash)))

print()
print("Will call eth.getProof")
aProof = l2.eth.getProof("0x4200000000000000000000000000000000000016", [mKey], 'latest')
print("Proof retuned storageHash {}".format(Web3.toHex(aProof.storageHash)))
print()
print("Account Proof:", aProof.accountProof)
sProof = rlp.encode(aProof.storageProof[0].proof)
print("Storage Proof", Web3.toHex(sProof))
print()

orp = {
  'version':Web3.toBytes(hexstr="0x0000000000000000000000000000000000000000000000000000000000000000"),
  'stateRoot':bb.stateRoot,
  'messagePasserStorageRoot': aProof.storageHash,
  'latestBlockhash':bb.hash
}

obn = l2oo.functions.latestBlockNumber().call()
print("Waiting for Output Oracle, block {}/{}".format(obn, atBlock))
while obn < atBlock:
  print("waiting, {} < {}... (L2BN={})".format(obn, atBlock,l2.eth.blockNumber))
  time.sleep(5)
  obn = l2oo.functions.latestBlockNumber().call()

oProp = l2oo.functions.getL2OutputAfter(obn).call()
print("Output Root {} Timestamp {}".format(Web3.toHex(oProp[0]), oProp[2]))

# For non-zero challenge period, wait here until valid Timestamp

oIdx = l2oo.functions.getL2OutputIndexAfter(obn).call()

tx = l1op.functions.proveWithdrawalTransaction(
	wt,
	oIdx,
	orp,
	aProof.storageProof[0].proof # sproof
  ).buildTransaction({
       'nonce': w3.eth.get_transaction_count(addr),
       'from':addr,
       'chainId': 900,
  })
  
balStart = w3.eth.getBalance(addr)
print ("L1 Balance BeforeTx:", balStart)
 
signed_txn =w3.eth.account.sign_transaction(tx, key)
ret2 = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
print("Submitted WithdrawalProof TX", Web3.toHex(ret2))

rcpt = w3.eth.wait_for_transaction_receipt(ret2)
print("Got receipt in block", rcpt.blockNumber, "status", rcpt.status, "time", time.time() - T0, "gasPrice", rcpt.effectiveGasPrice)
#print(rcpt)
assert(rcpt.status == 1)

tx = l1op.functions.finalizeWithdrawalTransaction(
	wt
  ).buildTransaction({
       'nonce': w3.eth.get_transaction_count(addr),
       'from':addr,
       'chainId': 900,
  })
signed_txn =w3.eth.account.sign_transaction(tx, key)
ret2 = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
print("Submitted WithdrawFinal TX", Web3.toHex(ret2))
      
rcpt = w3.eth.wait_for_transaction_receipt(ret2)
print("Got receipt in block", rcpt.blockNumber, "status", rcpt.status, "time", time.time() - T0, "gasPrice", rcpt.effectiveGasPrice)
#print(rcpt)
assert(rcpt.status == 1)

balFinal = w3.eth.getBalance(addr)
print ("L1 Balance After:", balFinal)
assert(balFinal > balStart)
print ("Balance change:", Web3.fromWei(balFinal - balStart,'ether'))
