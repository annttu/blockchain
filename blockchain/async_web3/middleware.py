"""
Async versions of Web3py middlewares
"""

from typing import Optional, Any, Callable, Coroutine

from web3 import Web3
from web3._utils.rpc_abi import RPC
from web3.middleware.geth_poa import is_not_null, geth_poa_cleanup
from web3.types import RPCEndpoint, RPCResponse, Formatters, Middleware, FormattersDict

from eth_utils.toolz import (
    assoc,
    merge,
)


async def async_apply_formatters(
    make_request: Callable[[RPCEndpoint, Any], Coroutine[RPCResponse, Any, Any]],
    request_formatters: Formatters,
    result_formatters: Formatters,
    error_formatters: Formatters,
) -> Callable[[RPCEndpoint, Any], Coroutine[RPCResponse, Any, Any]]:

    async def callback(method: RPCEndpoint, params: Any):
        if method in request_formatters:
            formatter = request_formatters[method]
            formatted_params = await formatter(params)
            response = await make_request(method, formatted_params)
        else:
            response = await make_request(method, params)

        if "result" in response and method in result_formatters:
            formatter = result_formatters[method]
            formatted_response = assoc(
                response,
                "result",
                formatter(response["result"]),
            )
            return formatted_response
        elif "error" in response and method in error_formatters:
            formatter = error_formatters[method]
            formatted_response = assoc(
                response,
                "error",
                formatter(response["error"]),
            )
            return formatted_response
        else:
            return response

    return callback


def async_apply_formatter_if(
    condition: Callable[..., bool],
        formatter: Callable[..., Any]
) -> Any:
    def callback(value: Any):
        if condition(value):
            return formatter(value)
        else:
            return value
    return callback


def async_construct_web3_formatting_middleware(
    web3_formatters_builder: Callable[["Web3"], FormattersDict]
) -> Middleware:
    async def formatter_middleware(
        make_request: Callable[[RPCEndpoint, Any], Any], w3: "Web3"
    ) -> Callable[[RPCEndpoint, Any], Coroutine[RPCResponse, Any, Any]]:
        formatters = merge(
            {
                "request_formatters": {},
                "result_formatters": {},
                "error_formatters": {},
            },
            web3_formatters_builder(w3),
        )
        return await async_apply_formatters(make_request=make_request, **formatters)

    return formatter_middleware


def async_construct_formatting_middleware(
    request_formatters: Optional[Formatters] = None,
    result_formatters: Optional[Formatters] = None,
    error_formatters: Optional[Formatters] = None
) -> Middleware:
    def ignore_web3_in_standard_formatters(
        w3: "Web3",
    ) -> FormattersDict:
        return FormattersDict(
            request_formatters=request_formatters or {},
            result_formatters=result_formatters or {},
            error_formatters=error_formatters or {},
        )

    return async_construct_web3_formatting_middleware(ignore_web3_in_standard_formatters)


async_geth_poa_middleware = async_construct_formatting_middleware(
        result_formatters={
            RPC.eth_getBlockByHash: async_apply_formatter_if(is_not_null, geth_poa_cleanup),
            RPC.eth_getBlockByNumber: async_apply_formatter_if(is_not_null, geth_poa_cleanup),
        },
    )
