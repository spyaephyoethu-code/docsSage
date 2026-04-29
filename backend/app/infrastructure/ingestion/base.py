from dataclasses import dataclass, field


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    text: str
    token_count: int
    metadata: dict = field(default_factory=dict)
