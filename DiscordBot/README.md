# 💎 The Finals Discord Bot — Stile Ruby Grind

Bot Discord per gestire un server competitivo di **The Finals**.
Usa le API della leaderboard per verificare i giocatori, rinominarli e assegnare ruoli rank automaticamente.

---

## ✨ Come funziona

### Quando un utente entra nel server:
1. Il bot gli manda un **DM** chiedendo il **nome Embark** con il codice `#xxxx`
2. Il bot **verifica** il giocatore tramite le API della leaderboard
3. Chiede se vuole il **ruolo rank** (il bot controlla l'RS e assegna il ruolo corretto)
4. **Rinomina** l'utente con il suo nome in-game
5. Annuncia il nuovo giocatore nel canale **📊-leaderboard**

### Regola fondamentale: solo promozioni!
I rank **non scendono mai**. Se un giocatore raggiunge Diamond, manterrà il ruolo Diamond anche se il suo RS cala temporaneamente. Il bot tiene traccia del **rank più alto** raggiunto.

### Aggiornamento automatico
Ogni 30 minuti il bot controlla tutti i giocatori collegati tramite API e:
- Aggiorna i rank (solo in positivo)
- Pubblica le promozioni nel canale dedicato
- Aggiorna la leaderboard del server

---

## 🎮 Rank di The Finals (soglie RS ufficiali)

| League | RS minimo | Sub-leagues |
|--------|-----------|-------------|
| 💎 Ruby | Top 500 per posizione | — |
| 💠 Diamond | 40,000 RS | D4 (40K) → D1 (47.5K) |
| 🔷 Platinum | 30,000 RS | P4 (30K) → P1 (37.5K) |
| 🥇 Gold | 20,000 RS | G4 (20K) → G1 (27.5K) |
| 🥈 Silver | 10,000 RS | S4 (10K) → S1 (17.5K) |
| 🥉 Bronze | 0 RS | B4 (0) → B1 (7.5K) |

---

## 📋 Comandi

### Utenti
| Comando | Descrizione |
|---------|-------------|
| `/link Nome#1234` | Collega il tuo account Embark |
| `/unlink` | Scollega l'account |
| `/rank [utente]` | Mostra rank, RS, posizione |
| `/search Nome#1234` | Cerca nella leaderboard globale |
| `/leaderboard` | Classifica dei giocatori del server |
| `/ruby` | Soglia attuale per il rank Ruby |
| `/stats` | Statistiche del server |
| `/help` | Lista comandi |

### Admin
| Comando | Descrizione |
|---------|-------------|
| `/setup` | Crea ruoli rank + canale 📊-leaderboard |
| `/updateranks` | Forza aggiornamento di tutti i giocatori |
| `/setchannel #canale` | Imposta canale per la leaderboard |

---

## 🚀 Installazione

### 1. Crea il Bot su Discord

1. Vai su [discord.com/developers/applications](https://discord.com/developers/applications)
2. **New Application** → nome → **Create**
3. Sezione **Bot**:
   - Clicca **Reset Token** → **copia il token** (salvalo!)
   - Attiva:
     - ✅ Presence Intent
     - ✅ Server Members Intent
     - ✅ Message Content Intent
4. Sezione **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Manage Roles`, `Manage Nicknames`, `Send Messages`, `Embed Links`, `Create Public Threads`
5. Copia il link → aprilo → invita il bot nel tuo server

### 2. Configura il progetto

```bash
cd the-finals-bot

# Installa dipendenze
pip install -r requirements.txt

# Copia e modifica la configurazione
cp .env.example .env
# Apri .env e incolla il tuo token
```

### 3. Avvia

```bash
python bot.py
```

### 4. Setup nel server Discord

1. Scrivi `/setup` nel server → crea ruoli e canale leaderboard
2. **Importante**: vai nelle impostazioni del server → Ruoli → sposta il ruolo del bot **sopra** ai ruoli 🎮
3. I nuovi membri riceveranno un DM automatico per collegare l'account

---

## 📁 Struttura

```
the-finals-bot/
├── bot.py              # Bot principale — comandi, eventi, auto-update
├── thefinals_api.py    # Client API leaderboard + soglie RS
├── database.py         # SQLite — link account e rank migliore
├── config.py           # Configurazione (.env)
├── requirements.txt    # Dipendenze Python
├── .env.example        # Template configurazione
└── data/
    └── bot.db          # Database (creato automaticamente)
```

---

## 📡 API utilizzate

Le API sono **pubbliche e gratuite**, non serve nessuna chiave:
- **Principale**: `api.the-finals-leaderboard.com` (by leonlarsson)
- **Fallback**: API diretta di Embark Studios (Google Storage)

La leaderboard mostra i **top 10.000** giocatori. Giocatori fuori dalla top 10K non possono essere trovati.

---

## ⚠️ Note

- Aggiorna `CURRENT_SEASON` nel `.env` ad ogni nuova stagione (attualmente Season 10 = `s10`)
- Il bot non può rinominare il proprietario del server né utenti con ruoli superiori
- I DM devono essere aperti per ricevere il messaggio di benvenuto
- Se un utente ha i DM chiusi, può usare `/link` nel server
