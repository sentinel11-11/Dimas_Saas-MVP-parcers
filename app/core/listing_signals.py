"""Сигналы из текста объявления. Не выдумываем ДТП/ТО/скрутку."""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from app.models.car_listing import CarListing

_PHRASES = [
    (r"не\s+на\s+ходу|не\s+ездит|требует\s+ремонт|под\s+восстановлен", "needs_repair", "в тексте: нужен ремонт", -0.12),
    (r"после\s+дтп|битая|битый\s+в\s+дтп|восстановлен[ао]?\s+после", "crash_text", "в тексте: после ДТП", -0.1),
    (r"такси|каршеринг|яндекс\s*\.?\s*драйв|ситидрайв|в\s+аренде", "fleet", "в тексте: такси/аренда", -0.08),
    (r"без\s+птс|птс\s+нет|документы\s+проблем", "docs_bad", "в тексте: проблемы с документами", -0.1),
    (r"в\s+залоге|залог\s+банка|кредитн", "lien", "в тексте: залог/кредит", -0.06),
    (r"скрут(или|ка)|корректир\w+\s+пробег|мотанул", "odo_text", "в тексте: пробег правили", -0.12),
    (r"срочн(о|ая\s+продаж)", "urgent", "в тексте: срочная продажа", -0.02),
    (r"сервисн(ая|ый)\s+книжк|то\s+у\s+дилера|официал\w+\s+дилер", "dealer_service", "в тексте: ТО у дилера", 0.03),
    (r"гаражн\w+\s+хранен", "garage", "в тексте: гаражное хранение", 0.02),
]


def extract_signals(car: CarListing, peer_miles: Optional[List[int]] = None) -> List[dict]:
    blob = " ".join(
        str(x or "")
        for x in (
            car.title,
            getattr(car, "description", None),
            car.pts,
        )
    ).lower()
    flags: List[dict] = []
    seen = set()
    for pat, fid, label, delta in _PHRASES:
        if fid in seen:
            continue
        if re.search(pat, blob, re.I):
            seen.add(fid)
            flags.append({"id": fid, "label": label, "delta": delta})

    if car.accidents is not None and int(car.accidents) > 0:
        flags.append({
            "id": "accidents",
            "label": f"ДТП в карточке: {int(car.accidents)}",
            "delta": -min(0.15, 0.05 * int(car.accidents)),
        })

    year = car.year or 0
    km = car.mileage or 0
    age = max(1, datetime.now().year - year) if year >= 1990 else 0
    if age >= 4 and km and km < age * 3000:
        flags.append({
            "id": "low_km",
            "label": "пробег заметно ниже типичного для года — проверьте, не факт скрутки",
            "delta": -0.04,
        })
    if peer_miles and km:
        med = sorted(peer_miles)[len(peer_miles) // 2]
        ids = {f["id"] for f in flags}
        if med >= 40000 and km < med * 0.35 and "low_km" not in ids:
            flags.append({
                "id": "low_km_peers",
                "label": "пробег сильно ниже похожих в этой выдаче",
                "delta": -0.03,
            })
    return flags
