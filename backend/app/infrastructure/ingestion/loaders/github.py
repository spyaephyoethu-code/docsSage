import logging
import tempfile
from pathlib import Path

import git

# runtime imports
from app.infrastructure.ingestion.base import Document
from app.infrastructure.ingestion.loaders.base import BaseLoader

logger = logging.getLogger(__name__)

_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".rst", ".txt",
    ".yaml", ".yml", ".json", ".html", ".css", ".java", ".go",
    ".rb", ".php", ".cpp", ".c", ".h", ".rs", ".swift", ".kt",
    ".toml", ".ini", ".cfg", ".sh", ".bash",
}
_MAX_FILE_BYTES = 1 * 1024 * 1024  # 1 MB per file
_MAX_REPO_MB = 100


class GitHubLoader(BaseLoader):
    async def load(self, url_or_path: str) -> list[Document]:
        clone_url = url_or_path.rstrip("/")
        if not clone_url.endswith(".git"):
            clone_url += ".git"

        documents: list[Document] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            logger.info(f"Cloning {clone_url} into {tmpdir}")
            git.Repo.clone_from(clone_url, tmpdir, depth=1, single_branch=True)

            repo_size_mb = sum(
                f.stat().st_size for f in Path(tmpdir).rglob("*") if f.is_file()
            ) / (1024 * 1024)
            if repo_size_mb > _MAX_REPO_MB:
                raise ValueError(
                    f"Repo is {repo_size_mb:.0f} MB — exceeds {_MAX_REPO_MB} MB limit"
                )

            for filepath in Path(tmpdir).rglob("*"):
                if not filepath.is_file():
                    continue
                if ".git" in filepath.parts:
                    continue
                if filepath.suffix not in _TEXT_EXTENSIONS:
                    continue
                if filepath.stat().st_size > _MAX_FILE_BYTES:
                    continue
                try:
                    text = filepath.read_text(encoding="utf-8", errors="ignore").strip()
                    if not text:
                        continue
                    rel_path = str(filepath.relative_to(tmpdir))
                    documents.append(
                        Document(
                            text=text,
                            metadata={
                                "source_type": "github",
                                "file_path": rel_path,
                                "url": f"{url_or_path.rstrip('/')}/blob/HEAD/{rel_path}",
                            },
                        )
                    )
                except Exception:
                    continue

        logger.info(f"GitHubLoader: {len(documents)} files loaded")
        return documents
