#!/usr/bin/env python3
import json
import logging

import web3
from eth_utils import encode_hex, function_abi_to_4byte_selector
from web3 import Web3

from blockchain import client, keyutils, networks
from blockchain.contract import Contract, read_abi_file

import argparse


def find_function(args):
    w3 = web3.Web3()

    # Add
    c = Contract(w3=w3, address=networks.binance.BURN, abi=read_abi_file(args.contract_json))

    # Get by selector
    print(c.contract.get_function_by_selector(args.selector))


def find_selector(args):
    w3 = web3.Web3()

    # Add
    c = Contract(w3=w3, address=networks.binance.BURN, abi=read_abi_file(args.contract_json))

    # Get by selector
    function = c.contract.get_function_by_name(args.function)
    print(encode_hex(function_abi_to_4byte_selector(function.abi)))
    print("{}({})".format(function.abi["name"], ','.join([x["type"] for x in function.abi["inputs"]])))


def map_function_args(f, call_args):
    mapped_args = {}
    list_args = []
    i = 0
    for f_input in f["inputs"]:
        name = f_input["name"]

        if len(call_args) <= i:
            print("ERROR: invalid amount of args")
            break
        value = call_args[i]
        if f_input["type"] == "address":
            value = Web3.toChecksumAddress(value)
        elif f_input["type"] == "uint256":
            value = int(value)
        elif f_input["type"] == "bytes":
            value = value.encode("utf-8")
        else:
            raise ValueError("Unknown type {}".format(f_input["type"]))
        mapped_args[name] = value
        list_args.append(value)
        i += 1

    return list_args, mapped_args


def get_function_and_args(my_client, address, contract_json, selector, function_args=None):

    contract = Contract(
        my_client.w3,
        my_client.w3.toChecksumAddress(address),
        abi=read_abi_file(contract_json)
    )

    call_args = []
    if function_args is not None:
        call_args = function_args

    f = contract.contract.get_function_by_name(selector)
    list_args, mapped_args = map_function_args(f.abi, call_args)

    return f, list_args


def call_function(args):
    public_key = networks.binance.BURN
    if args.public_key:
        public_key = args.public_key

    my_client = client.Client(
        public_key=public_key,
        private_key="",
        network=networks.get_network_by_name(args.network),
        test_mode=True
    )

    f, list_args = get_function_and_args(
        my_client=my_client,
        address=args.address,
        contract_json=args.contract_json,
        selector=args.selector,
        function_args=args.args
    )

    print(f"Calling function: {f} with args {list_args}")
    tx = f(*list_args)
    result = tx.call({'from': my_client.w3.toChecksumAddress(public_key)})
    print(f"Result: {result}")


def create_transaction(args):
    private_key, public_key = keyutils.get_keyfile(args.keyfile)
    my_client = client.Client(
        public_key=public_key,
        private_key=private_key,
        network=networks.get_network_by_name(args.network),
        test_mode=args.test_mode
    )
    f, list_args = get_function_and_args(
        my_client=my_client,
        address=args.address,
        contract_json=args.contract_json,
        selector=args.selector,
        function_args=args.args
    )

    print(f"Calling function: {f} with args {list_args}")
    tx = f(*list_args)
    print("Result: {}".format(tx.call({'from': my_client.w3.toChecksumAddress(public_key)})))
    signed_tx = my_client.sign_transaction(tx, gas_price=my_client.get_gas_price())
    print(signed_tx)
    tx_hash = my_client.send_transaction(signed_tx)
    my_client.wait_transaction_success(tx_hash)


def call_raw(args):
    public_key = networks.binance.BURN
    if args.public_key:
        public_key = args.public_key

    my_client = client.Client(
        public_key=public_key,
        private_key="",
        network=networks.get_network_by_name(args.network),
        test_mode=True
    )

    tx = {
        'value': int(args.value),
        'gas': args.gas,
        'to': my_client.w3.toChecksumAddress(args.address),
        'data': args.data
    }

    result = my_client.w3.eth.call(tx)
    print(f"Result raw: {result}")
    print(f"Result hex: {result.hex()}")
    if len(result.hex()) < 67:
        print(f"Result int: {int(result.hex(), 16)}")
    print(f"Result str: {result.decode('utf-8', errors='replace')}")
    return result


def storage_at(args):
    my_client = client.Client(
        public_key=networks.binance.BURN,
        private_key="",
        network=networks.get_network_by_name(args.network),
        test_mode=True
    )
    print(my_client.w3.eth.get_storage_at(my_client.w3.toChecksumAddress(args.address), int(args.at)).hex())


