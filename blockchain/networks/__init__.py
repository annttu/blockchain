from . import binance
from . import kardiachain


class Network(object):
    def __init__(self, provider, chain_id, routers, tokens):
        self.provider = provider
        self.chain_id = chain_id
        self.tokens = tokens
        self.routers = routers


KARDIACHAIN = "kardiachain"
BINANCE = "binance"


_NETWORKS = {
    BINANCE: binance,
    KARDIACHAIN: kardiachain
}

NETWORKS = {
    key: Network(
        provider=value.DEFAULT_PROVIDER,
        chain_id=value.CHAIN_ID,
        tokens=value.TOKENS,
        routers=value.ROUTERS,
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