"""
Proof of concept asyncio contract support
"""

import itertools
import json
import os
from decimal import Decimal
from typing import Union, Tuple, Callable, Any, Optional

import aiofiles
from eth_abi.exceptions import DecodingError
from eth_typing import ChecksumAddress
from web3 import Web3
from web3._utils.abi import get_abi_output_types, map_abi_data
from web3._utils.contracts import prepare_transaction, find_matching_fn_abi
from web3._utils.normalizers import BASE_RETURN_NORMALIZERS
from web3.contract import Contract, ContractFunction, ACCEPTABLE_EMPTY_STRINGS
from web3.exceptions import BadFunctionCallOutput
from web3.types import TxParams, FunctionIdentifier, BlockIdentifier, ABI, ABIFunction, CallOverrideParams

package_path = os.path.dirname(os.path.abspath(__file__))


async def async_read_abi_file(filename):
    async with aiofiles.open(filename, mode='r') as f:
        content = await f.read()
    return json.loads(content)


async def async_get_abi(name):
    abi_file = os.path.join(package_path, f"../contracts/{name}.json")
    return await async_read_abi_file(abi_file)


async def call_contract_function(
        web3: Web3,
        address: ChecksumAddress,
        normalizers: Tuple[Callable[..., Any], ...],
        function_identifier: FunctionIdentifier,
        transaction: TxParams,
        block_id: Optional[BlockIdentifier] = None,
        contract_abi: Optional[ABI] = None,
        fn_abi: Optional[ABIFunction] = None,
        state_override: Optional[CallOverrideParams] = None,
        fn_args: Any = [],
        fn_kwargs: Any = {}) -> Any:
    """
    Helper function for interacting with a contract function using the
    `eth_call` API.
    """
    call_transaction = prepare_transaction(
        address,
        web3,
        fn_identifier=function_identifier,
        contract_abi=contract_abi,
        fn_abi=fn_abi,
        transaction=transaction,
        fn_args=fn_args,
        fn_kwargs=fn_kwargs,
    )

    return_data = await web3.eth.call(
        call_transaction,
        block_identifier=block_id,
        state_override=state_override,
    )

    if fn_abi is None:
        fn_abi = find_matching_fn_abi(contract_abi, web3.codec, function_identifier, args, kwargs)

    output_types = get_abi_output_types(fn_abi)

    try:
        output_data = web3.codec.decode_abi(output_types, return_data)
    except DecodingError as e:
        # Provide a more helpful error message than the one provided by
        # eth-abi-utils
        is_missing_code_error = (
            return_data in ACCEPTABLE_EMPTY_STRINGS
            and web3.eth.get_code(address) in ACCEPTABLE_EMPTY_STRINGS)
        if is_missing_code_error:
            msg = (
                "Could not transact with/call contract function, is contract "
                "deployed correctly and chain synced?"
            )
        else:
            msg = (
                f"Could not decode contract function call to {function_identifier} with "
                f"return data: {str(return_data)}, output_types: {output_types}"
            )
        raise BadFunctionCallOutput(msg) from e

    _normalizers = itertools.chain(
        BASE_RETURN_NORMALIZERS,
        normalizers,
    )
    normalized_data = map_abi_data(_normalizers, output_types, output_data)

    if len(normalized_data) == 1:
        return normalized_data[0]
    else:
        return normalized_data


class AsyncContract(object):

    def __init__(self, w3, address, abi, name=None, contract_factory=None):
        self.w3 = w3
        self.address = address
        self.abi = abi
        self._name = name

        if not contract_factory:
            self._contract_factory = Contract.factory(web3=self.w3, abi=abi)
        else:
            self._contract_factory = contract_factory
        self.contract = self._contract_factory(address=self.address)

    async def call_function(self, function: ContractFunction, tx_kwargs=None, block_id=None):
        tx: TxParams = {}
        if not tx_kwargs:
            tx_kwargs = {}
        tx.update(tx_kwargs)
        # tx["data"] = function._encode_transaction_data()
        tx["to"] = self.address
        return await call_contract_function(
            web3=self.w3,
            address=self.address,
            transaction=tx,
            normalizers=tuple(),
            function_identifier=function.function_identifier,
            contract_abi=self.abi,
            fn_abi=function.abi,
            fn_args=function.args,
            fn_kwargs=function.kwargs,
            block_id=block_id,
            # **kwargs,
        )

    async def name(self):
        return self._name

    def __str__(self):
        return f"<AsyncContract {self._name}>"

    def __repr__(self):
        return self.__str__()


