"""Повтор сохранённого поиска: появились ли более дешёвые лоты."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from loguru import logger

from app.database.db import get_saved_search, update_saved_search_stats
from app.services.search_service import run_search


def check_saved_search(search_id: int) -> Dict[str, Any]:
    row = get_saved_search(search_id)
    if not row:
        return {"ok": False, "error": "Поиск не найден"}
    try:
        params = json.loads(row.params_json or "{}")
    except json.JSONDecodeError:
        params = {"brand": row.brand, "model": row.model, "sources": ["drom"]}
    data = run_search(params)
    results: List[dict] = data.get("results") or []
    prices = [int(r.get("price") or 0) for r in results if r.get("price")]
    min_price = min(prices) if prices else 0
    cheaper = []
    baseline = row.last_min_price or 0
    if baseline and min_price and min_price < baseline:
        cheaper = [r for r in results if (r.get("price") or 0) and r["price"] < baseline]
    update_saved_search_stats(search_id, min_price or baseline, len(results))
    logger.info(
        f"Monitor search={search_id} min={min_price} was={baseline} cheaper={len(cheaper)}"
    )
    return {
        "ok": True,
        "search_id": search_id,
        "brand": row.brand,
        "model": row.model,
        "previous_min_price": baseline,
        "current_min_price": min_price,
        "cheaper_count": len(cheaper),
        "cheaper": cheaper[:10],
        "total": len(results),
        "results": results,
        "errors": data.get("errors") or [],
    }
