"""
Database SQLite — con supporto per rank manuale admin
"""

import sqlite3
import json
import os
from typing import Optional


class Database:

    def __init__(self, db_path: str = "data/bot.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS linked_players (
                discord_id     INTEGER NOT NULL,
                guild_id       INTEGER NOT NULL,
                embark_name    TEXT NOT NULL,
                data           TEXT DEFAULT '{}',
                current_league TEXT DEFAULT NULL,
                manual_rank    TEXT DEFAULT NULL,
                linked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (discord_id, guild_id)
            );

            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id               INTEGER PRIMARY KEY,
                leaderboard_channel_id INTEGER DEFAULT NULL
            );
        """)
        conn.commit()
        conn.close()

    def link_player(self, discord_id, guild_id, embark_name, data):
        conn = self._conn()
        conn.execute("""
            INSERT INTO linked_players (discord_id, guild_id, embark_name, data, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id, guild_id) DO UPDATE SET
                embark_name = excluded.embark_name,
                data = excluded.data,
                updated_at = CURRENT_TIMESTAMP
        """, (discord_id, guild_id, embark_name, json.dumps(data)))
        conn.commit()
        conn.close()

    def update_league(self, discord_id, guild_id, league):
        conn = self._conn()
        conn.execute("""
            UPDATE linked_players SET current_league = ?, updated_at = CURRENT_TIMESTAMP
            WHERE discord_id = ? AND guild_id = ?
        """, (league, discord_id, guild_id))
        conn.commit()
        conn.close()

    def set_manual_rank(self, discord_id, guild_id, rank):
        """Imposta un rank manuale (admin). None per rimuoverlo."""
        conn = self._conn()
        conn.execute("""
            UPDATE linked_players SET manual_rank = ?, updated_at = CURRENT_TIMESTAMP
            WHERE discord_id = ? AND guild_id = ?
        """, (rank, discord_id, guild_id))
        conn.commit()
        conn.close()

    def unlink_player(self, discord_id, guild_id):
        conn = self._conn()
        conn.execute("DELETE FROM linked_players WHERE discord_id = ? AND guild_id = ?",
                     (discord_id, guild_id))
        conn.commit()
        conn.close()

    def get_player(self, discord_id, guild_id) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM linked_players WHERE discord_id = ? AND guild_id = ?",
            (discord_id, guild_id)
        ).fetchone()
        conn.close()
        if row:
            return {
                "discord_id": row["discord_id"], "guild_id": row["guild_id"],
                "embark_name": row["embark_name"], "data": json.loads(row["data"]),
                "current_league": row["current_league"],
                "manual_rank": row["manual_rank"],
            }
        return None

    def get_all_players(self, guild_id) -> list[dict]:
        conn = self._conn()
        rows = conn.execute("SELECT * FROM linked_players WHERE guild_id = ?", (guild_id,)).fetchall()
        conn.close()
        return [{
            "discord_id": r["discord_id"], "guild_id": r["guild_id"],
            "embark_name": r["embark_name"], "data": json.loads(r["data"]),
            "current_league": r["current_league"],
            "manual_rank": r["manual_rank"],
        } for r in rows]

    def get_guild_settings(self, guild_id) -> dict:
        conn = self._conn()
        row = conn.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)).fetchone()
        conn.close()
        return dict(row) if row else {"guild_id": guild_id, "leaderboard_channel_id": None}

    def update_guild_settings(self, guild_id, **kwargs):
        conn = self._conn()
        conn.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
        for key, value in kwargs.items():
            if key in {"leaderboard_channel_id"}:
                conn.execute(f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id))
        conn.commit()
        conn.close()
