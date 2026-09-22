"""LLM-assisted, domain-neutral dashboard topic planning.

The output remains constrained data: it can only assign generated page IDs to
human-readable topic headings. JSX, routes, and data access remain entirely
deterministic in the theme renderer.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger("converter.ui.dashboard_topics")


class DashboardTopicPlanner:
    """Group generated pages by business purpose via the configured provider."""

    def group(self, pages: list[dict]) -> list[dict[str, object]]:
        if not pages:
            return []
        page_ids = {page["dashboard_id"] for page in pages}
        page_list = [
            {"id": page["dashboard_id"], "name": page["nav_link_text"]}
            for page in pages if page.get("nav_link_text")
        ]
        if not page_list:
            return []
        prompt = f"""Group these MS Access application pages into 2 to 6 concise,
domain-appropriate dashboard topics. Do not assume a specific industry.
Every page id must appear exactly once. Return only JSON in this shape:
{{"topics": [{{"title": "Topic name", "page_ids": ["page_id"]}}]}}

Pages:
{json.dumps(page_list, ensure_ascii=False)}"""
        try:
            from ....llm.provider import get_default_provider
            response = get_default_provider().generate(
                prompt=prompt,
                system_prompt="You organize business application navigation. Return strict JSON only.",
                json_mode=True,
            )
            raw = json.loads(response.content)
            topics = raw.get("topics", []) if isinstance(raw, dict) else []
            seen: set[str] = set()
            valid: list[dict[str, object]] = []
            for topic in topics:
                title = str(topic.get("title", "")).strip()[:48]
                ids = [str(page_id) for page_id in topic.get("page_ids", [])]
                ids = [page_id for page_id in ids if page_id in page_ids and page_id not in seen]
                if title and ids:
                    seen.update(ids)
                    valid.append({"title": title, "page_ids": ids})
            if valid and seen == page_ids:
                return valid
            logger.warning("Dashboard topic plan omitted or duplicated pages; using fallback")
        except Exception as exc:
            logger.info("Dashboard topic planner unavailable; using fallback: %s", exc)
        return [{"title": "Application Workspaces", "page_ids": [page["id"] for page in page_list]}]
