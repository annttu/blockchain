#!/usr/bin/env python3

import unittest
from decimal import Decimal

from blockchain import contract, keyutils, networks
from blockchain.client import Client
from blockchain.router_client import RouterClient


"""

Address types
0x0.... Tokens
0x1.... Factories
0x2.... LP pairs
0x3.... Routers
"""


LP_TOKENS = {

}


class FakeW3FunctionCallable(object):
    def __init__(self, value):
        self.value = value

    def call(self):
        return self.value


def web3_callable(f):
    def wrapped(*args, **kwargs):
        return FakeW3FunctionCallable(value=f(*args, **kwargs))
    return wrapped


def web3_callable_var(value):
    def wrapped(*args, **kwargs):
        return FakeW3FunctionCallable(value=value)
    return wrapped


TEST_ROUTER = "0x3000000000000000000000000000000000000001"
TEST_TOKEN1 = "0x0000000000000000000000000000000000000001"
TEST_TOKEN2 = "0x0000000000000000000000000000000000000002"
TEST_FACTORY = "0x1000000000000000000000000000000000000001"
TEST_LP = "0x2000000000000000000000000000000000000001"


def test_get_amount_out(amount_in: int, reserve0: int, reserve1: int):
    return (reserve1 * amount_in) / reserve0


class FakeW3FunctionFactory(object):
    _factor_functions = {
        TEST_TOKEN1: {
            "decimals": 18,
            "name": "Test token1",
            "symbol": "TestToken1",
        },
        TEST_TOKEN2: {
            "decimals": 12,
            "name": "Test token2",
            "symbol": "TestToken2",
        },
        # Factory 
        TEST_FACTORY: {
            "getPair": TEST_LP,
        },
        # LP token
        TEST_LP: {
            "token0": TEST_TOKEN2,
            "token1": TEST_TOKEN1,
            "getReserves": (10**12, 10*10**18, 1631377645),
        },
        # Router
        TEST_ROUTER: {
            "factory": TEST_FACTORY,
            "getAmountOut": test_get_amount_out
        },

    }

    def __init__(self, address=None, decimals=18):
        self._decimals = decimals
        self._address = address

    def __getattr__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]

        elif item in self._factor_functions[self._address]:
            val = self._factor_functions[self._address][item]
            if hasattr(val, '__call__'):
                return web3_callable(val)
            return web3_callable_var(val)
        else:
            raise ValueError(f"Unknown function {item} for {self._address}")


class FakeW3Contract(object):

    def __init__(self, address, abi):
        self.address = address
        self.abi = abi

    @property
    def functions(self):
        return FakeW3FunctionFactory(address=self.address)


class FakeWeb3ETH(object):

    def contract(self, address=None, abi=None):
        if address:
            return FakeW3Contract(address=address, abi=abi)

        def contract_factory(address):
            return FakeW3Contract(address=address, abi=abi)
        return contract_factory


class FakeWeb3(object):

    @property
    def eth(self):
        return FakeWeb3ETH()


class FakeClient(Client):
    def __init__(self, test_mode=False):
        account = keyutils.create_account()
        private_key = account.key
        public_key = account.address
        w3 = FakeWeb3()
        network = networks.Network(
            provider="/fake/socket",
            chain_id=123,
            routers=[],
            tokens=[],
            wrapped_native_token=TEST_TOKEN1,
            explorer_tx_url="https://exlorer.fake/tx",
            native_token_decimals=18
        )
        super().__init__(
            public_key=public_key,
            private_key=private_key,
            network=network,
            test_mode=test_mode,
            w3=w3
        )


class RouterClientTest(unittest.TestCase):

    def setUp(self):
        self.client = FakeClient()
        self.router = RouterClient(
            client=self.client,
            contract_address=TEST_ROUTER,
            abi=contract.get_abi("PancakeRouterV2")
        )

    def test_get_amount_out(self):
        token0 = self.client.get_token(TEST_TOKEN1)
        token1 = self.client.get_token(TEST_TOKEN2)
        out = self.router.get_amount_out(token0=token0, token1=token1, amount_in=100000000)
        self.assertEqual(out, 10)

    def test_get_reserves(self):
        token0 = self.client.get_token(TEST_TOKEN1)
        token1 = self.client.get_token(TEST_TOKEN2)
        token0_amount, token1_amount, timestmap = self.router.get_reserves(token0=token0, token1=token1)
        self.assertEqual(token0_amount, 10*10**18)
        self.assertEqual(token1_amount, 10**12)

        token1_amount, token0_amount, timestmap = self.router.get_reserves(token0=token1, token1=token0)
        self.assertEqual(token0_amount, 10 * 10 ** 18)
        self.assertEqual(token1_amount, 10 ** 12)

    def test_get_price(self):
        token0 = self.client.get_token(TEST_TOKEN1)
        token1 = self.client.get_token(TEST_TOKEN2)

        # Test first this way
        price = self.router.get_price(token0=token0, token1=token1, reference_token=token1, amount_in=100000000)
        self.assertEqual(price, Decimal("0.1"))

        # Other way around
        price = self.router.get_price(token0=token1, token1=token0, reference_token=token1, amount_in=100000000)
        self.assertEqual(price, Decimal("0.1"))

    # TODO: test swap_tx


if  __name__ == '__main__':
    unittest.main()
