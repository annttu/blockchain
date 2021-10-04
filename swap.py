#!/usr/bin/env python3
import sys
from concurrent.futures.thread import ThreadPoolExecutor
from decimal import Decimal

from web3 import Web3

from blockchain import client, keyutils, networks, router_client
import argparse

from blockchain.networks import binance
from blockchain.contract import Token
from blockchain.router_client import RouterClient
import blockchain.exceptions


class Swapper(object):
    """
    TODO: Support for swaps from native token
    """

    def __init__(self, **kwargs):
        self.client = client.Client(**kwargs)

    def _get_price(self, router: RouterClient, token0: Token, token1: Token, amount: int) -> (Decimal, Token):
        reference_token = token0
        if token1.address in router.client.network.tokens.values():
            reference_token = token1
        return router.get_price(token0=token0, token1=token1, reference_token=reference_token, amount_in=amount), \
            reference_token

    def get_price(self, router: RouterClient, token0: Token, token1: Token, amount: Decimal):
        raw_amount = token0.fromDecimals(amount)
        price, reference_token = self._get_price(router=router, token0=token0, token1=token1, amount=raw_amount)
        return price, reference_token

    def _get_reserves(self, router: RouterClient, token0: Token, token1: Token) -> (int, int):
        token0, token1, timestamp = router.get_reserves(token0=token0, token1=token1)
        return token0, token1

    def get_reserves(self, router: RouterClient, token0: Token, token1: Token) -> (Decimal, Decimal):
        token0_reserves, token1_reserves = self._get_reserves(router=router, token0=token0, token1=token1)
        token0_reserves_decimal = token0.toDecimals(token0_reserves)
        token1_reserves_decimal = token1.toDecimals(token1_reserves)
        return token0_reserves_decimal, token1_reserves_decimal

    def _get_details(self, router: RouterClient, token0: Token, token1: Token, amount_in: int):

        # Balance
        price, reference_token = self._get_price(router=router, token0=token0, token1=token1, amount=amount_in)

        # Reserves
        token0_reserves, token1_reserves = self._get_reserves(router=router, token0=token0, token1=token1)

        percentage = amount_in * 100 / token0_reserves

        return price, reference_token, token0_reserves, token1_reserves, percentage

    def get_details(
            self,
            router: RouterClient,
            token_from: str,
            token_to: str,
            amount_in: Decimal
    ):
        token0 = self.client.get_token(token_from)
        token1 = self.client.get_token(token_to)
        raw_amount = token0.fromDecimals(amount_in)
        price, reference_token, token0_reserves, token1_reserves, percentage = self._get_details(
            router=router, token0=token0, token1=token1, amount_in=raw_amount)
        token0_reserves_decimal = token0.toDecimals(token0_reserves)
        token1_reserves_decimal = token1.toDecimals(token1_reserves)
        return price, reference_token, token0_reserves_decimal, token1_reserves_decimal, percentage

    def get_balance(self, token_address):
        token = self.client.get_token(token_address)
        return token.balanceOfDecimal(self.client.public_key)

    def swap_tokens(
            self,
            router: RouterClient,
            token_from: str,
            token_to: str,
            amount_in: Decimal,
            slippage: int,
            gas_price: int
    ):
        token0 = self.client.get_token(token_from)
        token1 = self.client.get_token(token_to)

        amount_in_raw = token0.fromDecimals(amount_in)

        price, reference_token, token0_reserves, token1_reserves, percentage = self._get_details(
            router=router,
            token0=token0,
            token1=token1,
            amount_in=amount_in_raw
        )

        token0_reserves_decimal = token0.toDecimals(token0_reserves)
        token1_reserves_decimal = token1.toDecimals(token1_reserves)

        router_name = router.address
        if router_name in self.client.network.routers.values():
            for name, address in self.client.network.routers.items():
                if address == router_name:
                    router_name = name
                    break
        print(f"Swapping {amount_in} {token0.symbol} to {token1.symbol} in {router_name}")

        amount_out_min = amount_in * price * ((Decimal("100") - Decimal(slippage)) / 100)
        amount_out_min_raw = token1.fromDecimals(amount_out_min)

        print(f"Current price {price:.18f} {reference_token.name} * {amount_in} - slippage = {amount_out_min:.18f} " +
              f"{token1.symbol}")

        print("Reserves: ")
        print(f"{token0_reserves_decimal:.5f} {token0.symbol}")
        print(f"{token1_reserves_decimal:.5f} {token1.symbol}")

        balance = token0.balanceOfDecimal(self.client.public_key)
        if balance < amount_in:
            print(f"ERROR account balance {balance:.5f} {token0.symbol} less than {amount_in:.5f} {token0.symbol}")
            return

        if amount_in > token0_reserves:
            print(f"ERROR about to swap {percentage:.2f}% of reserves")
            return
        elif amount_in * Decimal("100") > token0_reserves:
            print(f"Warning about to swap {percentage:.2f}% of reserves")

        # We need to approve first
        tx_hash = self.client.approve(
            token=token0,
            spender=router,
            amount=amount_in_raw,
            approve_amount=amount_in_raw * 2,
            gas_price=gas_price
        )
        if tx_hash:
            self.client.wait_transaction_success(tx_hash)

        # Swap

        sent_tx = router.swap(
            path=[token0, token1],
            amount_in=amount_in_raw,
            amount_out_min=amount_out_min_raw,
            gas_price=gas_price
        )

        url = self.client.network.explorer_tx_url.format(sent_tx)
        print(f"Explorer URL for transaction: {url}")

        self.client.wait_transaction_success(sent_tx)

    def wrap(self, amount: Decimal, gas_price: int = None):
        amount_raw = int(amount * 10 ** self.client.network.native_token_decimals)
        wrapped_token = self.client.get_wrapped_native_token()

        native_balance = self.client.w3.eth.get_balance(self.client.public_key)
        if native_balance < amount_raw:
            print(f"ERROR account balance {native_balance:.5f} less than {amount_raw:.5f} {wrapped_token.symbol}")
            return

        tx = wrapped_token.contract.functions.deposit()
        self.client.test_transaction(tx)
        signed_tx = self.client.sign_transaction(tx, value=amount_raw, gas_price=gas_price, gas_estimate=50000)
        sent_tx = self.client.send_transaction(signed_tx)

        url = self.client.network.explorer_tx_url.format(sent_tx)
        print(f"Explorer URL for transaction: {url}")

        self.client.wait_transaction_success(sent_tx)

    def unwrap(self, amount: Decimal, gas_price: int = None):
        amount_raw = int(amount * 10 ** self.client.network.native_token_decimals)
        wrapped_token = self.client.get_wrapped_native_token()

        token_balance = wrapped_token.balanceOf(self.client.public_key)

        if token_balance < amount_raw:
            print(f"ERROR account balance {token_balance:.5f} {wrapped_token.symbol} less than {amount_raw:.5f}")
            return

        tx = wrapped_token.contract.functions.withdraw(amount_raw)
        self.client.test_transaction(tx)
        # BSC gas estimation is broken, let's use static big enough gas estimate
        signed_tx = self.client.sign_transaction(tx, gas_price=gas_price, gas_estimate=50000)
        sent_tx = self.client.send_transaction(signed_tx)
        url = self.client.network.explorer_tx_url.format(sent_tx)
        print(f"Explorer URL for transaction: {url}")

        self.client.wait_transaction_success(sent_tx)