class AsyncLPContract(AsyncContract):
    def __init__(self, w3, address, abi, contract_factory=None):
        super().__init__(w3, address, abi=abi, name=None, contract_factory=contract_factory)
        self._name = None
        self._token0 = None
        self._token1 = None
        self._factory = None

    @classmethod
    async def create(cls, w3, address, contract_factory=None):
        abi = await async_get_abi("PancakeLP")
        return cls(w3, address, abi=abi, contract_factory=contract_factory)

    async def name(self, block_id=None):
        if not self._name:
            self._name = await self.call_function(self.contract.functions.name(), block_id=block_id)
        return self._name

    async def token0(self, block_id=None):
        if not self._token0:
            self._token0 = await self.call_function(self.contract.functions.token0(), block_id=block_id)
        return self._token0

    async def token1(self, block_id=None):
        if not self._token1:
            self._token1 = await self.call_function(self.contract.functions.token1(), block_id=block_id)
        return self._token1

    async def get_reserves(self, block_id=None):
        return await self.call_function(self.contract.functions.getReserves(), block_id=block_id)

    async def factory(self, block_id=None):
        if not self._factory:
            self._factory = await self.call_function(self.contract.functions.factory(), block_id=block_id)
        return self._factory

    def __str__(self):
        return f"<LPContract {self._name}>"

    def __repr__(self):
        return self.__str__()


class AsyncToken(AsyncContract):
    def __init__(self, w3, address, abi, contract_factory=None):
        super().__init__(w3, address, abi=abi, name=None, contract_factory=contract_factory)
        self._symbol = None
        self._decimals = None

    @classmethod
    async def create(cls, w3, address, abi_file="token", contract_factory=None):
        abi = await async_get_abi(abi_file)
        self = cls(w3, address=address, abi=abi, contract_factory=contract_factory)
        return self

    async def symbol(self):
        if not self._symbol:
            self._symbol = await self.call_function(self.contract.functions.symbol())
        return self._symbol

    async def decimals(self) -> int:
        if self._decimals is None:
            self._decimals = await self.call_function(self.contract.functions.decimals())
        return self._decimals

    async def balanceOf(self, address, block_id=None):
        return await self.call_function(self.contract.functions.balanceOf(address), block_id=block_id)

    async def balanceOfDecimal(self, address, block_id=None):
        divider = Decimal("10") ** await self.decimals()
        raw_balance = await self.balanceOf(address, block_id=block_id)
        return Decimal(raw_balance) / divider

    async def totalSupply(self):
        divider = Decimal("10") ** await self.decimals()
        return Decimal(await self.call_function(self.contract.functions.totalSupply())) / divider

    async def approve(self, spender, amount=0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff):
        return self.contract.functions.approve(spender, amount)

    async def allowance(self, owner, spender):
        return await self.call_function(self.contract.functions.allowance(owner, spender))

    async def toDecimals(self, amount):
        """
        Convert uint256 presentation to decimal number
        """
        return Decimal(amount) / Decimal(10 ** await self.decimals())

    async def fromDecimals(self, amount):
        """
        Convert Decimal number to uint256
        """
        return int(Decimal(amount) * Decimal(10 ** await self.decimals()))

    async def withdraw(self, amount):
        return self.contract.functions.withdraw(amount)

    def __str__(self):
        return f"<Contract {self._name}({self._symbol}) {self.address}>"

    def __repr__(self):
        return self.__str__()


AsyncContractType = Union[AsyncLPContract, AsyncToken]
