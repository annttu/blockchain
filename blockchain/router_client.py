import time
from decimal import Decimal
from typing import Dict, Optional, List

from .contract import get_abi, Contract, LPContract
from .client import Client
from .contract import Token
from .exceptions import NotFoundException, BlockchainException, ContractLogicError

import web3.exceptions

class FactoryContract(Contract):
    def __init__(self, client: Client, contract_address: str, abi: Dict):
        super().__init__(w3=client.w3, address=contract_address, abi=abi)
        self.client = client
        self.lp_abi = None
        self.lp_factory = None

    def get_lp(self, token0: Token, token1: Token):
        if not self.lp_abi:
            self.lp_abi = get_abi("PancakeLP")
        if not self.lp_factory:
            self.lp_factory = self.w3.eth.contract(abi=self.lp_abi)
        address = self.contract.functions.getPair(token0.address, token1.address).call()
        if not address or address == '0x0000000000000000000000000000000000000000':
            raise NotFoundException(f"Pair not found for tokens {token0} {token1}")
        return LPContract(w3=self.w3, address=address, contract_factory=self.lp_factory)

    def __str__(self):
        return f"<FactoryContract {self.name} {self.address}>"

    def __repr__(self):
        return self.__str__()


class RouterClient(Contract):
    """
    Add Router Swap functions
    """

    def __init__(self, client: Client, contract_address: str, abi: Dict):
        super().__init__(w3=client.w3, address=contract_address, abi=abi)
        self.client = client
        self._factory: Optional[FactoryContract] = None
        self._lp_cache = {}

    def get_factory(self) -> FactoryContract:
        if not self._factory:
            address = self.contract.functions.factory().call()
            self._factory = FactoryContract(
                client=self.client,
                contract_address=address,
                abi=get_abi("PancakeV2Factory")  # TODO: Get correct ABI
            )
        return self._factory

    def get_lp(self, token0: Token, token1: Token) -> LPContract:
        if (token0.address, token1.address) not in self._lp_cache:
            self._lp_cache[(token0.address, token1.address)] = self.get_factory().get_lp(token0=token0, token1=token1)
        return self._lp_cache[(token0.address, token1.address)]

    def get_amount_out(self, token0: Token, token1: Token, amount_in: int) -> int:
        lp = self.get_lp(token0, token1)
        reserves = lp.get_reserves()
        lp_token0 = lp.token0()
        lp_token1 = lp.token1()
        if token0.address == lp_token0 and token1.address == lp_token1:
            reserve_in = reserves[0]
            reserve_out = reserves[1]
        elif token0.address == lp_token1 and token1.address == lp_token0:
            reserve_in = reserves[1]
            reserve_out = reserves[0]
        else:
            raise RuntimeError(f"Got LP token {lp.address} which don't match pair {token0} {token1}")

        try:
            return self.contract.functions.getAmountOut(amount_in, reserve_in, reserve_out).call()
        except web3.exceptions.ContractLogicError:
            raise ContractLogicError("ContractLogicError")

    def get_reserves(self, token0: Token, token1: Token):
        lp = self.get_lp(token0, token1)
        reserves = lp.get_reserves()

        if lp.token0() == token0.address:
            return reserves
        else:
            return reserves[1], reserves[0], reserves[2]

    def get_price(self, token0: Token, token1: Token, reference_token: Token, amount_in: int) -> Decimal:
        amount_out = self.get_amount_out(token0=token0, token1=token1, amount_in=amount_in)
        if reference_token == token0:
            return token0.toDecimals(amount_in) / token1.toDecimals(amount_out)
        elif reference_token == token1:
            return token1.toDecimals(amount_out) / token0.toDecimals(amount_in)
        else:
            raise ValueError("reference_token is neither token0 nor token1")

    def __str__(self):
        return f"<RouterContract {self.name} {self.address}>"

    def __repr__(self):
        return self.__str__()

    def swap_tx(
        self,
        path: List[Token],
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
                lp = self.get_lp(token_pair[0], token_pair[1])
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

    def swap(
            self,
            path: List[Token],
            amount_in: int,
            amount_out_min: int = None,
            timeout: int = 60,
            gas_price: int = None,
            gas_estimate: int = None
    ):

        tx = self.swap_tx(path=path, amount_in=amount_in, amount_out_min=amount_out_min, timeout=timeout)

        self.client.test_transaction(tx)

        signed_tx = self.client.sign_transaction(tx, gas_price=gas_price, gas_estimate=gas_estimate)

        sent_tx = self.client.send_transaction(signed_tx)

        return sent_tx


def get_router(client, contract_address, abi_file):
    return RouterClient(
        client=client,
        contract_address=contract_address,
        abi=get_abi(abi_file),
    )
