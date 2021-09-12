import getpass
import json
import web3
import web3.eth
import os

from blockchain import configuration


class InvalidPasswordException(Exception):
    pass


def read_keyfile(keyfile, password):
    with open(keyfile, 'r') as f:
        encrypted_key = json.loads(f.read())
        w3 = web3.Web3()
        private_key = w3.eth.account.decrypt(encrypted_key, password)

    account = w3.eth.account.from_key(private_key)
    return account.key, account.address


def save_keyfile(private_key, keyfile, password):
    with open(keyfile, 'w') as f:
        w3 = web3.Web3()
        encrypted_key = w3.eth.account.encrypt(private_key, password)
        f.write(json.dumps(encrypted_key))


def create_account():
    w3 = web3.Web3()
    account = w3.eth.account.create()
    return account


def get_keyfile(keyfile):
    if not os.path.isfile(keyfile):
        raise RuntimeError("File {} does not exists".format(keyfile))
    password = configuration.get_variable("password", None)
    if not password:
        password = getpass.getpass(prompt="Private key password: ")
    try:
        return read_keyfile(keyfile, password=password)
    except ValueError as exc:
        if "MAC mismatch" in str(exc):
            print("Invalid password provided via environment variable")
            password = getpass.getpass(prompt="Private key password: ")
            return read_keyfile(keyfile, password=password)
        raise
