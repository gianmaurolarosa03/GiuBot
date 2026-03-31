"""
Client API per The Finals
"""

import aiohttp
import asyncio
from typing import Optional
from config import Config

LEAGUE_ORDER = ["Ruby", "Diamante", "Platino", "Oro", "Argento", "Bronzo", "Unranked"]

LEAGUE_COLORS = {
    "Unranked":  0x4F4F4F,
    "Bronzo":    0xC27F32,
    "Argento":   0xD0D2D3,
    "Oro":       0xC5A643,
    "Platino":   0xB3B1AC,
    "Diamante":  0xB9F2FF,
    "Ruby":      0x9B111E,
}


def determine_rank(rank_score: int, position: int = 99999) -> str:
    if position <= 500:
        return "Ruby"
    if rank_score >= 40000:
        return "Diamante"
    if rank_score >= 30000:
        return "Platino"
    if rank_score >= 20000:
        return "Oro"
    if rank_score >= 10000:
        return "Argento"
    if rank_score > 0:
        return "Bronzo"
    return "Unranked"


def determine_sub_rank(rank_score: int, position: int = 99999) -> str:
    if position <= 500:
        return "Ruby"
    subs = [
        (47500, "Diamante 1"), (45000, "Diamante 2"), (42500, "Diamante 3"), (40000, "Diamante 4"),
        (37500, "Platino 1"),  (35000, "Platino 2"),  (32500, "Platino 3"),  (30000, "Platino 4"),
        (27500, "Oro 1"),      (25000, "Oro 2"),      (22500, "Oro 3"),      (20000, "Oro 4"),
        (17500, "Argento 1"),  (15000, "Argento 2"),  (12500, "Argento 3"),  (10000, "Argento 4"),
        (7500, "Bronzo 1"),    (5000, "Bronzo 2"),    (2500, "Bronzo 3"),    (0, "Bronzo 4"),
    ]
    for threshold, name in subs:
        if rank_score >= threshold:
            return name
    return "Unranked"


class TheFinalsAPI:
    BASE_URL = "https://api.the-finals-leaderboard.com"

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={
                    "Accept-Encoding": "gzip, deflate",
                    "User-Agent": "TheFinalsDiscordBot/1.0",
                }
            )
        return self._session

    async def search_player(self, name: str) -> Optional[dict]:
        return await self._search_season(name, Config.CURRENT_SEASON)

    async def autocomplete_search(self, partial: str, max_results: int = 25) -> list[dict]:
        """Cerca nomi parziali per autocomplete. Timeout corto per Discord (3s max)."""
        if len(partial) < 2:
            return []

        try:
            session = await self._get_session()
            # Usa solo la stagione corrente per velocità
            url = f"{self.BASE_URL}/v1/leaderboard/{Config.CURRENT_SEASON}/crossplay"
            params = {"name": partial}

            # Timeout cortissimo: Discord dà solo 3 secondi per l'autocomplete
            async with asyncio.timeout(2.5):
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json(content_type=None)

                    if isinstance(data, dict) and "data" in data:
                        entries = data["data"]
                    elif isinstance(data, list):
                        entries = data
                    else:
                        return []

                    results = []
                    for entry in entries[:max_results]:
                        rs = entry.get("rankScore", 0)
                        pos = entry.get("rank", 99999)
                        results.append({
                            "name": entry.get("name", "?"),
                            "rankScore": rs,
                            "leagueIta": determine_rank(rs, pos),
                        })
                    return results

        except (asyncio.TimeoutError, Exception) as e:
            # Autocomplete fallito silenziosamente — non bloccare l'utente
            return []

    async def _search_season(self, name: str, season: str) -> Optional[dict]:
        try:
            session = await self._get_session()
            url = f"{self.BASE_URL}/v1/leaderboard/{season}/crossplay"
            params = {"name": name}

            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

                if isinstance(data, dict) and "data" in data:
                    entries = data["data"]
                elif isinstance(data, list):
                    entries = data
                else:
                    return None

                if not entries:
                    return None

                for entry in entries:
                    if entry.get("name", "").lower() == name.lower():
                        return self._normalize(entry, season)

                return self._normalize(entries[0], season)

        except Exception as e:
            print(f"[API] Errore '{name}' in {season}: {e}")
            return None

    async def get_ruby_threshold(self) -> Optional[dict]:
        try:
            session = await self._get_session()
            for season in [Config.CURRENT_SEASON, "s9"]:
                url = f"{self.BASE_URL}/v1/leaderboard/{season}/crossplay"
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json(content_type=None)
                    entries = data.get("data", data) if isinstance(data, dict) else data
                    if isinstance(entries, list) and len(entries) >= 500:
                        return self._normalize(entries[499], season)
        except Exception as e:
            print(f"[API] Errore Ruby: {e}")
        return None

    def _normalize(self, entry: dict, season: str = "?") -> dict:
        rs = entry.get("rankScore", 0)
        pos = entry.get("rank", 99999)
        return {
            "name":       entry.get("name", "Unknown"),
            "rank":       pos,
            "change":     entry.get("change", 0),
            "rankScore":  rs,
            "leagueIta":  determine_rank(rs, pos),
            "subLeague":  determine_sub_rank(rs, pos),
            "steamName":  entry.get("steamName", ""),
            "psnName":    entry.get("psnName", ""),
            "xboxName":   entry.get("xboxName", ""),
            "season":     season,
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
