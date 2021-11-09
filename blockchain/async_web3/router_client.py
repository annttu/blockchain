import asyncio
import time
from decimal import Decimal
from typing import Dict, Optional, List

from web3.contract import Contract

from blockchain import utils
from blockchain.async_web3.client import AsyncClient
from blockchain.async_web3.contract import AsyncToken, async_get_abi, AsyncContract, AsyncLPContract
from blockchain.exceptions import NotFoundException, ContractLogicError

import web3.exceptions


class FactoryContract(AsyncContract):
    def __init__(self, client: AsyncClient, contract_address: str, abi: Dict):
        super().__init__(w3=client.w3, address=contract_address, abi=abi)
        self.client = client
        self.lp_abi = None
        self.lp_factory = None

    async def get_lp_factory(self):
        if not self.lp_abi:
            self.lp_abi = await async_get_abi("PancakeLP")
        if not self.lp_factory:
            self.lp_factory = Contract.factory(web3=self.w3, abi=self.lp_abi)
        return self.lp_factory

    async def get_lp(self, token0: AsyncToken, token1: AsyncToken) -> AsyncLPContract:
        await self.get_lp_factory()
        address = await self.call_function(self.contract.functions.getPair(token0.address, token1.address))
        if not address or address == '0x0000000000000000000000000000000000000000':
            raise NotFoundException(f"Pair not found for tokens {token0} {token1}")
        return await AsyncLPContract.create(w3=self.w3, address=address, contract_factory=self.lp_factory)

    async def get_lp_by_address(self, address: str):
        await self.get_lp_factory()
        return await AsyncLPContract.create(w3=self.w3, address=address, contract_factory=self.lp_factory)

    def __str__(self):
        return f"<FactoryContract {self._name} {self.address}>"

    def __repr__(self):
        return self.__str__()


class AsyncRouterClient(AsyncContract):
    """
    Add Router Swap functions
    """

    def __init__(self, client: AsyncClient, contract_address: str, abi: Dict, max_cache_size: int = 100):
        super().__init__(w3=client.w3, address=contract_address, abi=abi)
        self.client = client
        self._factory: Optional[FactoryContract] = None
        if max_cache_size > 0:
            self._lp_cache = utils.LRUDict(max_size=max_cache_size)
        else:
            self._lp_cache = None
        self.max_cache_size = max_cache_size

    async def get_factory(self) -> FactoryContract:
        if not self._factory:
            address = await self.call_function(self.contract.functions.factory())
            self._factory = FactoryContract(
                client=self.client,
                contract_address=address,
                abi=await async_get_abi("PancakeV2Factory")  # TODO: Get correct ABI
            )
        return self._factory

    async def get_lp(self, token0: AsyncToken, token1: AsyncToken) -> AsyncLPContract:
        if self.max_cache_size == 0 or (token0.address, token1.address) not in self._lp_cache:
            contract_factory = await self.get_factory()
            lp = await contract_factory.get_lp(
                token0=token0, token1=token1
            )
            if self.max_cache_size == 0:
                return lp
            self._lp_cache[(token0.address, token1.address)] = lp
        return self._lp_cache[(token0.address, token1.address)]

    async def get_amount_out(self, token0: AsyncToken, token1: AsyncToken, amount_in: int) -> int:
        lp = await self.get_lp(token0, token1)
        reserves, lp_token0, lp_token1 = await asyncio.gather(
            lp.get_reserves(),
            lp.token0(),
            lp.token1(),
        )

        if not reserves:
            raise RuntimeError(f"Failed to get reserves")
        if token0.address == lp_token0 and token1.address == lp_token1:
            reserve_in = reserves[0]
            reserve_out = reserves[1]
        elif token0.address == lp_token1 and token1.address == lp_token0:
            reserve_in = reserves[1]
            reserve_out = reserves[0]
        else:
            raise RuntimeError(f"Got LP token {lp.address} which don't match pair {token0} {token1}")

        try:
            return await self.call_function(self.contract.functions.getAmountOut(amount_in, reserve_in, reserve_out))
        except web3.exceptions.ContractLogicError:
            raise ContractLogicError("ContractLogicError")

    async def get_reserves(self, token0: AsyncToken, token1: AsyncToken):
        lp = await self.get_lp(token0, token1)
        reserves = await lp.get_reserves()

        if await lp.token0() == token0.address:
            return reserves
        else:
            return reserves[1], reserves[0], reserves[2]

    async def get_price(
            self,
            token0: AsyncToken,
            token1: AsyncToken,
            reference_token: AsyncToken,
            amount_in: int
    ) -> Decimal:
        amount_out = await self.get_amount_out(token0=token0, token1=token1, amount_in=amount_in)
        token0_decimals, token1_decimals = await asyncio.gather(
            token0.toDecimals(amount_in),
            token1.toDecimals(amount_out)
        )
        if reference_token == token0:
            return token0_decimals / token1_decimals
        elif reference_token == token1:
            return token1_decimals / token0_decimals
        else:
            raise ValueError("reference_token is neither token0 nor token1")

    def __str__(self):
        return f"<RouterContract {self._name} {self.address}>"

    def __repr__(self):
        return self.__str__()

    async def swap_tx(
        self,
        path: List[AsyncToken],
        amount_in: int,
        amount_out_min: int = None,
        timeout: int = 60
    ):
        token_pair = []
        address_path = []
        lp_pairs = []

        # Let's test all lp pairs exists
        for token in path:
            if len(token_pair) == 2:
                token_pair.pop(0)
            token_pair.append(token)
            address_path.append(token.address)
            if len(token_pair) == 2:
                lp = await self.get_lp(token_pair[0], token_pair[1])
                lp_pairs.append(lp)
        deadline = int(time.time() + timeout)
        tx = self.contract.functions.swapExactTokensForTokensSupportingFeeOnTransferTokens(
            amount_in,
            amount_out_min,
            address_path,
            self.client.public_key,
            deadline,
        )

        return tx

    async def swap(
            self,
            path: List[AsyncToken],
            amount_in: int,
            amount_out_min: int = None,
            timeout: int = 60,
            gas_price: int = None,
            gas_estimate: int = None
    ):

        tx = await self.swap_tx(path=path, amount_in=amount_in, amount_out_min=amount_out_min, timeout=timeout)

        await self.client.test_transaction(tx)

        signed_tx = self.client.sign_transaction(tx, gas_price=gas_price, gas_estimate=gas_estimate)

        sent_tx = await self.client.send_transaction(signed_tx)

        return sent_tx


async def get_async_router(client, contract_address, abi_file):
    return AsyncRouterClient(
        client=client,
        contract_address=contract_address,
        abi=await async_get_abi(abi_file),
    )
