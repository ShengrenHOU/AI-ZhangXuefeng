from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx


SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
BING_RSS_ENDPOINT = "https://www.bing.com/search?format=rss&cc=cn&setlang=zh-Hans&q="
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
}


@dataclass(slots=True)
class WebRetriever:
    max_results: int = 4
    timeout_seconds: float = 15.0
    max_chars: int = 2200

    def retrieve(self, queries: list[str]) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        results: list[dict[str, Any]] = []

        for query in queries:
            if not query.strip():
                continue
            for candidate in self._search(query):
                url = candidate["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                page = self._fetch_page(url)
                if page is None:
                    continue
                page["query"] = query
                page["score"] = candidate["score"]
                results.append(page)
                if len(results) >= self.max_results:
                    return results
        return results

    def _search(self, query: str) -> list[dict[str, Any]]:
        for search_fn in (self._search_bing_rss, self._search_duckduckgo):
            try:
                candidates = search_fn(query)
                if candidates:
                    return candidates
            except Exception:
                continue
        return []

    def _search_bing_rss(self, query: str) -> list[dict[str, Any]]:
        response = httpx.get(
            f"{BING_RSS_ENDPOINT}{quote_plus(query)}",
            timeout=self.timeout_seconds,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)

        candidates: list[dict[str, Any]] = []
        for item in root.findall("./channel/item"):
            url = (item.findtext("link") or "").strip()
            title = self._clean_html(item.findtext("title") or "")
            if not url:
                continue
            domain = urlparse(url).netloc.lower()
            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "domain": domain,
                    "score": self._domain_score(domain),
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[: self.max_results * 2]

    def _search_duckduckgo(self, query: str) -> list[dict[str, Any]]:
        response = httpx.get(
            f"{SEARCH_ENDPOINT}?q={quote_plus(query)}",
            timeout=self.timeout_seconds,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
        )
        response.raise_for_status()
        html_text = response.text

        candidates: list[dict[str, Any]] = []
        pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html_text):
            raw_url = match.group(1)
            title = self._clean_html(match.group(2))
            url = self._normalize_duckduckgo_url(raw_url)
            if not url:
                continue
            domain = urlparse(url).netloc.lower()
            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "domain": domain,
                    "score": self._domain_score(domain),
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[: self.max_results * 2]

    def _fetch_page(self, url: str) -> dict[str, Any] | None:
        try:
            response = httpx.get(
                url,
                timeout=self.timeout_seconds,
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
            )
            response.raise_for_status()
        except Exception:
            return None

        title_match = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL)
        title = self._clean_html(title_match.group(1)) if title_match else url
        body = self._extract_text(response.text)
        if not body:
            return None

        parsed = urlparse(str(response.url))
        return {
            "title": title,
            "url": str(response.url),
            "domain": parsed.netloc.lower(),
            "summary": body[: self.max_chars],
        }

    def _normalize_duckduckgo_url(self, raw_url: str) -> str | None:
        if raw_url.startswith("//duckduckgo.com/l/?"):
            parsed = urlparse("https:" + raw_url)
            uddg = parse_qs(parsed.query).get("uddg", [])
            if uddg:
                return unquote(uddg[0])
            return None
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            return raw_url
        return None

    def _domain_score(self, domain: str) -> int:
        score = 0
        if domain.endswith(".edu.cn"):
            score += 5
        if domain.endswith(".gov.cn"):
            score += 5
        if any(token in domain for token in ["gaokao.cn", "haeea.cn", "zsks", "admission", "eea", "eaagz"]):
            score += 4
        if domain.endswith(".cn"):
            score += 1
        if any(token in domain for token in ["edu", "university", "college"]):
            score += 2
        return score

    def _clean_html(self, value: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<.*?>", "", value))).strip()

    def _extract_text(self, html_text: str) -> str:
        stripped = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
        stripped = re.sub(r"(?is)<style.*?>.*?</style>", " ", stripped)
        stripped = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", stripped)
        stripped = re.sub(r"(?is)<.*?>", " ", stripped)
        stripped = html.unescape(stripped)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        return stripped
