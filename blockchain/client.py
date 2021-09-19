import logging
import os
import time
from typing import Any, Dict
from functools import lru_cache



import requests
import requests.adapters

from eth_account.datastructures import SignedTransaction
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.middleware import geth_poa_middleware

from . import contract, configuration
from .networks import get_network_by_name, Network, BINANCE
from .contract import Token
from .exceptions import BlockchainException, NoBalanceException


logger = logging.getLogger(__name__)

DEFAULT_NETWORK = configuration.get_variable("default_network", BINANCE)


def get_provider(address: str, query_limit: int = 50) -> Web3:
    if address.startswith("ws"):
        return Web3(
            Web3.WebsocketProvider(
                address,
                websocket_timeout=60,
                websocket_kwargs={"max_size": 30000000, "ping_timeout": 180}
            ),
            middlewares=[geth_poa_middleware]
        )
    elif address.startswith("/"):
        return Web3(Web3.IPCProvider(address, timeout=60),
                    middlewares=[geth_poa_middleware])
    else:
        adapter = requests.adapters.HTTPAdapter(pool_connections=query_limit*2,
                                                pool_maxsize=query_limit*2)
        session = requests.Session()
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return Web3(Web3.HTTPProvider(address, session=session, request_kwargs={'timeout': 60}),
                    middlewares=[geth_poa_middleware])


