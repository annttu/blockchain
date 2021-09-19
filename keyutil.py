#!/usr/bin/env python3
import getpass
import os
import sys

from blockchain import keyutils

import argparse


def create_keyfile(args):
    keyfile = args.keyfile

    if os.path.exists(keyfile) is True:
        print(f"Keyfile \"{keyfile}\" already exist")
        sys.exit(1)

    if args.generate:
        account = keyutils.create_account()
        private_key = account.key
        print("Account address {}".format(account.address))
    else:
        private_key = getpass.getpass("Private key: ")

    password = getpass.getpass("Export password: ")

    keyutils.save_keyfile(private_key=private_key, keyfile=keyfile, password=password)


def show_info(args):
    keyfile = args.keyfile

    if os.path.isfile(keyfile) is not True:
        print(f"Keyfile \"{keyfile}\" does not exist")
        sys.exit(1)

    private_key, public_key = keyutils.get_keyfile(keyfile=keyfile)

    print(f"Public key is: {public_key}")
    if args.private_key:
        print(f"Private key is: {private_key.hex()}")


def main():

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--generate", action="store_true", default=False)
    create_parser.add_argument("keyfile", help="Keyfile path")
    create_parser.set_defaults(func=create_keyfile)

    info_parser = subparsers.add_parser("info")
    info_parser.add_argument("--private-key", action="store_true", default=False, help="Show private key")
    info_parser.add_argument("keyfile", help="Keyfile path")
    info_parser.set_defaults(func=show_info)

    args = parser.parse_args()

    args.func(args)


if __name__ == '__main__':
    main()
