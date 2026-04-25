from app.core.config import settings

MAX_KBS_PER_USER: int = settings.max_kbs_per_user
MAX_SOURCES_PER_KB: int = 5
MAX_PDF_SIZE_MB: int = 10
MAX_CRAWL_PAGES: int = 50
MAX_CHUNKS_PER_KB: int = 5_000
MAX_CHAT_MESSAGES_PER_DAY: int = 20
MAX_INGESTIONS_PER_DAY: int = 5