def get_router_price(router_name, router_address, swapper, token_from, token_to, amount_in):
    try:
        router = router_client.get_router(
            client=swapper.client,
            contract_address=router_address,
            abi_file="PancakeRouterV2"
        )
        price, reference_token, token0_reserves, token1_reserves, percentage = swapper.get_details(
            router=router,
            token_from=token_from,
            token_to=token_to,
            amount_in=amount_in,
        )
        return (router, router_name, price, reference_token, token0_reserves, token1_reserves, percentage)

    except blockchain.exceptions.BlockchainException:
        print(f"No LP pair in {router_name}")


def select_router(router_name, token_from, token_to, amount_in, swapper) -> RouterClient:
    router_address = None
    all_routers = False
    selected_router = None
    if router_name.startswith("0x"):
        router_address = Web3.toChecksumAddress(router_name)
    elif router_name in ["all", "any"]:
        all_routers = True
    else:
        router_address = binance.ROUTERS.get(router_name, None)
        if not router_address:
            print(f"No such router {router_name}")
            sys.exit(1)

    if all_routers:
        print("Checking prices from known routers")
        tasks = []
        values = []

        sell = False
        if token_to in swapper.client.network.tokens.values() and \
                token_from not in swapper.client.network.tokens.values():
            sell = True
        elif token_to in swapper.client.network.tokens.values() and \
                token_from in swapper.client.network.tokens.values():
            print("WARNING: best and worst prices might be upside down, be extra careful...")
            token_to_index = list(swapper.client.network.tokens.values()).index(token_to)
            token_from_index = list(swapper.client.network.tokens.values()).index(token_from)
            if token_to_index < token_from_index:
                sell = True

        with ThreadPoolExecutor(max_workers=10) as executor:
            for router_name, router_address in swapper.client.network.routers.items():
                tasks.append(
                    executor.submit(
                        get_router_price,
                        router_name=router_name,
                        router_address=router_address,
                        swapper=swapper,
                        token_from=token_from,
                        token_to=token_to,
                        amount_in=amount_in,
                    )
                )

            for task in tasks:
                result = task.result()
                if result:
                    values.append(result)

        values = sorted(values, key=lambda x: x[2], reverse=sell)

        print("router               price                              price symbol token0 reserves                " +
              "    token1 reserves                        % of reserves")
        selected_price = None
        for router, router_name, price, reference_token, token0_reserves, token1_reserves, percentage in values:
            if sell:
                if not selected_price or selected_price < price:
                    selected_price = price
                diff = price - selected_price
            else:
                if not selected_price or selected_price > price:
                    selected_price = price
                diff = price - selected_price
            diff_p = diff * Decimal("100") / selected_price
            if not selected_router and percentage < Decimal("100"):
                selected_router = router
            print(f"{router_name:20s} {price:>10.18f} ({diff_p:>+10.5f}%) {reference_token.symbol:10s} " +
                  f"{token0_reserves:>35.18f} {token1_reserves:>35.18f} {percentage:>15.5f}")

        if not selected_router:
            print("failed to find suitable router")
            sys.exit(1)
        print(f"Selected router is {selected_router.address}")

    else:
        selected_router = router_client.get_router(
            client=swapper.client,
            contract_address=router_address,
            abi_file="PancakeRouterV2"
        )

    return selected_router