def deploy(args):
    private_key, public_key = keyutils.get_keyfile(args.keyfile)
    my_client = client.Client(
        public_key=public_key,
        private_key=private_key,
        network=networks.get_network_by_name(args.network),
        test_mode=False
    )
    with open(args.bytecode) as f:
        code = f.read().strip()
        if code.startswith("0x"):
            code = code[2:]
        contract_bytecode = bytes.fromhex(code)
    with open(args.abi) as f:
        contract_abi = f.read()
    c = my_client.w3.eth.contract(abi=contract_abi, bytecode=contract_bytecode)

    constructor_f = json.loads(contract_abi)[0]
    assert constructor_f["type"] == "constructor"

    list_args, mapped_args = map_function_args(constructor_f, args.args)

    deploy_transaction = c.constructor(*list_args)

    gas_estimate = deploy_transaction.estimateGas()
    signed_tx = my_client.sign_transaction(deploy_transaction, gas_price=args.gas_price,
                                           gas_estimate=gas_estimate + 10000)
    tx_hash = my_client.send_transaction(signed_tx)
    my_client.wait_transaction_success(tx_hash)
    address = my_client.w3.eth.get_transaction_receipt(tx_hash)["contractAddress"]
    print(f"Contract address is {address}")


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True
    find_function_parser = subparsers.add_parser("find-function")
    find_function_parser.add_argument("contract_json")
    find_function_parser.add_argument("selector")
    find_function_parser.set_defaults(func=find_function)

    find_selector_parser = subparsers.add_parser("find-selector")
    find_selector_parser.add_argument("contract_json")
    find_selector_parser.add_argument("function")
    find_selector_parser.set_defaults(func=find_selector)

    call_function_parser = subparsers.add_parser("call")
    call_function_parser.add_argument("network", choices=networks.NETWORKS.keys())
    call_function_parser.add_argument("contract_json")
    call_function_parser.add_argument("address")
    call_function_parser.add_argument("selector")
    group = call_function_parser.add_mutually_exclusive_group()
    group.add_argument("--public-key", default=None, help="Public key to use with call")
    group.add_argument("--keyfile", default=None, help="Keyfile path")
    call_function_parser.add_argument("args", nargs="*", type=str, help="Optional function arguments")
    call_function_parser.set_defaults(func=call_function)

    call_raw_parser = subparsers.add_parser("call-raw")
    call_raw_parser.add_argument("network", choices=networks.NETWORKS.keys())
    call_raw_parser.add_argument("address")
    call_raw_parser.add_argument("data")
    group = call_raw_parser.add_mutually_exclusive_group()
    group.add_argument("--public-key", default=None, help="Public key to use with call")
    group.add_argument("--keyfile", default=None, help="Keyfile path")
    call_raw_parser.add_argument("--gas", default=2500000, type=int, help="Gas amount")
    call_raw_parser.add_argument("--value", type=int, default=0)
    call_raw_parser.set_defaults(func=call_raw)

    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--test-mode", default=False, action="store_true")
    execute_parser.add_argument("--keyfile", required=True, help="Keyfile path")
    execute_parser.add_argument("network", choices=networks.NETWORKS.keys())
    execute_parser.add_argument("contract_json")
    execute_parser.add_argument("address")
    execute_parser.add_argument("selector")
    execute_parser.add_argument("args", nargs="*", type=str, help="Optional function arguments")
    execute_parser.set_defaults(func=create_transaction)

    storage_parser = subparsers.add_parser("storage")
    storage_parser.add_argument("network", choices=networks.NETWORKS.keys())
    storage_parser.add_argument("address")
    storage_parser.add_argument("at")
    storage_parser.set_defaults(func=storage_at)

    deploy_parser = subparsers.add_parser("deploy")
    # execute_parser.add_argument("--test-mode", default=False, action="store_true")
    deploy_parser.add_argument("--keyfile", required=True, help="Keyfile path")
    deploy_parser.add_argument("--gas-price", type=int, default=5)
    deploy_parser.add_argument("network", choices=networks.NETWORKS.keys())
    deploy_parser.add_argument("bytecode")
    deploy_parser.add_argument("abi")
    deploy_parser.add_argument("args", nargs="*", type=str, help="Optional function arguments")
    deploy_parser.set_defaults(func=deploy)


args = parser.parse_args()

    args.func(args)


if __name__ == '__main__':
    main()
