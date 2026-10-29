#!/usr/bin/env python3
"""SEO-Радар: официальная статистика Яндекс.Вебмастера, без парсинга поисковой выдачи.

Требуется YANDEX_TOKEN как переменная окружения. Серверное выполнение предпочтительнее
браузерного: OAuth-токен НЕ публикуется в JavaScript и на GitHub Pages.
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "keywords.json"
DEST = ROOT / "web" / "data" / "positions.json"
API = "https://api.webmaster.yandex.net/v4"
REGIONS = {"22": "Калининград", "10857": "Калининградская область"}
DEVICES = {"mobile": "MOBILE", "desktop": "DESKTOP"}
DOMAIN = "битвадиванов.рф"
USER_AGENT = "SEO-Radar-Bitva-Divanov/1.0"


class APIError(Exception):
    pass


def yandex_json(method: str, path: str, token: str, payload: dict | None = None, *, tries=3):
    headers = {"Authorization": "OAuth " + token, "Accept": "application/json", "User-Agent": USER_AGENT}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=UTF-8"
    url = API + path
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            content = exc.read(2500).decode("utf-8", errors="replace")
            try:
                msg = json.loads(content).get("error_message", content)
            except ValueError:
                msg = content
            if exc.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(min(10, (2 ** attempt) + random.random()))
                continue
            raise APIError(f"HTTP {exc.code}: {str(msg).replace(token, '[скрыто]')[:260]}") from None
        except (OSError, ValueError) as exc:
            if attempt < tries - 1:
                time.sleep(1.2 * (attempt + 1))
                continue
            raise APIError(f"Ошибка соединения / формата ответа: {str(exc).replace(token, '[скрыто]')[:240]}") from None
    raise APIError("Превышено количество попыток")


def domain_matches(url: str) -> bool:
    try:
        name = urllib.parse.urlsplit(url).hostname
        if not name:
            return False
        name = name.lower().rstrip(".")
        name = name[4:] if name.startswith("www.") else name
        return name.encode("idna").decode("ascii") == DOMAIN.encode("idna").decode("ascii")
    except (ValueError, UnicodeError, TypeError, AttributeError):
        return False


def discover_host(token: str) -> tuple[int, str]:
    user = yandex_json("GET", "/user", token)
    user_id = user.get("user_id") if isinstance(user, dict) else None
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise APIError("Яндекс не вернул корректный ID пользователя")
    host_payload = yandex_json("GET", f"/user/{user_id}/hosts", token)
    host_candidates = host_payload.get("hosts") if isinstance(host_payload, dict) else None
    if not isinstance(host_candidates, list):
        raise APIError("Яндекс не вернул корректный список сайтов")
    verified = [h for h in host_candidates
                if isinstance(h, dict) and h.get("verified") is True
                and any(domain_matches(h.get(key, ""))
                        for key in ("ascii_host_url", "unicode_host_url"))]
    if not verified:
        raise APIError(f"В Яндекс Вебмастере не найден подтверждённый сайт {DOMAIN}. Проверьте аккаунт.")
    # Вебмастер может вернуть http/www как дополнительное зеркало. Статистику
    # запрашиваем для подтверждённого главного адреса, возвращённого самим API.
    mirrors = [h.get("main_mirror") for h in verified]
    mirrors = [h for h in mirrors if isinstance(h, dict) and h.get("verified") is True
               and any(domain_matches(h.get(key, ""))
                       for key in ("ascii_host_url", "unicode_host_url"))]
    preferred = sorted(mirrors or verified, key=lambda h: (
        0 if any(str(h.get(key, "")).startswith("https://")
                 for key in ("ascii_host_url", "unicode_host_url")) else 1,
        1 if any("//www." in str(h.get(key, ""))
                 for key in ("ascii_host_url", "unicode_host_url")) else 0,
    ))[0]
    host_id = preferred.get("host_id")
    if not isinstance(host_id, str) or not host_id:
        raise APIError("Не найден ID сайта в ответе Вебмастера")
    return user_id, host_id


def normalize_analytics(payload: dict, query: str, region: str, device: str) -> list[dict]:
    """Нормализация реального ответа query-analytics/list по дням и метрикам.

    Позиция — среднее место показа, в том числе дробное. Никаких предположений
    по отсутствующим позициям и никаких значений 'за пределами ТОП-100'.
    """
    results = []
    for entry in payload.get("text_indicator_to_statistics", []):
        text_info = entry.get("text_indicator", {})
        actual_query = text_info.get("value")
        if text_info.get("type") != "QUERY" or not isinstance(actual_query, str):
            continue
        if actual_query.strip().casefold() != query.strip().casefold():
            continue
        candidate_url = entry.get("popular_complementary_indicator") or {}
        url = candidate_url.get("value", "") if candidate_url.get("type") == "URL" else ""
        stats_by_date: dict[str, dict] = {}
        for stat in entry.get("statistics", []):
            date = stat.get("date")
            field = stat.get("field")
            value = stat.get("value")
            if not isinstance(date, str) or field not in ("POSITION", "IMPRESSIONS", "CLICKS", "CTR", "DEMAND"):
                continue
            try:
                parsed_date = dt.date.fromisoformat(date)
            except ValueError:
                continue
            if parsed_date.isoformat() != date:
                continue
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(value) or value < 0):
                continue
            stats_by_date.setdefault(date, {})[field] = float(value)
        for date, st in stats_by_date.items():
            # Нет позиции => данных о позиции действительно нет, не присваиваем худшее место.
            position = st.get("POSITION")
            if position is not None and position < 1:
                position = None
            results.append({
                "date": date,
                "query": query,
                "region": region,
                "device": device,
                "position": round(position, 2) if position is not None else None,
                "impressions": st.get("IMPRESSIONS"),
                "clicks": st.get("CLICKS"),
                "demand": st.get("DEMAND"),
                "url": url if isinstance(url, str) and len(url) < 400 else "",
            })
    return results


def fetch_keyword(token: str, user_id: int, host_id: str, query: str, region: str, device: str):
    endpoint = f"/user/{user_id}/hosts/{urllib.parse.quote(host_id, safe='')}/query-analytics/list"
    body = {
        "offset": 0,
        "limit": 500,
        "device_type_indicator": DEVICES[device],
        "search_location": "WEB_LOCATION",
        "text_indicator": "QUERY",
        "region_ids": [int(region)],
        "filters": {"text_filters": [{
            "text_indicator": "QUERY",
            "operation": "TEXT_MATCH",
            "value": query,
        }]}
    }
    rows = []
    while True:
        data = yandex_json("POST", endpoint, token, body)
        if not isinstance(data, dict) or not isinstance(data.get("text_indicator_to_statistics"), list):
            raise APIError("Некорректный ответ мониторинга поисковых запросов")
        entries = data["text_indicator_to_statistics"]
        if any(not isinstance(entry, dict) for entry in entries):
            raise APIError("Некорректные записи мониторинга поисковых запросов")
        count = data.get("count", len(entries))
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise APIError("Некорректное число записей мониторинга поисковых запросов")
        rows.extend(normalize_analytics(data, query, region, device))
        next_offset = body["offset"] + len(entries)
        if next_offset >= count:
            return rows
        if not entries:
            raise APIError("Яндекс вернул пустую страницу до конца списка запросов")
        body = {**body, "offset": next_offset}


def build_default(keywords: list[dict]) -> dict:
    return {
        "schema": 2,
        "site": DOMAIN,
        "provider": "Яндекс Вебмастер",
        "position_type": "average_show_position",
        "updated_at": None,
        "last_attempt_at": None,
        "last_success_at": None,
        "latest_position_date": None,
        "status": "not_connected",
        "keywords": keywords,
        "regions": REGIONS,
        "measurements": [],
        "errors": [],
    }


def load_state(keywords: list[dict]) -> dict:
    if DEST.exists():
        try:
            data = json.loads(DEST.read_text(encoding="utf-8"))
            if data.get("schema") == 2 and isinstance(data.get("measurements"), list):
                data["keywords"] = keywords
                return data
        except (ValueError, OSError):
            pass
    return build_default(keywords)


def merge_records(existing: list[dict], new: list[dict], *, today: dt.date | None = None) -> list[dict]:
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=2))).date()
    earliest = today - dt.timedelta(days=120)
    keyed = {}
    for row in existing + new:
        if not isinstance(row, dict):
            continue
        try:
            date = dt.date.fromisoformat(row["date"])
        except (ValueError, KeyError, TypeError):
            continue
        if date < earliest or date > today:
            continue
        key = (row.get("date"), row.get("query"), row.get("region"), row.get("device"))
        keyed[key] = row
    return sorted(keyed.values(), key=lambda x: (x["date"], x["region"], x["device"], x["query"]))


def store(state: dict):
    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(DEST)


def run() -> int:
    keywords = json.loads(CONFIG.read_text(encoding="utf-8"))
    queries = [v["query"] for v in keywords]
    if len(queries) != len(set(x.casefold() for x in queries)):
        print("Ошибка: повторяющиеся поисковые запросы", file=sys.stderr)
        return 2
    token = os.environ.get("YANDEX_TOKEN", "").strip()
    state = load_state(keywords)
    state["last_attempt_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    state.setdefault("last_success_at", state.get("updated_at"))
    state["collection"] = {
        "successful_requests": 0,
        "total_requests": len(queries) * len(REGIONS) * len(DEVICES),
        "current_position_records": 0,
        "latest_date": None,
        "latest_position_date": None,
    }
    if not token:
        state["status"] = "not_connected"
        state["errors"] = [{"message": "Добавьте секрет YANDEX_TOKEN в настройках GitHub Actions."}]
        store(state)
        print("Токен отсутствует: опубликована панель без данных.")
        return 0
    try:
        user_id, host_id = discover_host(token)
    except APIError as exc:
        state["status"] = "error"
        state["errors"] = [{"message": str(exc)}]
        store(state)
        print(f"Подключение не удалось: {exc}", file=sys.stderr)
        return 1
    tasks = [(query, region, device) for query in queries for region in REGIONS for device in DEVICES]
    successful = 0
    measures = []
    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = {pool.submit(fetch_keyword, token, user_id, host_id, *task): task for task in tasks}
        for future in concurrent.futures.as_completed(results):
            query, region, device = results[future]
            try:
                measures.extend(future.result())
                successful += 1
            except APIError as exc:
                errors.append({"query": query, "region": region, "device": device, "message": str(exc)})
            except Exception as exc:
                errors.append({"query": query, "region": region, "device": device, "message": "Внутренняя ошибка: " + type(exc).__name__})
    state["measurements"] = merge_records(state.get("measurements", []), measures)
    if successful:
        state["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        state["last_success_at"] = state["updated_at"]
    current_rows = merge_records([], measures)
    current_positions = [row for row in current_rows if row.get("position") is not None]
    state["latest_position_date"] = max(
        (row["date"] for row in state["measurements"] if row.get("position") is not None), default=None)
    state["collection"] = {
        "successful_requests": successful,
        "total_requests": len(tasks),
        "current_position_records": len(current_positions),
        "latest_date": max((row["date"] for row in current_rows), default=None),
        "latest_position_date": max((row["date"] for row in current_positions), default=None),
    }
    state["status"] = "ok" if not errors else "partial" if successful else "error"
    state["errors"] = errors[:12]
    store(state)
    print(f"Готово: запросов {len(tasks)}, успешных {successful}, новых точек {len(measures)}, всего записей {len(state['measurements'])}, ошибок {len(errors)}.")
    if errors:
        print("Типичные ошибки:", *[e.get('message') for e in errors[:3]], sep="\n  - ", file=sys.stderr)
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(run())
