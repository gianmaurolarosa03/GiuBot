"""
The Finals Discord Bot — Stile "Ruby Grind"
- Leaderboard automatica alle 00:00 (mezzanotte)
- Rank update ogni ora
- /leaderboard /ruby /stats visibili solo a chi li usa
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, time, timezone
from typing import Optional

from config import Config
from database import Database
from thefinals_api import TheFinalsAPI, LEAGUE_ORDER, LEAGUE_COLORS

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()
api = TheFinalsAPI()

VALID_RANKS = ["Ruby", "Diamante", "Platino", "Oro", "Argento", "Bronzo"]


# ═══════════════════════════════════════════
#  UTILITY
# ═══════════════════════════════════════════

async def get_or_create_rank_role(guild, league_ita):
    role = discord.utils.get(guild.roles, name=league_ita)
    if role is None:
        color = LEAGUE_COLORS.get(league_ita, 0x808080)
        role = await guild.create_role(
            name=league_ita, color=discord.Color(color),
            hoist=True, reason=f"Ruolo: {league_ita}"
        )
    else:
        expected = LEAGUE_COLORS.get(league_ita, 0x808080)
        if role.color.value != expected:
            try:
                await role.edit(color=discord.Color(expected))
            except:
                pass
    return role


async def get_or_create_verified_role(guild):
    role = discord.utils.get(guild.roles, name="Verified")
    if role is None:
        role = await guild.create_role(name="Verified", color=discord.Color.green())
    return role


async def get_leaderboard_channel(guild):
    settings = db.get_guild_settings(guild.id)
    cid = settings.get("leaderboard_channel_id")
    if cid:
        ch = guild.get_channel(cid)
        if ch:
            return ch
    return None


async def assign_rank(guild, member, league_ita, embark_name, player_data):
    errors = []

    api_name = player_data.get("name", embark_name) if player_data else embark_name
    nick = api_name[:32]
    try:
        await member.edit(nick=nick)
    except discord.Forbidden:
        errors.append("Non posso rinominare — controlla gerarchia ruoli")
    except Exception as e:
        errors.append(f"Nick: {e}")

    roles_to_remove = [r for r in member.roles if r.name in LEAGUE_ORDER]
    if roles_to_remove:
        try:
            await member.remove_roles(*roles_to_remove)
        except discord.Forbidden:
            errors.append("Non posso rimuovere vecchi ruoli")

    new_role = await get_or_create_rank_role(guild, league_ita)
    try:
        await member.add_roles(new_role, reason=f"Rank: {league_ita}")
    except discord.Forbidden:
        errors.append(f"Non posso assegnare {league_ita}")

    verified = await get_or_create_verified_role(guild)
    if verified not in member.roles:
        try:
            await member.add_roles(verified)
        except:
            pass

    db.link_player(member.id, guild.id, embark_name, player_data or {})
    db.update_league(member.id, guild.id, league_ita)

    for e in errors:
        print(f"[WARN] {e}")
    return league_ita, errors


# ═══════════════════════════════════════════
#  MODAL + VIEW
# ═══════════════════════════════════════════

class LinkModal(discord.ui.Modal, title="🔗 Collega il tuo account The Finals"):
    embark_input = discord.ui.TextInput(
        label="Nome Embark (con #codice)",
        placeholder="Es: giammo#0001",
        required=True, min_length=3, max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embark_name = self.embark_input.value.strip()

        if "#" not in embark_name:
            await interaction.followup.send(embed=discord.Embed(
                title="❌", description="Serve il #codice: `Player#1234`",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        player = await api.search_player(embark_name)

        if player is None:
            final, errs = await assign_rank(
                interaction.guild, interaction.user,
                "Unranked", embark_name, {"name": embark_name}
            )
            desc = f"**Nome:** {embark_name}\n**Rank:** Unranked\n\nSi aggiornerà automaticamente!"
            if errs:
                desc += "\n\n⚠️ " + "\n".join(errs)
            await interaction.followup.send(embed=discord.Embed(
                title="✅ Collegato (Unranked)", description=desc,
                color=discord.Color(LEAGUE_COLORS["Unranked"])
            ), ephemeral=True)
            return

        league_ita = player.get("leagueIta", "Bronzo")
        final, errs = await assign_rank(
            interaction.guild, interaction.user, league_ita, embark_name, player
        )
        api_name = player.get("name", embark_name)
        rs = player.get("rankScore", 0)
        color = LEAGUE_COLORS.get(final, 0x808080)
        desc = f"**Nome:** {api_name}\n**Rank:** {final}\n**RS:** {rs:,}\n**Sub:** {player.get('subLeague','?')}"
        if errs:
            desc += "\n\n⚠️ " + "\n".join(errs)

        await interaction.followup.send(embed=discord.Embed(
            title=f"✅ {api_name}", description=desc, color=discord.Color(color)
        ), ephemeral=True)

        lb = await get_leaderboard_channel(interaction.guild)
        if lb:
            await lb.send(embed=discord.Embed(
                title="🆕 Nuovo giocatore!",
                description=f"{interaction.user.mention} → **{api_name}** — {final} ({rs:,} RS)",
                color=discord.Color(color)
            ))


class LinkUnlinkView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔗 Collega account", style=discord.ButtonStyle.green, custom_id="link_btn")
    async def link_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        saved = db.get_player(interaction.user.id, interaction.guild.id)
        if saved:
            await interaction.response.send_message(embed=discord.Embed(
                title="ℹ️ Già collegato",
                description=f"**{saved['embark_name']}** ({saved.get('current_league','?')}). Scollega prima.",
                color=discord.Color.yellow()
            ), ephemeral=True)
            return
        await interaction.response.send_modal(LinkModal())

    @discord.ui.button(label="🔓 Scollega account", style=discord.ButtonStyle.red, custom_id="unlink_btn")
    async def unlink_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        saved = db.get_player(interaction.user.id, interaction.guild.id)
        if not saved:
            await interaction.response.send_message("Non collegato.", ephemeral=True)
            return

        old = saved["embark_name"]
        db.unlink_player(interaction.user.id, interaction.guild.id)

        for r in interaction.user.roles:
            if r.name in LEAGUE_ORDER:
                try:
                    await interaction.user.remove_roles(r)
                except:
                    pass
        verified = discord.utils.get(interaction.guild.roles, name="Verified")
        if verified and verified in interaction.user.roles:
            try:
                await interaction.user.remove_roles(verified)
            except:
                pass
        try:
            await interaction.user.edit(nick=None)
        except:
            pass

        await interaction.response.send_message(embed=discord.Embed(
            title="🔓 Scollegato", description=f"**{old}** scollegato.",
            color=discord.Color.orange()
        ), ephemeral=True)


# ═══════════════════════════════════════════
#  EVENTI
# ═══════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"✅ {bot.user} — {len(bot.guilds)} server")
    bot.add_view(LinkUnlinkView())
    try:
        synced = await bot.tree.sync()
        print(f"   Comandi: {len(synced)}")
    except Exception as e:
        print(f"   Sync: {e}")
    if not auto_update_ranks.is_running():
        auto_update_ranks.start()
    if not daily_leaderboard.is_running():
        daily_leaderboard.start()


@bot.event
async def on_member_join(member: discord.Member):
    if member.bot:
        return
    ch = discord.utils.get(member.guild.text_channels, name="🔗-collega-account")
    if ch:
        await ch.send(
            f"👋 {member.mention} Clicca il bottone qui sopra per collegare il tuo account!",
            delete_after=60
        )


# ═══════════════════════════════════════════
#  AUTOCOMPLETE
# ═══════════════════════════════════════════

async def embark_autocomplete(interaction: discord.Interaction, current: str):
    if len(current) < 2:
        return []
    results = await api.autocomplete_search(current, max_results=25)
    choices = []
    for r in results:
        label = f"{r['name']} — {r['leagueIta']} ({r['rankScore']:,} RS)"
        if len(label) > 100:
            label = label[:97] + "..."
        choices.append(app_commands.Choice(name=label, value=r["name"]))
    return choices[:25]


async def rank_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=r, value=r) for r in VALID_RANKS if current.lower() in r.lower()]


# ═══════════════════════════════════════════
#  SLASH COMMANDS
# ═══════════════════════════════════════════

@bot.tree.command(name="link", description="Collega il tuo account The Finals")
@app_commands.describe(embark_name="Inizia a digitare il tuo nome Embark...")
@app_commands.autocomplete(embark_name=embark_autocomplete)
async def link_cmd(interaction: discord.Interaction, embark_name: str):
    await interaction.response.defer(ephemeral=True)

    if "#" not in embark_name:
        await interaction.followup.send(embed=discord.Embed(
            title="❌", description="Serve il #codice", color=discord.Color.red()
        ), ephemeral=True)
        return

    player = await api.search_player(embark_name)
    if player is None:
        final, errs = await assign_rank(
            interaction.guild, interaction.user, "Unranked", embark_name, {"name": embark_name}
        )
        desc = f"**{embark_name}** — Unranked\nSi aggiornerà automaticamente!"
        if errs:
            desc += "\n\n⚠️ " + "\n".join(errs)
        await interaction.followup.send(embed=discord.Embed(
            title="✅ Collegato", description=desc, color=discord.Color(LEAGUE_COLORS["Unranked"])
        ), ephemeral=True)
        return

    league_ita = player.get("leagueIta", "Bronzo")
    final, errs = await assign_rank(
        interaction.guild, interaction.user, league_ita, embark_name, player
    )
    api_name = player.get("name", embark_name)
    rs = player.get("rankScore", 0)
    desc = f"**{api_name}** — {final} ({rs:,} RS)"
    if errs:
        desc += "\n\n⚠️ " + "\n".join(errs)
    await interaction.followup.send(embed=discord.Embed(
        title="✅ Collegato", description=desc,
        color=discord.Color(LEAGUE_COLORS.get(final, 0x808080))
    ), ephemeral=True)

    lb = await get_leaderboard_channel(interaction.guild)
    if lb:
        await lb.send(embed=discord.Embed(
            title="🆕 Nuovo giocatore!",
            description=f"{interaction.user.mention} → **{api_name}** — {final} ({rs:,} RS)",
            color=discord.Color(LEAGUE_COLORS.get(final, 0x808080))
        ))


@bot.tree.command(name="unlink", description="Scollega il tuo account")
async def unlink_cmd(interaction: discord.Interaction):
    saved = db.get_player(interaction.user.id, interaction.guild.id)
    if not saved:
        await interaction.response.send_message("Non collegato.", ephemeral=True)
        return
    db.unlink_player(interaction.user.id, interaction.guild.id)
    for r in interaction.user.roles:
        if r.name in LEAGUE_ORDER:
            try:
                await interaction.user.remove_roles(r)
            except:
                pass
    try:
        await interaction.user.edit(nick=None)
    except:
        pass
    await interaction.response.send_message("🔓 Scollegato.", ephemeral=True)


# ═══════════════════════════════════════════
#  COMANDI ADMIN
# ═══════════════════════════════════════════

@bot.tree.command(name="setrank", description="[Admin] Assegna rank manuale")
@app_commands.describe(user="Utente", rank="Rank")
@app_commands.autocomplete(rank=rank_autocomplete)
@app_commands.checks.has_permissions(administrator=True)
async def setrank_cmd(interaction: discord.Interaction, user: discord.Member, rank: str):
    if rank not in VALID_RANKS:
        await interaction.response.send_message(f"❌ Scegli tra: {', '.join(VALID_RANKS)}", ephemeral=True)
        return

    saved = db.get_player(user.id, interaction.guild.id)
    if not saved:
        await interaction.response.send_message(f"❌ {user.mention} non collegato.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    for r in user.roles:
        if r.name in LEAGUE_ORDER:
            try:
                await user.remove_roles(r)
            except:
                pass

    new_role = await get_or_create_rank_role(interaction.guild, rank)
    try:
        await user.add_roles(new_role, reason=f"Admin: {rank}")
    except discord.Forbidden:
        await interaction.followup.send("❌ Gerarchia ruoli.", ephemeral=True)
        return

    db.set_manual_rank(user.id, interaction.guild.id, rank)
    db.update_league(user.id, interaction.guild.id, rank)

    await interaction.followup.send(embed=discord.Embed(
        title="✅ Rank manuale",
        description=f"{user.mention} → **{rank}**\n\nSe l'API trova un rank reale, si aggiorna automaticamente.",
        color=discord.Color(LEAGUE_COLORS.get(rank, 0x808080))
    ), ephemeral=True)

    lb = await get_leaderboard_channel(interaction.guild)
    if lb:
        await lb.send(embed=discord.Embed(
            title="🔧 Rank manuale",
            description=f"{user.mention} → **{rank}** (admin)",
            color=discord.Color(LEAGUE_COLORS.get(rank, 0x808080))
        ))


@bot.tree.command(name="removerank", description="[Admin] Rimuove rank manuale")
@app_commands.describe(user="Utente")
@app_commands.checks.has_permissions(administrator=True)
async def removerank_cmd(interaction: discord.Interaction, user: discord.Member):
    saved = db.get_player(user.id, interaction.guild.id)
    if not saved:
        await interaction.response.send_message(f"❌ {user.mention} non collegato.", ephemeral=True)
        return
    db.set_manual_rank(user.id, interaction.guild.id, None)
    await interaction.response.send_message(f"✅ Rank manuale rimosso da {user.mention}.", ephemeral=True)


# ═══════════════════════════════════════════
#  COMANDI INFO (EPHEMERAL — solo chi li usa li vede)
# ═══════════════════════════════════════════

@bot.tree.command(name="rank", description="Mostra rank")
@app_commands.describe(user="Utente (opzionale)")
async def rank_cmd(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    await interaction.response.defer(ephemeral=True)
    target = user or interaction.user
    saved = db.get_player(target.id, interaction.guild.id)
    if not saved:
        await interaction.followup.send(embed=discord.Embed(
            title="❌", description="Non collegato.", color=discord.Color.red()
        ), ephemeral=True)
        return

    player = await api.search_player(saved["embark_name"])
    if player:
        db.link_player(target.id, interaction.guild.id, saved["embark_name"], player)
    else:
        player = saved.get("data", {})

    league_ita = player.get("leagueIta", saved.get("current_league", "?"))
    rs = player.get("rankScore", 0)
    manual = saved.get("manual_rank")
    color = LEAGUE_COLORS.get(league_ita, 0x808080)

    embed = discord.Embed(
        title=f"📊 {player.get('name', saved['embark_name'])}", color=discord.Color(color)
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🏆 Posizione", value=f"#{player.get('rank', '?')}", inline=True)
    embed.add_field(name="🎖️ Rank", value=f"**{league_ita}**", inline=True)
    embed.add_field(name="📊 RS", value=f"**{rs:,}**", inline=True)
    embed.add_field(name="📋 Sub", value=player.get("subLeague", "?"), inline=True)
    if manual:
        embed.add_field(name="🔧 Manuale", value=f"**{manual}**", inline=True)

    change = player.get("change", 0)
    if change > 0:
        embed.add_field(name="📈", value=f"+{change}", inline=True)
    elif change < 0:
        embed.add_field(name="📉", value=f"{change}", inline=True)

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="search", description="Cerca nella leaderboard")
@app_commands.describe(embark_name="Nome Embark")
@app_commands.autocomplete(embark_name=embark_autocomplete)
async def search_cmd(interaction: discord.Interaction, embark_name: str):
    await interaction.response.defer(ephemeral=True)
    player = await api.search_player(embark_name)
    if not player:
        await interaction.followup.send(embed=discord.Embed(
            title="❌ Non trovato", color=discord.Color.red()
        ), ephemeral=True)
        return
    l = player.get("leagueIta", "?")
    embed = discord.Embed(title=f"🎮 {player.get('name','?')}", color=discord.Color(LEAGUE_COLORS.get(l, 0x808080)))
    embed.add_field(name="🏆", value=f"#{player.get('rank',0)}", inline=True)
    embed.add_field(name="🎖️", value=l, inline=True)
    embed.add_field(name="📊", value=f"{player.get('rankScore',0):,} RS", inline=True)
    embed.add_field(name="📋", value=player.get("subLeague", "?"), inline=True)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="leaderboard", description="Classifica server")
async def leaderboard_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    linked = db.get_all_players(interaction.guild.id)
    if not linked:
        await interaction.followup.send(embed=discord.Embed(
            title="📋 Vuota", color=discord.Color.greyple()
        ), ephemeral=True)
        return

    updated = []
    for lp in linked:
        player = await api.search_player(lp["embark_name"])
        if player:
            db.link_player(lp["discord_id"], interaction.guild.id, lp["embark_name"], player)
            member = interaction.guild.get_member(lp["discord_id"])
            updated.append({"member": member, "data": player})
        await asyncio.sleep(0.5)

    updated.sort(key=lambda x: x["data"].get("rankScore", 0), reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, p in enumerate(updated[:15]):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        d = p["data"]
        mention = p["member"].mention if p["member"] else d.get("name", "?")
        lines.append(
            f"{medal} **{d.get('name','?')}** — {d.get('leagueIta','?')} — "
            f"{d.get('rankScore',0):,} RS\n   └ {mention}"
        )

    await interaction.followup.send(embed=discord.Embed(
        title=f"🏆 {interaction.guild.name}",
        description="\n".join(lines) or "Vuota",
        color=discord.Color.gold(), timestamp=datetime.now(timezone.utc)
    ), ephemeral=True)


@bot.tree.command(name="ruby", description="Soglia Ruby")
async def ruby_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    t = await api.get_ruby_threshold()
    embed = discord.Embed(title="💎 Ruby — Top 500", color=discord.Color(LEAGUE_COLORS["Ruby"]))
    if t:
        embed.description = f"#500: **{t.get('name','?')}** — **{t.get('rankScore',0):,}** RS"
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="stats", description="Statistiche")
async def stats_cmd(interaction: discord.Interaction):
    linked = db.get_all_players(interaction.guild.id)
    counts = {}
    for lp in linked:
        l = lp.get("current_league")
        if l:
            counts[l] = counts.get(l, 0) + 1
    embed = discord.Embed(title=f"📊 {interaction.guild.name}", color=discord.Color.blue())
    embed.add_field(name="Membri", value=str(interaction.guild.member_count), inline=True)
    embed.add_field(name="Verificati", value=str(len(linked)), inline=True)
    if counts:
        embed.add_field(name="Rank", value="\n".join(
            f"{l}: **{counts[l]}**" for l in LEAGUE_ORDER if counts.get(l, 0) > 0
        ), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="setup", description="[Admin] Setup: ruoli + canali")
@app_commands.checks.has_permissions(administrator=True)
async def setup_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    created = []
    for league in LEAGUE_ORDER:
        role = await get_or_create_rank_role(interaction.guild, league)
        created.append(role.mention)
    verified = await get_or_create_verified_role(interaction.guild)

    link_ch = discord.utils.get(interaction.guild.text_channels, name="🔗-collega-account")
    if not link_ch:
        link_ch = await interaction.guild.create_text_channel(
            name="🔗-collega-account",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(send_messages=False, read_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True),
            },
            topic="Collega o scollega il tuo account The Finals"
        )

    await link_ch.purge(limit=10)
    await link_ch.send(
        embed=discord.Embed(
            title="🎮 Collega il tuo account The Finals",
            description=(
                "🔗 **Collega** — Inserisci il tuo nome Embark. Nickname e rank automatici.\n\n"
                "🔓 **Scollega** — Rimuove collegamento, nickname e ruoli.\n\n"
                "Se non sei in classifica ricevi **Unranked**. Un admin può assegnarti un rank.\n"
                "L'aggiornamento rank avviene ogni ora. La classifica si aggiorna ogni giorno a mezzanotte."
            ),
            color=discord.Color.blue()
        ),
        view=LinkUnlinkView()
    )

    lb_ch = discord.utils.get(interaction.guild.text_channels, name="📊-leaderboard")
    if not lb_ch:
        lb_ch = await interaction.guild.create_text_channel(
            name="📊-leaderboard",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(send_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(send_messages=True),
            },
            topic="Classifica giornaliera e aggiornamenti rank"
        )
    db.update_guild_settings(interaction.guild.id, leaderboard_channel_id=lb_ch.id)

    embed = discord.Embed(title="⚙️ Setup completato!", color=discord.Color.green())
    embed.add_field(name="Ruoli", value="\n".join(created) + f"\n{verified.mention}", inline=False)
    embed.add_field(name="Canali", value=f"{link_ch.mention}\n{lb_ch.mention}", inline=False)
    embed.add_field(name="⚠️", value="Sposta il ruolo del bot **sopra** ai ruoli rank!", inline=False)
    embed.add_field(name="Admin", value="`/setrank @utente Rank`\n`/removerank @utente`", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="updateranks", description="[Admin] Forza aggiornamento")
@app_commands.checks.has_permissions(administrator=True)
async def force_update_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    linked = db.get_all_players(interaction.guild.id)
    updated = 0
    changed = 0

    for lp in linked:
        try:
            member = interaction.guild.get_member(lp["discord_id"])
            if not member:
                continue
            player = await api.search_player(lp["embark_name"])
            old = lp.get("current_league")
            manual = lp.get("manual_rank")

            if player:
                api_rank = player.get("leagueIta", "Bronzo")
                if api_rank != "Unranked":
                    await assign_rank(interaction.guild, member, api_rank, lp["embark_name"], player)
                    if manual:
                        db.set_manual_rank(member.id, interaction.guild.id, None)
                else:
                    final = manual if manual else "Unranked"
                    await assign_rank(interaction.guild, member, final, lp["embark_name"], player)
            else:
                final = manual if manual else "Unranked"
                await assign_rank(interaction.guild, member, final, lp["embark_name"], {"name": lp["embark_name"]})

            updated += 1
            new = db.get_player(member.id, interaction.guild.id)
            if new and old != new.get("current_league"):
                changed += 1
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[ERROR] {lp['embark_name']}: {e}")

    await interaction.followup.send(embed=discord.Embed(
        title="🔄 Completato",
        description=f"Controllati: **{updated}** — Cambiati: **{changed}**",
        color=discord.Color.green()
    ), ephemeral=True)


@bot.tree.command(name="setchannel", description="[Admin] Canale leaderboard")
@app_commands.describe(channel="Canale")
@app_commands.checks.has_permissions(administrator=True)
async def setchannel_cmd(interaction: discord.Interaction, channel: discord.TextChannel):
    db.update_guild_settings(interaction.guild.id, leaderboard_channel_id=channel.id)
    await interaction.response.send_message(f"✅ Leaderboard → {channel.mention}", ephemeral=True)


@bot.tree.command(name="help", description="Comandi")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Comandi", color=discord.Color.blue())
    embed.add_field(name="👤", value="`/link` — Collega\n`/unlink` — Scollega", inline=False)
    embed.add_field(name="📊", value="`/rank` `/search` `/leaderboard` `/ruby` `/stats`\n*(visibili solo a te)*", inline=False)
    embed.add_field(name="⚙️ Admin", value=(
        "`/setup` — Setup iniziale\n"
        "`/setrank @utente Rank` — Rank manuale\n"
        "`/removerank @utente` — Rimuovi manuale\n"
        "`/updateranks` — Aggiorna ora\n"
        "`/setchannel` — Canale leaderboard"
    ), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ═══════════════════════════════════════════
#  TASK 1: AGGIORNAMENTO RANK — OGNI ORA
#  (aggiorna ruoli e nickname, NO leaderboard)
# ═══════════════════════════════════════════

@tasks.loop(hours=1)
async def auto_update_ranks():
    print(f"🔄 Rank update — {datetime.now(timezone.utc).strftime('%H:%M')} UTC")

    for guild in bot.guilds:
        linked = db.get_all_players(guild.id)
        lb = await get_leaderboard_channel(guild)
        changes = []

        for lp in linked:
            try:
                member = guild.get_member(lp["discord_id"])
                if not member:
                    continue

                player = await api.search_player(lp["embark_name"])
                old = lp.get("current_league")
                manual = lp.get("manual_rank")

                if player:
                    api_rank = player.get("leagueIta", "Bronzo")
                    if api_rank != "Unranked":
                        final = api_rank
                        if manual:
                            db.set_manual_rank(member.id, guild.id, None)
                    else:
                        final = manual if manual else "Unranked"
                else:
                    player = {"name": lp["embark_name"]}
                    final = manual if manual else "Unranked"

                await assign_rank(guild, member, final, lp["embark_name"], player)

                if old and old != final:
                    old_idx = LEAGUE_ORDER.index(old) if old in LEAGUE_ORDER else 99
                    new_idx = LEAGUE_ORDER.index(final) if final in LEAGUE_ORDER else 99
                    changes.append({
                        "member": member, "old": old, "new": final,
                        "rs": player.get("rankScore", 0),
                        "up": new_idx < old_idx,
                    })

                await asyncio.sleep(2)
            except Exception as e:
                print(f"[ERROR] {lp.get('embark_name')}: {e}")

        # Posta solo le promozioni/retrocessioni, NON la leaderboard
        if changes and lb:
            for c in changes:
                title = "⬆️ Promozione!" if c["up"] else "⬇️ Retrocessione"
                verb = "salito" if c["up"] else "sceso"
                color = LEAGUE_COLORS.get(c["new"], 0x808080)
                await lb.send(embed=discord.Embed(
                    title=title,
                    description=f"{c['member'].mention} {verb}: **{c['old']}** → **{c['new']}** ({c['rs']:,} RS)",
                    color=discord.Color(color)
                ))


@auto_update_ranks.before_loop
async def before_rank_update():
    await bot.wait_until_ready()


# ═══════════════════════════════════════════
#  TASK 2: LEADERBOARD GIORNALIERA — OGNI GIORNO ALLE 00:00 UTC
# ═══════════════════════════════════════════

@tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
async def daily_leaderboard():
    print(f"📊 Leaderboard giornaliera — {datetime.now(timezone.utc).strftime('%d/%m/%Y')}")

    for guild in bot.guilds:
        lb = await get_leaderboard_channel(guild)
        if not lb:
            continue

        linked = db.get_all_players(guild.id)
        players = []

        for lp in linked:
            d = lp.get("data", {})
            if d:
                players.append({
                    "name": d.get("name", lp["embark_name"]),
                    "rs": d.get("rankScore", 0),
                    "pos": d.get("rank", 99999),
                    "league": lp.get("current_league", d.get("leagueIta", "?")),
                })

        players.sort(key=lambda x: x["rs"], reverse=True)
        if not players:
            continue

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, p in enumerate(players[:20]):
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(f"{medal} **{p['name']}** — {p['league']} — {p['rs']:,} RS")

        today = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        await lb.send(embed=discord.Embed(
            title=f"🏆 Classifica giornaliera — {today}",
            description="\n".join(lines),
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        ))


@daily_leaderboard.before_loop
async def before_daily_lb():
    await bot.wait_until_ready()


# ═══════════════════════════════════════════
#  ERROR HANDLER
# ═══════════════════════════════════════════

@bot.tree.error
async def on_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)
    else:
        print(f"[ERROR] {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Errore.", ephemeral=True)


if __name__ == "__main__":
    token = Config.BOT_TOKEN
    if not token or token == "IL_TUO_TOKEN_QUI":
        print("❌ Token mancante")
        exit(1)
    bot.run(token)