class Client(object):
    def __init__(
            self,
            public_key: str,
            private_key: str,
            network: Network = None,
            test_mode: bool = True,
            w3: Web3 = None,
            default_gas: int = 1
    ):
        if not network:
            network = get_network_by_name(DEFAULT_NETWORK)
        self.network = network
        self.chain_id = network.chain_id
        if not w3:
            w3 = get_provider(network.provider)
        self.w3 = w3
        self.public_key = public_key
        self.private_key = private_key
        self.test_mode = test_mode
        self.default_gas = default_gas
        self._token_factory = None
        self._nonce = None

    def get_nonce(self):
        network_tx_count = self.w3.eth.get_transaction_count(self.public_key)
        if not self._nonce or network_tx_count > self._nonce:
            self._nonce = network_tx_count
        return self._nonce

    def sign_transaction(self, tx, gas_estimate=None, gas_price=None, nonce=None, value=None):
        """
        Sign transaction

        gas_price in gwei
        """

        if gas_price > 10000:
            raise BlockchainException("Way too big gas_price")

        if not gas_estimate:
            gas_estimate = tx.estimateGas({"from": self.public_key})
        if not gas_price:
            gas_price = self.get_gas_price()
            print(gas_price)
            if gas_price is None:
                raise BlockchainException("Failed to generate gas price")
        else:
            gas_price = self.w3.toWei(gas_price, 'gwei')
        if nonce is None:
            nonce = self.get_nonce()
        tx_to_sign = tx.buildTransaction({
            'chainId': self.chain_id,
            'gas': gas_estimate,
            'gasPrice': gas_price,
            'nonce': nonce,
        })
        if value is not None:
            tx_to_sign["value"] = value
        if self.chain_id is None:
            del tx_to_sign["chainId"]
        logger.debug(f"Transaction to sign {tx_to_sign}")
        signed = self.w3.eth.account.sign_transaction(tx_to_sign, self.private_key)
        return signed

    def sign_raw_transaction(self, value, gas_estimate, data=None, to=None, gas_price=5):
        """
        Sign raw transaction
        """
        nonce = self.get_nonce()
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
        logger.debug(f"Transaction to sign {tx_to_sign}")
        signed = self.w3.eth.account.sign_transaction(tx_to_sign, self.private_key)
        return signed

    def send_transaction(self, tx):
        """
        Send signed transaction
        :param tx: tx to send
        :return: hash
        """
        if self.test_mode:
            logger.warning("Not actually sending transaction, disable test mode first")
            return
        hash = self.w3.eth.send_raw_transaction(tx.rawTransaction)
        logger.info("Transaction hash: {}".format(hash.hex()))
        # Update nonce
        if self._nonce is not None:
            self._nonce += 1
        return hash.hex()

    def test_transaction(self, tx):
        return tx.call({'from': self.public_key})

    def wait_transaction_success(self, tx_hash, timeout=180):
        if self.test_mode:
            logger.warning("Transactions aren't sent anywhere in test mode")
            return None
        logger.info(f"Waiting transaction {tx_hash} success")
        for i in range(timeout):
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
                if receipt["status"] != 1:
                    raise Exception(f"Transaction {tx_hash} failed")
                return receipt
            except TransactionNotFound:
                logger.exception("Failed to fetch transaction %(hash)s", {"hash": tx_hash})
            except ValueError:
                # TODO: parse exc for actual error from network
                logger.exception("Failed to fetch transaction %(hash)s", {"hash": tx_hash})
            time.sleep(1)
            timeout -= 1
        raise Exception(f"Transaction {tx_hash} not found")

    def get_gas_price(self):

        gas_price = self.w3.eth.generate_gas_price()
        if not gas_price:
            # TODO: implement
            logger.info("Gas price generation failed, falling back to default gas fee")
            return self.w3.toWei(self.default_gas, "gwei")
        elif gas_price < self.default_gas:
            logger.info("Generated gas price less than default gas price, falling back to default gas price")
            return self.w3.toWei(self.default_gas, "gwei")
        return gas_price

    def send_native_token_tx(self, amount: int, to_address: str) -> Dict:
        """
        Send native token to to_address
        :param amount:
        :param to_address:
        :return:
        """
        balance = self.w3.eth.get_balance(self.public_key)

        if balance < amount:
            balance_decimal = self.w3.fromWei(balance, 'ether')
            amount_decimal = self.w3.fromWei(amount, 'ether')
            raise NoBalanceException(f"Account balance ({balance_decimal:.5f}) less than amount ({amount_decimal:.5f})")

        return dict(
            value=amount,
            to=self.w3.toChecksumAddress(to_address),
            gas_estimate=400000,
        )

    def send_native_token(self, amount: int, to_address: str, gas_price: int = None) -> SignedTransaction:
        tx = self.send_native_token_tx(amount=amount, to_address=to_address)
        tx["gas_price"] = gas_price or self.get_gas_price()
        return self.sign_raw_transaction(**tx)

    def send_token_tx(self, token: Token, amount: int, to_address: str) -> Any:

        balance = token.balanceOf(self.public_key)

        if balance < amount:
            balance_decimal = token.toDecimals(balance)
            amount_decimal = token.toDecimals(amount)
            raise NoBalanceException(f"Account balance ({balance_decimal:.5f}) less than amount ({amount_decimal:.5f})")

        tx = token.contract.functions.transfer(self.w3.toChecksumAddress(to_address), amount)

        return tx

    def send_token(self, token: Token, amount: int, to_address: str, gas_price: int = None) -> SignedTransaction:

        tx = self.send_token_tx(token=token, amount=amount, to_address=to_address)

        self.test_transaction(tx)

        signed_tx = self.sign_transaction(tx, gas_price=gas_price)

        return signed_tx

    def _get_token_factory(self):
        if not self._token_factory:
            self._token_factory = self.w3.eth.contract(abi=contract.get_abi("token"))
        return self._token_factory

    @lru_cache(maxsize=512)
    def get_token(self, token_address: str) -> Token:
        # TODO: Check token exists?
        return Token(self.w3, token_address, contract_factory=self._get_token_factory())

    def approve_tx(
            self,
            token: Token,
            spender: contract.Contract,
            amount: int,
            approve_amount: int = None,
    ) -> Any:
        allowance = token.allowance(self.public_key, spender.address)
        if allowance < amount:
            if approve_amount is None or approve_amount < amount:
                approve_amount = amount
            tx = token.approve(spender=spender.address, amount=approve_amount)
            return tx
        return None

    def approve(
        self,
        token: Token,
        spender: contract.Contract,
        amount: int,
        approve_amount: int = None,
        gas_price: int = None,
        gas_estimate: int = None,
    ):
        tx = self.approve_tx(token=token, spender=spender, amount=amount, approve_amount=approve_amount)
        if tx:
            self.test_transaction(tx)
            signed_tx = self.sign_transaction(tx, gas_price=gas_price, gas_estimate=gas_estimate)
            tx_hash = self.send_transaction(signed_tx)
            return tx_hash
