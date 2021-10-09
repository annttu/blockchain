import asyncio
import concurrent.futures
import logging
from typing import Callable, Union

from eth_account import Account
from eth_account.datastructures import SignedTransaction
from eth_typing import HexStr
from hexbytes import HexBytes
from web3 import Web3
from web3._utils.rpc_abi import RPC
from web3._utils.threads import Timeout
from web3.eth import AsyncEth
from web3.exceptions import TransactionNotFound, TimeExhausted
from web3.method import Method, default_root_munger
from web3.net import AsyncNet
from web3.providers import BaseProvider
from web3.types import TxReceipt, _Hash32

from blockchain import networks
from blockchain.async_web3.contract import AsyncToken, AsyncLPContract
from blockchain.async_web3.middleware import async_geth_poa_middleware
from blockchain.async_web3.rpc import PooledAsyncHTTPProvider
from blockchain.exceptions import BlockchainException

import aiologger

"""
NOTE: This is quite a Proof of Concept for async client, not all features are supported.

TODO: Replace sync web3 calls with async
"""

logger = aiologger.Logger.with_default_handlers(name=__name__, level=logging.INFO)


async def wait_for_transaction_receipt(
    web3: "Web3", txn_hash: _Hash32, timeout: float, poll_latency: float
) -> TxReceipt:
    with Timeout(timeout) as _timeout:
        while True:
            try:
                txn_receipt = await web3.eth.get_transaction_receipt(txn_hash)
            except TransactionNotFound:
                txn_receipt = None
            # FIXME: The check for a null `blockHash` is due to parity's
            # non-standard implementation of the JSON-RPC API and should
            # be removed once the formal spec for the JSON-RPC endpoints
            # has been finalized.
            if txn_receipt is not None and txn_receipt['blockHash'] is not None:
                break
            _timeout.sleep(poll_latency)
    return txn_receipt


class CustomAsyncEth(AsyncEth):
    send_raw_transaction: Method[Callable[[Union[HexStr, bytes]], HexBytes]] = Method(
        RPC.eth_sendRawTransaction,
        mungers=[default_root_munger],
    )

    async def wait_for_transaction_receipt(
        self, transaction_hash: _Hash32, timeout: int = 120, poll_latency: float = 0.1
    ) -> TxReceipt:
        try:
            return await wait_for_transaction_receipt(self.web3, transaction_hash, timeout, poll_latency)
        except Timeout:
            raise TimeExhausted(
                "Transaction {!r} is not in the chain, after {} seconds".format(
                    HexBytes(transaction_hash),
                    timeout,
                )
            )

    get_transaction_receipt: Method[Callable[[_Hash32], TxReceipt]] = Method(
        RPC.eth_getTransactionReceipt,
        mungers=[default_root_munger]
    )


def get_provider(address: str) -> Web3:
    if address.startswith("http"):
        connector: BaseProvider = PooledAsyncHTTPProvider(
                address,
                request_kwargs={'timeout': 60}
            )
        return Web3(
            connector,
            modules={
                'eth': (CustomAsyncEth,),
                'net': (AsyncNet,),
            },
            middlewares=[async_geth_poa_middleware],  # Middlewares needs to be set explicitly to empty list
        )
    else:
        raise ValueError("Unsupported provider %s", address)


