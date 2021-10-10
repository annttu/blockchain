
CHAIN_ID = 56
DEFAULT_PROVIDER = "https://bsc-dataseed.binance.org/"


PANCAKEROUTERV2 = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
PANCAKEROUTERV1 = "0x05fF2B0DB69458A0750badebc4f9e13aDd608C7F"
CAFESWAPROUTERV2 = "0x933DAea3a5995Fb94b14A7696a5F3ffD7B1E385A"
SAFESWAPROUTER = "0xE804f3C3E6DdA8159055428848fE6f2a91c2b9AF"
SHIBANCEROUTER = "0xA1fDB322Ab5fE4dF90099E6f514B9819AEaCA8Cf"
BABYROUTER = "0x325E343f1dE602396E256B67eFd1F61C3A6B38Bd"
PANTHERSWAPROUTER = "0x24f7C33ae5f77e2A9ECeed7EA858B4ca2fa1B7eC"
APEROUTER = "0xC0788A3aD43d79aa53B09c2EaCc313A787d1d607"
MDEXROUTER = "0x7DAe51BD3E3376B8c7c4900E9107f12Be3AF1bA8"
JETSWAPROUTER = "0xA8583a8C53A08EbCD6cB494B10Ce48C86F53Be75"
SWAPROUTER = "0xE9C7650b97712C0Ec958FF270FBF4189fB99C071"

PANCAKELP = "0x8195143df00e94F320F3f60C48D5ED97A6bFAbfc"

WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT = "0x55d398326f99059fF775485246999027B3197955"
BUSD = "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"
USDC = "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"
BURN = "0x0000000000000000000000000000000000000000"


ROUTERS = {
    "PancakeRouterV2": PANCAKEROUTERV2,
    "PancakeRouterV1": PANCAKEROUTERV1,
    "CafeSwapRouterV2": CAFESWAPROUTERV2,
    "SafeswapRouter": SAFESWAPROUTER,
    "ShibanceRouter": SHIBANCEROUTER,
    "BabyRouter": BABYROUTER,
    "PantherSwapRouter": PANTHERSWAPROUTER,
    "ApeRouter": APEROUTER,
    "MDEXRouter": MDEXROUTER,
    "JetswapRouter": JETSWAPROUTER,
    "SwapRouter": SWAPROUTER,
}

# List of token to use in price calculations as base token
TOKENS = {
    "WBNB": WBNB,
    "USDT": USDT,
    "BUSD": BUSD,
    "USDC": USDC,
}

WRAPPED_NATIVE_TOKEN = WBNB

EXPLORER_TX_URL = "https://bscscan.com/tx/{}"

NATIVE_TOKEN_DECIMALS = 18
