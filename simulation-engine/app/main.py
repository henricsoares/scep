import asyncio
import logging

from app.clients.backend import fetch_backend_health
from app.core.config import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run() -> None:
    settings = Settings()
    health = await fetch_backend_health(settings.backend_url)
    logger.info("Connected to backend health endpoint: %s", health)


if __name__ == "__main__":
    asyncio.run(run())