class AsyncClient(object):
    def __init__(
            self,
            public_key: str,
            private_key: str,
            network: networks.Network = None,
            test_mode: bool = True,
            thread_limit: int = 20,
            default_gas: int = 1,
    ):
        if not network:
            network = networks.get_network_by_name(networks.BINANCE)
        self.network = network
        self.chain_id = network.chain_id
        self.w3 = get_provider(network.provider)
        self.public_key = public_key
        self.private_key = private_key
        self.test_mode = test_mode
        self._nonce = None
        # For blocking calls
        self._sync_pool = concurrent.futures.ThreadPoolExecutor(max_workers=thread_limit)
        self._query_limit_sem = asyncio.Semaphore(thread_limit)
        self._nonce_lock = asyncio.Lock()
        self.default_gas = default_gas

    async def call_async(self, function, *args):
        async with self._query_limit_sem:
            return await self._call_async(function, *args)

    async def _call_async(self, function, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._sync_pool, function, *args)

    async def get_nonce(self):
        network_tx_count = await self.w3.eth.get_transaction_count(self.public_key, 'pending')
        if not self._nonce or network_tx_count > self._nonce:
            self._nonce = network_tx_count
        return self._nonce

    def _update_nonce(self):
        # Update nonce
        if self._nonce is not None:
            self._nonce += 1

    async def get_and_update_nonce(self):
        """
        Fetch and update nonce atomically
        :return:
        """
        async with self._nonce_lock:
            nonce = await self.get_nonce()
            self._update_nonce()
        return nonce

    async def get_gas_price(self):
        gas_price = await self.w3.eth.generate_gas_price()
        if not gas_price:
            logger.info("Gas price generation failed, falling back to default gas fee")
            return self.w3.toWei(self.default_gas, "gwei")
        elif gas_price < self.default_gas:
            logger.info("Generated gas price less than default gas price, falling back to default gas price")
            return self.w3.toWei(self.default_gas, "gwei")
        return gas_price

    async def sign_transaction(
            self,
            tx,
            gas_estimate: int = None,
            gas_price: int = None,
            nonce: int = None,
    ) -> SignedTransaction:
        """
        Sign transaction

        gas_price in gwei
        """
        if not gas_estimate:
            # TODO: Does this require any external io?
            gas_estimate = await tx.estimateGas({"from": self.public_key})
        if not gas_price:
            gas_price = await self.get_gas_price()
            if not gas_price:
                raise BlockchainException("Failed to generate gas price")
        else:
            gas_price = self.w3.toWei(gas_price, 'gwei')
        if not nonce:
            # TODO: this will cause problems if we don't send transaction
            nonce = await self.get_and_update_nonce()
        tx_to_sign = tx.buildTransaction({
            'chainId': self.chain_id,
            'gas': gas_estimate,
            'gasPrice': gas_price,
            'nonce': nonce,
        })
        if self.chain_id is None:
            del tx_to_sign["chainId"]
        await logger.debug(f"Transaction to sign {tx_to_sign}")
        signed = Account().sign_transaction(tx_to_sign, self.private_key)
        return signed

    async def sign_raw_transaction(
            self,
            value,
            gas_estimate,
            data=None,
            to=None,
            gas_price=5,
            nonce: int = None,
    ):
        """
        Sign raw transaction
        """
        if not nonce:
            # TODO: this will cause problems if we don't send transaction
            nonce = await self.get_and_update_nonce()
        tx_to_sign = {
            'gas': gas_estimate,
            'gasPrice': self.w3.toWei(gas_price, 'gwei'),
            'nonce': nonce,
            'value': value,
        }
        if data:
            tx_to_sign["data"] = data
        if to:
            tx_to_sign["to"] = to
        if self.chain_id is not None:
            tx_to_sign["chainId"] = self.chain_id
        await logger.debug(f"Transaction to sign {tx_to_sign}")
        signed = self.w3.eth.account.sign_transaction(tx_to_sign, self.private_key)
        return signed

    async def send_transaction(self, tx):
        """
        Send signed transaction
        :param tx: tx to send
        :return: hash
        """
        if self.test_mode:
            await logger.warning("Not actually sending transaction, disable test mode first")
            return
        hash = await self.w3.eth.send_raw_transaction(tx)
        await logger.info("Transaction hash: {}".format(hash.hex()))
        return hash.hex()

    async def test_transaction(self, tx):
        return await tx.call({'from': self.public_key})

    async def wait_transaction_success(self, tx_hash, timeout=180):
        if self.test_mode:
            await logger.warning("Transactions aren't sent anywhere in test mode")
            return None
        await logger.info(f"Waiting transaction {tx_hash} success")
        for i in range(timeout):
            try:
                receipt = await self.w3.eth.wait_for_transaction_receipt(
                    tx_hash,
                    timeout
                )
                if receipt["status"] != 1:
                    raise Exception(f"Transaction {tx_hash} failed")
                return
            except TransactionNotFound:
                await logger.exception(f"Failed to fetch transaction {tx_hash}")
            except ValueError:
                # TODO: parse exc for actual error from network
                await logger.exception(f"Failed to fetch transaction {tx_hash}")
            await asyncio.sleep(1)
            timeout -= 1
        raise Exception(f"Transaction {tx_hash} not found")

    async def get_token(self, token_address: str) -> AsyncToken:
        # TODO: Check token exists?
        return await AsyncToken.create(self.w3, token_address)

    async def get_lp_contract(self, contract_address: str) -> AsyncLPContract:
        return await AsyncLPContract.create(self.w3, contract_address)
