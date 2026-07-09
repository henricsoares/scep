import httpx


async def fetch_backend_health(backend_url: str) -> dict[str, object]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{backend_url.rstrip('/')}/health")
        response.raise_for_status()
        return response.json()
