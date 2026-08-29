import re
from urllib.parse import urlparse
def digits(value):
    raw = re.sub(r"\D", "", value or "")
    return int(raw) if raw else 0
def normalize_avito_item(item, brand="", model=""):
    title = str(item.get("title") or "Unknown").strip()
    year = item.get("year")
    if year is None:
        m = re.search(r"\b(19\d{2}|20\d{2})\b", title)
        year = int(m.group(1)) if m else 0
    region = item.get("region") or ""
    if not region:
        parts=[p for p in urlparse(item.get("url","")).path.split("/") if p]
        region=parts[0] if parts else ""
    return {**item,"title":title,"brand":item.get("brand") or brand.lower(),"model":item.get("model") or model.lower(),"price":int(item.get("price") or 0),"year":int(year or 0),"mileage":int(item.get("mileage") or 0),"region":region,"data_confidence":0.65,"source":"avito","platform":"avito"}
