from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import CategoryNode

ZGBS_HREF = re.compile(r"/zgbs/([a-z-]+)/(\d+)")
PAGINATION_HREF = re.compile(r"[?&]pg=\d+|ref=zg_bs_pg_")
SKIP_NAMES = {"any department", "next page →", "←previous page", "next page", "previous page"}


def _node_id_from_href(href: str) -> str | None:
    match = ZGBS_HREF.search(href)
    if match:
        return match.group(2)
    return None


def _slug_name(href: str) -> str:
    match = re.search(r"/Best-Sellers[^/]*?([A-Za-z0-9-]+)/zgbs", href)
    if match:
        return match.group(1).replace("-", " ").strip()
    return ""


def _clean_label(text: str) -> str:
    return text.replace("(Current)", "").strip()


def _ancestor_labels(anchor) -> list[str]:
    parts: list[str] = []
    node_li = anchor.find_parent("li")
    seen = set()
    while node_li is not None:
        marker = id(node_li)
        if marker in seen:
            break
        seen.add(marker)
        level_ul = node_li.find_parent("ul")
        if level_ul is None:
            break
        group_li = level_ul.find_parent("li")
        if group_li is None:
            break
        label_li = group_li.find_previous_sibling("li")
        if label_li is not None:
            anchor_el = label_li.find("a", href=True)
            selected = label_li.select_one('span[aria-current="page"]')
            text = ""
            if anchor_el is not None:
                text = _clean_label(anchor_el.get_text(" ", strip=True))
            elif selected is not None:
                text = _clean_label(selected.get_text(" ", strip=True))
            if text and text.lower() not in SKIP_NAMES:
                parts.append(text)
        node_li = group_li
    parts.reverse()
    return parts


def extract_category_links(html: str) -> list[CategoryNode]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, CategoryNode] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if PAGINATION_HREF.search(href):
            continue
        node_id = _node_id_from_href(href)
        if not node_id:
            continue
        name = anchor.get_text(" ", strip=True)
        if name.lower() in SKIP_NAMES or not name:
            continue
        segments = _ancestor_labels(anchor) + [name]
        path = " > ".join(segments)
        if node_id not in found or len(path) > len(found[node_id].path):
            found[node_id] = CategoryNode(node_id=node_id, name=name, path=path)
    return list(found.values())


def extract_current_path(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    selected = soup.select_one('span[aria-current="page"]')
    if selected is None:
        return None
    current = _clean_label(selected.get_text(" ", strip=True))
    probe_anchor = selected.find_parent("li")
    if probe_anchor is None:
        return current
    fake = BeautifulSoup(f"<li><a data-x></a></li>", "lxml").a
    ancestors = _ancestor_labels(selected)
    segments = ancestors + ([current] if current else [])
    return " > ".join(segments)
