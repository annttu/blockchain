from typing import Optional, Any, Dict

import aiohttp
from eth_typing import URI
from web3 import AsyncHTTPProvider
from web3._utils.http import construct_user_agent
from web3.types import RPCEndpoint, RPCResponse


async def async_make_post_request(
    endpoint_uri: URI, data: bytes, *args: Any, connector: aiohttp.TCPConnector,  **kwargs: Any
) -> bytes:
    kwargs.setdefault('timeout', aiohttp.ClientTimeout(10))
    async with aiohttp.ClientSession(
            connector=connector,
            raise_for_status=True,
            connector_owner=False
    ) as session:
        async with session.post(endpoint_uri,
                                data=data,
                                *args,
                                **kwargs) as response:
            return await response.read()


class PooledAsyncHTTPProvider(AsyncHTTPProvider):
    """
    Pooled version of AsyncHTTPProvider
    """

    def __init__(self, *args, connector_kwargs: Optional[Any] = None, **kwargs):
        super().__init__(*args, **kwargs)
        if not connector_kwargs:
            connector_kwargs = {}
        self._connector = aiohttp.TCPConnector(**connector_kwargs)

    def get_request_headers(self) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'User-Agent': construct_user_agent(str(self)),
        }

    ## Rewrite http provider to use pool
    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        self.logger.debug("Making request HTTP. URI: %s, Method: %s",
                          self.endpoint_uri, method)
        request_data = self.encode_rpc_request(method, params)

        raw_response = await async_make_post_request(
            self.endpoint_uri,
            request_data,
            connector=self._connector,
            **self.get_request_kwargs()
        )
        response = self.decode_rpc_response(raw_response)
        self.logger.debug("Getting response HTTP. URI: %s, "
                          "Method: %s, Response: %s",
                          self.endpoint_uri, method, response)
        return response

    def __del__(self):
        if self._connector.closed is False:
            self._connector.close()

    def __str__(self):
        return "PooledAsyncHTTPProvider"

    def __repr__(self):
        return "PooledAsyncHTTPProvider"
