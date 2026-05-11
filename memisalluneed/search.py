from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import jieba

from memisalluneed.schema import MemoryItem
from memisalluneed.store import MemoryStore


@dataclass(frozen=True)
class MemorySearchResult:
    item: MemoryItem
    score: float


BM25_K1 = 1.5
BM25_B = 0.75
MAX_TOKEN_REPETITIONS = 8

STOPWORDS = {
    "的",
    "了",
    "是",
    "我",
    "你",
    "他",
    "她",
    "它",
    "在",
    "和",
    "与",
    "吗",
    "呢",
    "啊",
    "这",
    "那",
    "一个",
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
}

TECHNICAL_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)+|[a-z0-9]+")
CHINESE_SPAN_RE = re.compile(r"[\u4e00-\u9fff]+")


def tokenize_terms(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    terms: list[str] = []

    for match in TECHNICAL_TOKEN_RE.finditer(normalized):
        token = match.group(0).strip("._/-")
        if token:
            terms.append(token)
            terms.extend(_split_compound_token(token))

    for token in jieba.lcut(normalized):
        token = token.strip()
        if token and not _is_punctuation_only(token) and not _is_single_chinese_char(token):
            terms.append(token)

    for span in CHINESE_SPAN_RE.findall(normalized):
        terms.extend(_chinese_ngrams(span, min_n=2, max_n=3))

    return _filter_and_cap_terms(terms)


def _split_compound_token(token: str) -> list[str]:
    if not any(separator in token for separator in ("_", "-", "/", ".")):
        return []
    return [
        part
        for part in re.split(r"[._/-]+", token)
        if part and part != token
    ]


def _chinese_ngrams(text: str, *, min_n: int, max_n: int) -> list[str]:
    grams: list[str] = []
    for size in range(min_n, max_n + 1):
        if len(text) < size:
            continue
        grams.extend(text[index : index + size] for index in range(len(text) - size + 1))
    return grams


def _filter_and_cap_terms(terms: list[str]) -> list[str]:
    counts: Counter[str] = Counter()
    filtered: list[str] = []
    for term in terms:
        if not term or term in STOPWORDS or _is_punctuation_only(term):
            continue
        if counts[term] >= MAX_TOKEN_REPETITIONS:
            continue
        counts[term] += 1
        filtered.append(term)
    return filtered


def _is_punctuation_only(text: str) -> bool:
    return all(unicodedata.category(char).startswith("P") for char in text)


def _is_single_chinese_char(text: str) -> bool:
    return len(text) == 1 and "\u4e00" <= text <= "\u9fff"


def score_memories_bm25(
    query: str,
    items: list[MemoryItem],
) -> list[MemorySearchResult]:
    query_terms = tokenize_terms(query)
    if not query_terms or not items:
        return []

    document_terms = [tokenize_terms(item.content) for item in items]
    document_lengths = [len(terms) for terms in document_terms]
    non_empty_lengths = [length for length in document_lengths if length > 0]
    if not non_empty_lengths:
        return []

    avg_doc_len = sum(non_empty_lengths) / len(non_empty_lengths)
    document_frequencies = _document_frequencies(document_terms)
    total_documents = len(items)

    results: list[MemorySearchResult] = []
    for item, terms, doc_len in zip(items, document_terms, document_lengths):
        if doc_len == 0:
            continue
        score = _bm25_score(
            query_terms=query_terms,
            document_terms=terms,
            document_frequencies=document_frequencies,
            total_documents=total_documents,
            doc_len=doc_len,
            avg_doc_len=avg_doc_len,
        )
        if score > 0:
            results.append(MemorySearchResult(item=item, score=score))
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def _document_frequencies(document_terms: list[list[str]]) -> Counter[str]:
    frequencies: Counter[str] = Counter()
    for terms in document_terms:
        frequencies.update(set(terms))
    return frequencies


def _bm25_score(
    *,
    query_terms: list[str],
    document_terms: list[str],
    document_frequencies: Counter[str],
    total_documents: int,
    doc_len: int,
    avg_doc_len: float,
) -> float:
    term_frequencies = Counter(document_terms)
    score = 0.0
    for term in query_terms:
        tf = term_frequencies.get(term, 0)
        if tf == 0:
            continue
        df = document_frequencies[term]
        idf = math.log(1 + ((total_documents - df + 0.5) / (df + 0.5)))
        denominator = tf + BM25_K1 * (1 - BM25_B + BM25_B * (doc_len / avg_doc_len))
        score += idf * ((tf * (BM25_K1 + 1)) / denominator)
    return score


def search_memories(
    store: MemoryStore,
    query: str,
    top_k: int = 5,
) -> list[MemorySearchResult]:
    results = score_memories_bm25(query, store.all())
    results.sort(
        key=lambda result: (
            result.score,
            result.item.confidence,
            result.item.created_at,
        ),
        reverse=True,
    )
    results = results[:top_k]
    store.mark_recalled(result.item.id for result in results)
    return results
