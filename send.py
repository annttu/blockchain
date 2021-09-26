#!/usr/bin/env python3
from decimal import Decimal

from blockchain import client, keyutils, networks
import argparse


class Sender(object):

    def __init__(self, **kwargs):
        self.client = client.Client(**kwargs)

    def send_native(self, amount, to_address, gas_price: int = None):
        amount_raw = self.client.w3.toWei(amount, 'ether')

        signed = self.client.send_native_token(amount=amount_raw, to_address=to_address, gas_price=gas_price)
        tx_hash = self.client.send_transaction(signed)
        print("TX hash: {}".format(tx_hash))
        self.client.wait_transaction_success(tx_hash=tx_hash)
        print("Transaction successfully sent")

    def send_token(self, token_address, amount, to_address, gas_price: int = None):
        token = self.client.get_token(token_address)
        amount_raw = token.fromDecimals(amount)

        signed_tx = self.client.send_token(token=token, amount=amount_raw, to_address=to_address, gas_price=gas_price)

        tx_hash = self.client.send_transaction(signed_tx)
        print("TX hash: {}".format(tx_hash))
        self.client.wait_transaction_success(tx_hash=tx_hash)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keyfile', required=True, help="Keyfile path")
    parser.add_argument("--network", required=True, choices=networks.NETWORKS.keys(), help="Network to operate on")
    parser.add_argument(
        "--test-mode",
        action="store_true",
        default=False,
        help="Run in test mode, don't send transactions"
    )
    parser.add_argument("--gas-price", default=None, type=int, help="Gas price in gwei")
    parser.add_argument("--token", default=None, help="ERC-20 token address, default is network native token")
    parser.add_argument("to", help="Target address")
    parser.add_argument("amount", type=Decimal, help="Amount to send")

    args = parser.parse_args()

    privkey, pubkey = keyutils.get_keyfile(args.keyfile)

    sender = Sender(
        private_key=privkey,
        public_key=pubkey,
        test_mode=args.test_mode,
        network=networks.get_network_by_name(args.network)
    )

    if args.token:
        sender.send_token(
            token_address=args.token,
            amount=args.amount,
            to_address=args.to,
            gas_price=args.gas_price
        )
    else:
        sender.send_native(
            amount=args.amount,
            to_address=args.to,
            gas_price=args.gas_price
        )


if __name__ == '__main__':
    main()
