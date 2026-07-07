import asyncio

import httpx


async def fetch_backend_health(
    backend_url: str,
    *,
    max_attempts: int = 12,
    retry_delay_seconds: float = 5.0,
) -> dict[str, object]:
    max_attempts = max(max_attempts, 1)
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.get(f"{backend_url.rstrip('/')}/health")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == max_attempts:
                    break
                await asyncio.sleep(retry_delay_seconds)

    raise RuntimeError(
        f"Backend health endpoint was unavailable after {max_attempts} attempts"
    ) from last_error
