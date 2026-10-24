"""Small trusted-document retrieval boundary with provenance and injection flags."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


@dataclass(frozen=True)
class KnowledgeDocument:
    source_id: str
    title: str
    text: str
    publisher: str
    published_on: date | None
    retrieved_on: date
    version: str | None = None


@dataclass(frozen=True)
class KnowledgeHit:
    source_id: str
    title: str
    passage: str
    publisher: str
    published_on: date | None
    retrieved_on: date
    version: str | None
    untrusted_content_warning: bool


class KnowledgeStore:
    def __init__(self, documents: tuple[KnowledgeDocument, ...] = ()):
        self._documents = {doc.source_id: doc for doc in documents}

    def add(self, document: KnowledgeDocument) -> None:
        if not document.source_id or not document.title or not document.text:
            raise ValueError("source_id, title, and text are required")
        self._documents[document.source_id] = document

    def search(self, query: str, limit: int = 5) -> tuple[KnowledgeHit, ...]:
        if not query.strip() or not 1 <= limit <= 20:
            raise ValueError("query is required and limit must be between 1 and 20")
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        ranked = []
        for doc in self._documents.values():
            haystack = f"{doc.title} {doc.text}".lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                snippet = doc.text[:600]
                warning = bool(re.search(r"ignore (all|previous)|system message|grant permission", snippet, re.I))
                ranked.append((score, KnowledgeHit(doc.source_id, doc.title, snippet, doc.publisher,
                                                   doc.published_on, doc.retrieved_on, doc.version, warning)))
        ranked.sort(key=lambda item: (-item[0], item[1].source_id))
        return tuple(hit for _, hit in ranked[:limit])
