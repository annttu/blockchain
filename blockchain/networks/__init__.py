from . import binance
from . import kardiachain
import os

from .. import configuration


class Network(object):
    def __init__(
            self,
            provider,
            chain_id,
            routers,
            tokens,
            wrapped_native_token,
            explorer_tx_url,
            native_token_decimals,
    ):
        self.provider = provider
        self.chain_id = chain_id
        self.tokens = tokens
        self.routers = routers
        self.wrapped_native_token = wrapped_native_token
        self.explorer_tx_url = explorer_tx_url
        self.native_token_decimals = native_token_decimals


KARDIACHAIN = "kardiachain"
BINANCE = "binance"


_NETWORKS = {
    BINANCE: binance,
    KARDIACHAIN: kardiachain
}

NETWORKS = {
    key: Network(
        provider=configuration.get_variable("{}_provider".format(key), value.DEFAULT_PROVIDER),
        chain_id=value.CHAIN_ID,
        tokens=value.TOKENS,
        routers=value.ROUTERS,
        wrapped_native_token=value.WRAPPED_NATIVE_TOKEN,
        explorer_tx_url=value.EXPLORER_TX_URL,
        native_token_decimals=value.NATIVE_TOKEN_DECIMALS,
    ) for key, value in _NETWORKS.items()
}


def get_network_by_name(name):
    if name in NETWORKS.keys():
        return NETWORKS[name]
    else:
        raise ValueError(f"Unknown network {name}")


__all__ = [
    Network,
    binance,
    kardiachain,
    get_network_by_name,
    NETWORKS,
]