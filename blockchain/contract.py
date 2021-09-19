import json
import os
from decimal import Decimal
from functools import lru_cache
from typing import Union

import cachetools


package_path = os.path.dirname(os.path.abspath(__file__))


def read_abi_file(filename):
    with open(filename, 'r') as f:
        return json.loads(f.read())


@cachetools.cached(cache=cachetools.LRUCache(maxsize=512))
def get_abi(name):
    abi_file = os.path.join(package_path, f"contracts/{name}.json")
    return read_abi_file(abi_file)


class Contract(object):
    def __init__(self, w3, address, abi, name=None, contract_factory=None):
        self.w3 = w3
        self._name = name
        self.address = address
        self.abi = abi
        if contract_factory:
            self.contract = contract_factory(address=address)
        else:
            self.contract = self.w3.eth.contract(address=address, abi=self.abi)

    @property
    def name(self):
        return self._name

    def decode_function_input(self, input_string):
        args = self.contract.decode_function_input(input_string)
        return {"function": args[0], "arguments": args[1]}

    def __str__(self):
        return f"<Contract {self.name} {self.address}>"

    def __repr__(self):
        return self.__str__()


class LPContract(Contract):
    def __init__(self, w3, address, abi=None, contract_factory=None):
        if not abi:
            abi = get_abi("PancakeLP")
        super().__init__(w3, address, abi=abi, name=None, contract_factory=contract_factory)
        self._name = None

    @property
    def name(self):
        if not self._name:
            self._name = self.contract.functions.name().call()
        return self._name

    @lru_cache()
    def token0(self):
        return self.contract.functions.token0().call()

    @lru_cache()
    def token1(self):
        return self.contract.functions.token1().call()

    def get_reserves(self) -> (int, int, int):
        """
        GET LP pair reserves
        """
        return self.contract.functions.getReserves().call()

    def total_supply(self) -> int:
        """
        Get LP token total supply
        """
        return self.contract.functions.totalSupply().call()

    def __str__(self):
        return f"<LPContract {self.name}>"

    def __repr__(self):
        return self.__str__()


class Token(Contract):
    def __init__(self, w3, address, abi=None, contract_factory=None):
        if not abi:
            abi = get_abi("token")
        super().__init__(w3, address, abi=abi, name=None, contract_factory=contract_factory)
        self._symbol = None
        self._decimals = None

    @property
    def name(self):
        if not self._name:
            self._name = self.contract.functions.name().call()
        return self._name

    @property
    def symbol(self):
        if not self._symbol:
            self._symbol = self.contract.functions.symbol().call()
        return self._symbol

    def decimals(self) -> int:
        if self._decimals is None:
            self._decimals = self.contract.functions.decimals().call()
        return self._decimals

    def balanceOf(self, address, **kwargs):
        return self.contract.functions.balanceOf(address).call(**kwargs)

    def balanceOfDecimal(self, address):
        raw_balance = self.balanceOf(address)
        return self.toDecimals(raw_balance)

    def totalSupply(self):
        divider = Decimal("10") ** self.decimals()
        return Decimal(self.contract.functions.totalSupply().call()) / divider

    def approve(self, spender, amount=0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff):
        return self.contract.functions.approve(spender, amount)

    def allowance(self, owner, spender):
        return self.contract.functions.allowance(owner, spender).call()

    def toDecimals(self, amount):
        """
        Convert uint256 presentation to decimal number
        """
        return Decimal(amount) / Decimal(10**self.decimals())

    def fromDecimals(self, amount):
        """
        Convert Decimal number to uint256
        """
        return int(Decimal(amount) * Decimal(10 ** self.decimals()))

    def withdraw(self, amount):
        return self.contract.functions.withdraw(amount)

    def __str__(self):
        return f"<Contract {self.name}({self.symbol}) {self.address}>"

    def __repr__(self):
        return self.__str__()


ContractType = Union[Contract, LPContract, Token]
