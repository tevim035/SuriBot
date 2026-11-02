"""
Bot de Discord que analisa o sentimento de cada mensagem (em português)
e reage com um emoji. Também guarda estatísticas por servidor.

Comandos:
  !sentimento   -> mostra o resumo de sentimentos do servidor
  !analisar <texto> -> analisa um texto específico e mostra as probabilidades
"""

import asyncio
import os
from collections import defaultdict

import discord
from discord.ext import commands
from dotenv import load_dotenv
from pysentimiento import create_analyzer

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Só reage se o modelo tiver pelo menos essa confiança (0 a 1)
CONFIANCA_MINIMA = 0.60

# Emoji para cada sentimento (POS = positivo, NEG = negativo, NEU = neutro)
EMOJIS = {"POS": "😊", "NEG": "😠", "NEU": "😐"}
NOMES = {"POS": "Positivo", "NEG": "Negativo", "NEU": "Neutro"}

# Reagir também às mensagens neutras? (pode poluir o chat)
REAGIR_NEUTRO = False

print("Carregando o modelo de sentimentos (a primeira vez demora um pouco)...")
analyzer = create_analyzer(task="sentiment", lang="pt")
print("Modelo carregado!")

# Estatísticas em memória: {id_do_servidor: {"POS": n, "NEG": n, "NEU": n}}
# Obs.: são perdidas quando o bot reinicia.
estatisticas = defaultdict(lambda: {"POS": 0, "NEG": 0, "NEU": 0})

intents = discord.Intents.default()
intents.message_content = True  # precisa estar ativado também no Developer Portal

bot = commands.Bot(command_prefix="!", intents=intents)


async def analisar(texto: str):
    """Roda o modelo fora do loop principal para não travar o bot."""
    resultado = await asyncio.to_thread(analyzer.predict, texto)
    return resultado.output, resultado.probas


@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user} (id: {bot.user.id})")


@bot.event
async def on_message(message: discord.Message):
    # Ignora mensagens de bots (inclusive dele mesmo)
    if message.author.bot:
        return

    # Deixa os comandos (!sentimento etc.) funcionarem normalmente
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    texto = message.content.strip()
    if not texto:
        return  # mensagem só com imagem/arquivo

    sentimento, probas = await analisar(texto)
    confianca = probas[sentimento]

    if message.guild:
        estatisticas[message.guild.id][sentimento] += 1

    print(f"[{message.author}] {texto[:60]!r} -> {sentimento} ({confianca:.0%})")

    if confianca < CONFIANCA_MINIMA:
        return
    if sentimento == "NEU" and not REAGIR_NEUTRO:
        return

    try:
        await message.add_reaction(EMOJIS[sentimento])
    except discord.Forbidden:
        print("Sem permissão para adicionar reações neste canal.")


@bot.command(name="sentimento")
async def resumo(ctx: commands.Context):
    """Mostra o resumo de sentimentos do servidor."""
    if not ctx.guild:
        await ctx.send("Esse comando só funciona em servidores.")
        return

    dados = estatisticas[ctx.guild.id]
    total = sum(dados.values())
    if total == 0:
        await ctx.send("Ainda não analisei nenhuma mensagem por aqui.")
        return

    embed = discord.Embed(
        title="📊 Clima do servidor",
        description=f"{total} mensagens analisadas desde que liguei",
        color=discord.Color.blurple(),
    )
    for chave in ("POS", "NEU", "NEG"):
        pct = dados[chave] / total
        barra = "█" * round(pct * 20)
        embed.add_field(
            name=f"{EMOJIS[chave]} {NOMES[chave]}",
            value=f"`{barra:<20}` {pct:.0%} ({dados[chave]})",
            inline=False,
        )
    await ctx.send(embed=embed)


@bot.command(name="analisar")
async def analisar_texto(ctx: commands.Context, *, texto: str):
    """Analisa um texto específico: !analisar estou muito feliz hoje"""
    sentimento, probas = await analisar(texto)
    linhas = [f"{EMOJIS[k]} {NOMES[k]}: {probas[k]:.0%}" for k in ("POS", "NEU", "NEG")]
    await ctx.send(f"**Resultado: {NOMES[sentimento]}**\n" + "\n".join(linhas))


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Defina DISCORD_TOKEN no arquivo .env")
    bot.run(TOKEN)