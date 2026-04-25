"""
One-time script to create the Pinecone index for DocsSage.
Run once before first deploy:

    cd backend
    source .venv/bin/activate
    python scripts/setup_pinecone.py
"""

import sys
from pathlib import Path

# allow importing app.config from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from pinecone import Pinecone, ServerlessSpec

from app.config import settings

DIMENSION = 512       # voyage-3-lite output dimension
METRIC = "cosine"
CLOUD = "aws"
REGION = "us-east-1"


def main() -> None:
    pc = Pinecone(api_key=settings.pinecone_api_key)

    existing = [idx.name for idx in pc.list_indexes()]

    if settings.pinecone_index_name in existing:
        print(f"Index '{settings.pinecone_index_name}' already exists — nothing to do.")
        return

    print(f"Creating index '{settings.pinecone_index_name}' ...")
    pc.create_index(
        name=settings.pinecone_index_name,
        dimension=DIMENSION,
        metric=METRIC,
        spec=ServerlessSpec(cloud=CLOUD, region=REGION),
    )
    print(f"Done. Index '{settings.pinecone_index_name}' created.")
    print(f"  dimension : {DIMENSION}")
    print(f"  metric    : {METRIC}")
    print(f"  cloud     : {CLOUD} / {REGION}")


if __name__ == "__main__":
    main()
