Blockchain utils
====

These utils are in early development phase. USE AT YOUR OWN RISK!


Install requirements
---

```bash
python3 -m virtualenv env --python=python3
. env/bin/activate
pip install -r requirements.txt
```

Keyfile
---

Keyfile is encrypted using export password.

Create new keyfile using `./keyutil.py create --generate ~/.key.json`.

Omit --generate to use existing private key.

### Usage

```bash
./keyutil.py info [-h] [--private-key] keyfile

positional arguments:
  keyfile        Keyfile path

optional arguments:
  -h, --help     show this help message and exit
  --private-key  Show private key

./keyutil.py create [-h] [--generate] keyfile

positional arguments:
  keyfile     Keyfile path

optional arguments:
  -h, --help  show this help message and exit
  --generate
```

Send
---

Send Native and ERC-20 tokens.

### Usage

```bash
usage: send.py [-h] --keyfile KEYFILE --network {binance,kai} [--test-mode] [--gas-price GAS_PRICE] [--token TOKEN] to amount

positional arguments:
  to                    Target address
  amount                Amount to send

optional arguments:
  -h, --help            show this help message and exit
  --keyfile KEYFILE     Keyfile path
  --network {binance,kai}
                        Network to operate on
  --test-mode           Run in test mode, don\'t send transactions
  --gas-price GAS_PRICE
                        Gas price in gwei
  --token TOKEN         ERC-20 token address, default is network native token
```

Swap
---

Swap tokens in exchange

### Usage

```bash

usage: Swap tokens [-h] --keyfile KEYFILE --network {binance,kardiachain} [--router ROUTER] [--test-mode] [--gas-price GAS_PRICE] [--slippage SLIPPAGE] token_from token_to amount

positional arguments:
  token_from            ERC-20 token address, default is network native token
  token_to              Target address
  amount                Amount token_from to swap

optional arguments:
  -h, --help            show this help message and exit
  --keyfile KEYFILE     Keyfile path
  --network {binance,kardiachain}
                        Network to operate on
  --router ROUTER       Router (exchange) to use
  --test-mode           Run in test mode, don\'t send transactions
  --gas-price GAS_PRICE Gas price in gwei
  --slippage SLIPPAGE   slippage percent
```


License
---

MIT License

Copyright © 2021 Annttu

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the “Software”), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.