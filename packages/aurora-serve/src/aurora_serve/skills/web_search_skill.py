import json
import logging
import random
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

import charset_normalizer
import pandas as pd
import requests
from bs4 import BeautifulSoup

from aurora_core.agent.skill.base import BaseSkill

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
]

session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENTS[0],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = re.sub(r"[\x00-\x1F\x7F]", "", text)
    cleaned = re.sub(r"\n+", "\n\n", cleaned).strip()
    cleaned = re.sub(r" +", " ", cleaned)
    return cleaned


def get_page_content(url: str) -> str:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.bing.com/",
    }
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return "非HTML内容，无法提取"
        chunks = []
        for chunk in response.iter_content(chunk_size=1024):
            chunks.append(chunk)
        content_bytes = b"".join(chunks)
        detected = charset_normalizer.from_bytes(content_bytes).best()
        encoding = detected.encoding if detected and detected.encoding else "utf-8"
        text = content_bytes.decode(encoding, errors="replace")
    except Exception as e:
        logger.error(f"获取页面内容失败 ({url}): {e}")
        return "无法获取内容"

    soup = BeautifulSoup(text, "html.parser")
    article = soup.find("article")
    if article:
        extracted_text = "\n\n".join(
            p.get_text(separator="\n", strip=True)
            for p in article.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"])
        )
    else:
        paragraphs = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"])
        extracted_text = "\n\n".join(p.get_text(separator="\n", strip=True) for p in paragraphs)

    extracted_text = clean_text(extracted_text)
    if len(extracted_text) < 200:
        extracted_text = "\n\n".join(
            p.get_text(separator="\n", strip=True)
            for p in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"])
        )
        extracted_text = clean_text(extracted_text)
    return extracted_text if extracted_text else "无法提取内容"


def get_bing_search_results(query: str, num_results: int = 5) -> list[dict[str, str]]:
    query_encoded = urllib.parse.quote_plus(query)
    url = f"https://www.bing.com/search?q={query_encoded}"
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.bing.com/",
        }
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            raise Exception("搜索结果页面非HTML内容")
        detected = charset_normalizer.from_bytes(response.content).best()
        encoding = detected.encoding if detected and detected.encoding else "utf-8"
        text = response.content.decode(encoding, errors="replace")
    except Exception as e:
        logger.error(f"请求Bing搜索失败: {e}")
        raise

    soup = BeautifulSoup(text, "html.parser")
    candidates = soup.select("li.b_algo, li.b_ans, div.b_vlist > li, div.b_mhdr")
    links = []
    for el in candidates:
        a = el.select_one("h2 a") or el.select_one("a")
        link = a["href"] if a and a.has_attr("href") else None
        title = a.get_text(strip=True) if a else el.get_text(strip=True)[:80]
        snippet_tag = el.select_one("p") or el.select_one(".b_caption p")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
        if not link:
            continue
        if link.startswith("https://www.zhihu.com"):
            continue
        links.append({"title": title, "link": link, "snippet": snippet})
        if len(links) >= num_results:
            break

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_link = {
            executor.submit(get_page_content, link_info["link"]): link_info
            for link_info in links
        }
        for future in as_completed(future_to_link):
            link_info = future_to_link[future]
            try:
                content = future.result()
                results.append({**link_info, "content": content})
            except Exception as e:
                logger.error(f"抓取内容时出错 ({link_info['link']}): {e}")
                results.append({**link_info, "content": "无法获取内容"})
    return results


class WebSearchSkill(BaseSkill):
    """Search the web using Bing and return structured results with content snippets."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the internet using Bing to find up-to-date information. "
            "Returns search results with titles, links, snippets, and page content summaries."
        )

    @property
    def description_cn(self) -> str:
        return "使用必应搜索互联网获取最新信息，返回包含标题、链接和内容摘要的搜索结果。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query keywords.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to retrieve (default 5, max 10).",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", num_results: int = 5, **kwargs: Any) -> str:
        if not query:
            return "No search query provided."
        num_results = max(1, min(int(num_results), 10))
        try:
            results = get_bing_search_results(query, num_results=num_results)
            if not results:
                return "No search results found."
            return (
                f"Web search results for '{query}':\n\n"
                + json.dumps(results, ensure_ascii=False, indent=2)
            )
        except Exception as e:
            return f"Web search failed: {e}"
