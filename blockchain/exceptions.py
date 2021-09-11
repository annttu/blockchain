class BlockchainException(Exception):
    pass


class ContractLogicError(BlockchainException):
    pass


class NoBalanceException(BlockchainException):
    pass


class NotFoundException(BlockchainException):
    pass
