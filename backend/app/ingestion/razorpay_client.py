from abc import ABC, abstractmethod
import time
import httpx
from typing import Any
import asyncio
import os

class RazorpayClientInterface(ABC):
    @abstractmethod
    async def fetch_payments(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]: ...
    
    @abstractmethod
    async def fetch_orders(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]: ...
    
    @abstractmethod
    async def fetch_settlements(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]: ...
    
    @abstractmethod
    async def fetch_refunds(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]: ...
    
    @abstractmethod
    async def fetch_disputes(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]: ...


class MockRazorpayClient(RazorpayClientInterface):
    """Mock implementation returning realistic test data for Razorpay."""
    
    async def fetch_payments(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        now = int(time.time())
        return [
            {
                "id": f"pay_mock{i}",
                "entity": "payment",
                "amount": 100000,
                "currency": "INR",
                "status": "captured",
                "order_id": f"order_mock{i}",
                "method": "card",
                "amount_refunded": 0,
                "refund_status": None,
                "captured": True,
                "email": f"customer{i}@example.com",
                "contact": "+919999999999",
                "fee": 2000,
                "tax": 360,
                "created_at": now - i * 3600
            }
            for i in range(min(5, count))
        ]

    async def fetch_orders(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        now = int(time.time())
        return [
            {
                "id": f"order_mock{i}",
                "entity": "order",
                "amount": 100000,
                "amount_paid": 100000,
                "amount_due": 0,
                "currency": "INR",
                "receipt": f"receipt_{i}",
                "status": "paid",
                "attempts": 1,
                "created_at": now - i * 3600
            }
            for i in range(min(5, count))
        ]

    async def fetch_settlements(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        now = int(time.time())
        return [
            {
                "id": f"setl_mock{i}",
                "entity": "settlement",
                "amount": 97640,
                "status": "processed",
                "fees": 2000,
                "tax": 360,
                "utr": f"UTR_mock_{i}",
                "created_at": now - i * 86400
            }
            for i in range(min(5, count))
        ]

    async def fetch_refunds(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        now = int(time.time())
        return [
            {
                "id": f"rfnd_mock{i}",
                "entity": "refund",
                "amount": 10000,
                "currency": "INR",
                "payment_id": f"pay_mock{i}",
                "status": "processed",
                "speed_processed": "normal",
                "created_at": now - i * 3600
            }
            for i in range(min(5, count))
        ]

    async def fetch_disputes(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        now = int(time.time())
        return [
            {
                "id": f"disp_mock{i}",
                "entity": "dispute",
                "payment_id": f"pay_mock{i}",
                "amount": 100000,
                "currency": "INR",
                "amount_deducted": 100000,
                "reason_code": "fraudulent",
                "status": "open",
                "created_at": now - i * 86400
            }
            for i in range(min(5, count))
        ]

class SandboxRazorpayClient(RazorpayClientInterface):
    """Real Razorpay API client using httpx."""
    
    def __init__(self, key_id: str | None = None, key_secret: str | None = None):
        self.key_id = key_id or os.environ.get("RAZORPAY_KEY_ID")
        self.key_secret = key_secret or os.environ.get("RAZORPAY_KEY_SECRET")
        if not self.key_id or not self.key_secret:
            raise ValueError("Razorpay API keys are required for Sandbox client.")
        
        self.base_url = "https://api.razorpay.com/v1/"
        self.auth = (self.key_id, self.key_secret)

    async def _request(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(auth=self.auth, base_url=self.base_url) as client:
            for attempt in range(3):
                response = await client.get(endpoint, params=params)
                if response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                data = response.json()
                return data.get("items", [])
            return []

    async def fetch_payments(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        params = {"count": count}
        if from_timestamp: params["from"] = from_timestamp
        if to_timestamp: params["to"] = to_timestamp
        return await self._request("payments", params)
        
    async def fetch_orders(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        params = {"count": count}
        if from_timestamp: params["from"] = from_timestamp
        if to_timestamp: params["to"] = to_timestamp
        return await self._request("orders", params)
        
    async def fetch_settlements(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        params = {"count": count}
        if from_timestamp: params["from"] = from_timestamp
        if to_timestamp: params["to"] = to_timestamp
        return await self._request("settlements", params)

    async def fetch_refunds(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        params = {"count": count}
        if from_timestamp: params["from"] = from_timestamp
        if to_timestamp: params["to"] = to_timestamp
        return await self._request("refunds", params)

    async def fetch_disputes(self, from_timestamp: int | None = None, to_timestamp: int | None = None, count: int = 100) -> list[dict[str, Any]]:
        params = {"count": count}
        if from_timestamp: params["from"] = from_timestamp
        if to_timestamp: params["to"] = to_timestamp
        return await self._request("disputes", params)

def get_razorpay_client(mode: str = "mock") -> RazorpayClientInterface:
    if mode == "sandbox" or mode == "live":
        return SandboxRazorpayClient()
    return MockRazorpayClient()
