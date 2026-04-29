import logging

import fitz  # PyMuPDF
import httpx

# runtime imports
from app.infrastructure.ingestion.base import Document
from app.infrastructure.ingestion.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class PDFLoader(BaseLoader):
    async def load(self, url_or_path: str) -> list[Document]:
        if url_or_path.startswith("http"):
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(url_or_path)
                resp.raise_for_status()
                pdf_doc = fitz.open(stream=resp.content, filetype="pdf")
        else:
            pdf_doc = fitz.open(url_or_path)

        documents: list[Document] = []
        try:
            for page_num in range(len(pdf_doc)):
                text = pdf_doc[page_num].get_text().strip()
                if text:
                    documents.append(
                        Document(
                            text=text,
                            metadata={
                                "source_type": "pdf",
                                "page_num": page_num + 1,
                                "url": url_or_path if url_or_path.startswith("http") else None,
                            },
                        )
                    )
        finally:
            pdf_doc.close()

        logger.info(f"PDFLoader: {len(documents)} pages loaded")
        return documents