def swap(swapper, args):

    token_from = None
    token_to = None
    if args.token_from in binance.TOKENS.keys():
        token_from = binance.TOKENS[args.token_from]
    else:
        token_from = Web3.toChecksumAddress(args.token_from)

    if args.token_to in binance.TOKENS.keys():
        token_to = binance.TOKENS[args.token_to]
    else:
        token_to = Web3.toChecksumAddress(args.token_to)

    if token_to == token_from:
        print("token_from must be different from token_to")
        sys.exit(1)

    amount_in = None
    if args.amount == "all":
        amount_in = swapper.get_balance(token_address=token_from)
        print(f"Calculated amount is {amount_in}")
    elif args.amount.endswith("%"):
        amount_percent = Decimal(args.amount[:-1])
        banance = swapper.get_balance(token_address=token_from)
        amount_in = banance * (amount_percent / Decimal("100"))
        print(f"Calculated amount is {amount_in} of {banance}")
    else:
        try:
            amount_in = Decimal(args.amount)
        except ValueError:
            print(f"Invalid amount value {args.amount}")
            sys.exit(1)

    selected_router = select_router(args.router, token_from, token_to, amount_in, swapper)

    swapper.swap_tokens(
        router=selected_router,
        token_from=token_from,
        token_to=token_to,
        amount_in=amount_in,
        gas_price=args.gas_price,
        slippage=args.slippage,
    )


def unwrap(swapper: Swapper, args):
    try:
        amount = Decimal(args.amount)
    except ValueError:
        print(f"Invalid amount value {args.amount}")
        sys.exit(1)
    swapper.unwrap(amount, gas_price=args.gas_price)


def wrap(swapper, args):
    try:
        amount = Decimal(args.amount)
    except ValueError:
        print(f"Invalid amount value {args.amount}")
        sys.exit(1)
    swapper.wrap(amount, gas_price=args.gas_price)


def main():
    parser = argparse.ArgumentParser("Swap tokens")
    parser.add_argument(
        '--keyfile',
        required=True,
        help="Keyfile path"
    )
    parser.add_argument(
        "--network",
        required=True,
        choices=networks.NETWORKS.keys(),
        help="Network to operate on"
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        default=False,
        help="Run in test mode, don't send transactions"
    )
    parser.add_argument(
        "--gas-price",
        default=None,
        type=int,
        help="Gas price in gwei"
    )

    subparsers = parser.add_subparsers()
    swap_parser = subparsers.add_parser("swap")

    swap_parser.add_argument(
        "--router",
        required=False,
        help="Router to use, either address or name of the known router, special value any will find lowest price",
    )
    swap_parser.add_argument(
        "--slippage",
        default=3,
        type=int,
        help="slippage percent"
    )
    swap_parser.add_argument(
        "token_from",
        help="ERC-20 token address"
    )
    swap_parser.add_argument(
        "token_to",
        help="Target address"
    )
    swap_parser.add_argument(
        "amount",
        type=str,
        help="Amount token_from to swap, all means whole address balance, 10% is 10% of current balance"
    )
    swap_parser.set_defaults(func=swap)

    wrap_parser = subparsers.add_parser("wrap")
    wrap_parser.add_argument(
        "amount",
        type=str,
        help="Amount to wrap"
    )
    wrap_parser.set_defaults(func=wrap)

    unwrap_parser = subparsers.add_parser("unwrap")
    unwrap_parser.add_argument(
        "amount",
        type=str,
        help="Amount to unwrap"
    )
    unwrap_parser.set_defaults(func=unwrap)

    args = parser.parse_args()

    privkey, pubkey = keyutils.get_keyfile(args.keyfile)

    swapper = Swapper(
        private_key=privkey,
        public_key=pubkey,
        test_mode=args.test_mode,
        network=networks.get_network_by_name(args.network),

    )

    args.func(swapper, args)


if __name__ == '__main__':
    main()
