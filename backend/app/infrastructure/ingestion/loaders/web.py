import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

# runtime imports
from app.core.quotas import MAX_CRAWL_PAGES
from app.infrastructure.ingestion.base import Document
from app.infrastructure.ingestion.loaders.base import BaseLoader

logger = logging.getLogger(__name__)

_HREF_RE = re.compile(r'href=["\']([^"\'#?][^"\']*)["\']')


class WebLoader(BaseLoader):
    async def load(self, url_or_path: str) -> list[Document]:
        base_domain = urlparse(url_or_path).netloc
        visited: set[str] = set()
        queue = [url_or_path]
        documents: list[Document] = []

        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            while queue and len(visited) < MAX_CRAWL_PAGES:
                url = queue.pop(0)
                if url in visited:
                    continue
                visited.add(url)

                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    html = resp.text
                    text = trafilatura.extract(
                        html, include_links=False, include_images=False
                    )
                    if text and text.strip():
                        documents.append(
                            Document(
                                text=text.strip(),
                                metadata={"source_type": "web", "url": url},
                            )
                        )
                    # Enqueue same-domain links
                    for href in _HREF_RE.findall(html):
                        if href.startswith("http"):
                            candidate = href
                        elif href.startswith("/"):
                            candidate = urljoin(url, href)
                        else:
                            continue
                        if (
                            urlparse(candidate).netloc == base_domain
                            and candidate not in visited
                        ):
                            queue.append(candidate)
                except Exception:
                    continue

        logger.info(f"WebLoader: {len(documents)} pages loaded from {url_or_path}")
        return documents
