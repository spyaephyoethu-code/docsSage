import logging

import httpx

# runtime imports
from app.infrastructure.ingestion.base import Document
from app.infrastructure.ingestion.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class TextLoader(BaseLoader):
    async def load(self, url_or_path: str) -> list[Document]:
        if url_or_path.startswith("http"):
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(url_or_path)
                resp.raise_for_status()
                text = resp.text
        else:
            text = open(url_or_path, encoding="utf-8", errors="ignore").read()

        text = text.strip()
        if not text:
            return []

        logger.info("TextLoader: loaded 1 document")
        return [Document(text=text, metadata={"source_type": "text", "url": url_or_path})]
