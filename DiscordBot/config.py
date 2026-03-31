"""
Configurazione — carica dal file .env
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Token del bot Discord (OBBLIGATORIO)
    BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")

    # Stagione corrente di The Finals
    # Season 10 inizia il 26/03/2026 — aggiorna questo valore ogni nuova stagione
    # Controlla su https://api.the-finals-leaderboard.com per i valori validi
    # CURRENT_SEASON: str = os.getenv("CURRENT_SEASON", "s10")
    CURRENT_SEASON: str = "s10"
    
    # Piattaforma leaderboard
    PLATFORM: str = os.getenv("PLATFORM", "crossplay")

    # Intervallo aggiornamento automatico (minuti)
    UPDATE_INTERVAL: int = int(os.getenv("UPDATE_INTERVAL", "30"))

    # Percorso database
    DB_PATH: str = os.getenv("DB_PATH", "data/bot.db")
