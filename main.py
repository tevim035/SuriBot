"""
Bot de Discord que identifica as EMOÇÕES de cada mensagem (em português).

Usa as 5 emoções principais: Alegria, Tristeza, Medo, Raiva e Nojo (ou Neutro).
O modelo detecta 28 emoções e cada uma entra num desses grupos
(ex.: gratidão e diversão contam como Alegria; decepção conta como Tristeza).
Uma mensagem pode ter mais de uma emoção ao mesmo tempo.

Também conversa (com uma IA que roda no próprio PC, pelo Ollama) quando é marcado
(@bot) ou recebe mensagem no privado, levando em conta a emoção detectada.

Comandos:
  !emocoes                 -> resumo das emoções do servidor
  !emocoes @usuario        -> resumo das emoções de um usuário
  !minhas                  -> resumo das suas emoções (em todos os servidores e no privado)
  !grafico [@usuario] [dias] -> gráfico das emoções e de como mudaram dia a dia
  !historico [@usuario] [quantidade] -> analisa as mensagens antigas do canal
  !analisar <texto>        -> mostra a força de cada emoção num texto
  !esquecer                -> apaga a memória da conversa neste canal
  !apagardados             -> apaga as suas estatísticas de emoções
"""

import asyncio
import io
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Optional

import discord
import matplotlib
import ollama
from discord.ext import commands
from dotenv import load_dotenv
from pysentimiento import create_analyzer

matplotlib.use("Agg")  # desenha os gráficos em imagem, sem abrir janela
import matplotlib.pyplot as plt  # noqa: E402

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

# Probabilidade mínima (0 a 1) para considerar que uma emoção está presente.
CONFIANCA_MINIMA = 0.30

# Quantas emoções no máximo atribuir a uma mensagem.
MAX_EMOCOES = 2

# Reagir na mensagem com o emoji da emoção principal?
REAGIR = True

# As 5 emoções principais (mais Neutro): nome, emoji e cor nos gráficos.
# As cores foram testadas no fundo escuro do Discord, inclusive para daltonismo
# (com o nome escrito ao lado, como os gráficos fazem).
EMOCOES = {
    "alegria":  ("Alegria",  "😄", "#B28838"),
    "tristeza": ("Tristeza", "😢", "#3183BF"),
    "medo":     ("Medo",     "😨", "#B46CF2"),
    "raiva":    ("Raiva",    "😡", "#EA5365"),
    "nojo":     ("Nojo",     "🤢", "#4A8D46"),
    "neutro":   ("Neutro",   "😐", "#80848E"),
}

# Em qual emoção principal entra cada uma das emoções que o modelo detecta.
# Emoções do modelo que não estiverem aqui contam como Neutro.
GRUPOS = {
    "joy": "alegria", "amusement": "alegria", "excitement": "alegria",
    "gratitude": "alegria", "love": "alegria", "optimism": "alegria",
    "pride": "alegria", "relief": "alegria", "admiration": "alegria",
    "approval": "alegria", "caring": "alegria", "desire": "alegria",
    "sadness": "tristeza", "grief": "tristeza", "disappointment": "tristeza",
    "remorse": "tristeza", "embarrassment": "tristeza",
    "fear": "medo", "nervousness": "medo",
    "anger": "raiva", "annoyance": "raiva", "disapproval": "raiva",
    "disgust": "nojo",
    "neutral": "neutro", "others": "neutro", "surprise": "neutro",
    "curiosity": "neutro", "confusion": "neutro", "realization": "neutro",
}

# Emoções tratadas como "nenhuma emoção" (o bot não reage a elas).
NEUTRAS = {"neutro"}

# Máximo de mensagens antigas que o !historico lê de uma vez.
LIMITE_HISTORICO = 2000

# --- Conversa com IA -------------------------------------------------------

# O bot conversa quando é marcado (@bot) ou no privado? (precisa do Ollama aberto)
CONVERSAR = True

# Modelo do Ollama usado na conversa (baixe outros com: ollama pull <nome>).
MODELO_IA = "gemma3:4b"

# Quantas mensagens de cada canal o bot lembra na conversa.
HISTORICO_MAX = 20

# Personalidade do bot. Pode mudar à vontade.
PERSONALIDADE = """Você é a Suri e está batendo papo com amigos num servidor de Discord brasileiro.
Converse como uma pessoa normal conversa no chat, não como um assistente:
- Escreva em português do Brasil informal, do jeito que se digita no chat: frases curtas,
  "vc", "tb", "kkkk", "nossa", "pô" quando cair bem, sem exagerar nas gírias.
- Na maioria das vezes responda com uma ou duas frases. Só escreva mais se a pessoa pedir
  uma explicação ou contar algo que pede uma resposta maior.
- Nada de listas, tópicos, títulos ou negrito. Emoji só de vez em quando.
- Não comece com "Claro!", "Ótima pergunta!" nem termine oferecendo ajuda
  ("Posso ajudar em algo mais?"). Não fique resumindo o que a pessoa disse.
- Tenha opinião, gostos e senso de humor. Pode discordar, brincar e zoar de leve.
- Demonstre interesse de verdade: às vezes faça uma pergunta de volta, como um amigo faria.
- Quando alguém estiver triste ou mal, seja acolhedora e ouça antes de dar conselho.
- Se perguntarem a sério se você é um bot ou uma IA, diga a verdade, de um jeito leve.

Cada mensagem chega no formato
"Nome [emoções desta mensagem] {histórico: emoções de todas as mensagens dele}: texto".
Esse formato é só para você: nunca escreva desse jeito. As emoções (Alegria, Tristeza,
Medo, Raiva, Nojo ou Neutro) são detectadas automaticamente pela mensagem e podem errar.
Use-as para ajustar o seu jeito de responder, como uma pessoa que percebe o humor do amigo,
sem dizer que detectou nada:
- Alegria: entre na vibe, comemore junto;
- Tristeza: fique mais calma e acolhedora, pergunte o que houve;
- Medo: tranquilize;
- Raiva: não discuta nem dê sermão, mostre que entendeu o motivo;
- Nojo: concorde com a reação ou brinque com ela, sem julgar;
- Neutro: converse normalmente.
Se o texto contradisser a emoção detectada (ironia, por exemplo), confie no texto.
Se perguntarem quantas mensagens tristes, felizes etc. mandaram, responda com o histórico
(e diga que os comandos !minhas e !grafico mostram o resumo completo)."""

# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

print("Carregando o modelo de emoções (a primeira vez demora um pouco)...")
analyzer = create_analyzer(task="emotion", lang="pt")
rotulos_modelo = sorted(analyzer.id2label.values())
print(f"Modelo carregado! Ele detecta {len(rotulos_modelo)} emoções, agrupadas em "
      + ", ".join(n for n, _, _ in EMOCOES.values()) + ".")

sem_grupo = [r for r in rotulos_modelo if r.lower() not in GRUPOS]
if sem_grupo:
    print("Emoções do modelo sem grupo (contam como Neutro):", ", ".join(sem_grupo))


def nome(emocao: str) -> str:
    return EMOCOES.get(emocao, (emocao, "", ""))[0]


def emoji(emocao: str) -> str:
    return EMOCOES.get(emocao, ("", "🔹", ""))[1]


def _forcas(probas: dict):
    """
    Junta as 28 emoções do modelo nas emoções principais.
    Retorna (emocoes_detectadas, todas_ordenadas)
      emocoes_detectadas: emoções acima da confiança mínima (máx. MAX_EMOCOES)
                          ou ["neutro"] se nenhuma apareceu
      todas_ordenadas:    lista [(emoção, força), ...] da maior para a menor
    """
    # A força de cada emoção principal é a da emoção mais forte do modelo que entra nela.
    forca = Counter({e: 0.0 for e in EMOCOES})
    for rotulo, p in probas.items():
        grupo = GRUPOS.get(rotulo.lower(), "neutro")
        forca[grupo] = max(forca[grupo], p)
    ordenadas = forca.most_common()

    detectadas = [
        e for e, p in ordenadas
        if p >= CONFIANCA_MINIMA and e not in NEUTRAS
    ][:MAX_EMOCOES]

    return (detectadas or ["neutro"]), ordenadas


def _classificar(texto: str):
    return _forcas(analyzer.predict(texto).probas)


def _classificar_varios(textos: list) -> list:
    return [_forcas(r.probas) for r in analyzer.predict(textos)]


async def classificar(texto: str):
    """Roda o modelo fora do loop principal para não travar o bot."""
    return await asyncio.to_thread(_classificar, texto)


# ---------------------------------------------------------------------------
# Conversa (IA local pelo Ollama)
# ---------------------------------------------------------------------------

ia = ollama.AsyncClient() if CONVERSAR else None

historico = defaultdict(list)   # {channel_id: [{"role": ..., "content": ...}, ...]}
travas = defaultdict(asyncio.Lock)  # uma resposta por vez em cada canal


async def gerar_resposta(canal_id: int, autor: discord.abc.User, texto: str, detectadas: list) -> str:
    async with travas[canal_id]:
        return await _gerar_resposta(canal_id, autor, texto, detectadas)


async def _gerar_resposta(canal_id: int, autor: discord.abc.User, texto: str, detectadas: list) -> str:
    emocoes = ", ".join(nome(e) for e in detectadas)
    estatisticas = resumo_texto(contar(usuario_id=autor.id))
    mensagens = historico[canal_id]
    mensagens.append({
        "role": "user",
        "content": f"{autor.display_name} [{emocoes}] {{histórico: {estatisticas}}}: {texto}",
    })

    try:
        resposta = await ia.chat(
            model=MODELO_IA,
            messages=[{"role": "system", "content": PERSONALIDADE}, *mensagens],
            keep_alive="1h",  # mantém o modelo carregado na placa de vídeo entre as mensagens
        )
    except Exception:
        mensagens.pop()
        raise

    texto_resposta = resposta.message.content.strip()
    # Modelos pequenos às vezes começam a resposta com o próprio nome.
    if texto_resposta.lower().startswith("suri:"):
        texto_resposta = texto_resposta[5:].strip()
    if not texto_resposta:
        mensagens.pop()
        return "Hmm, não consegui pensar numa resposta. Pode repetir?"

    mensagens.append({"role": "assistant", "content": texto_resposta})

    # Mantém só as últimas mensagens, começando sempre por uma do usuário.
    del mensagens[:-HISTORICO_MAX]
    while mensagens and mensagens[0]["role"] != "user":
        mensagens.pop(0)

    return texto_resposta


async def conversar(message: discord.Message, texto: str, detectadas: list):
    try:
        async with message.channel.typing():
            resposta = await gerar_resposta(message.channel.id, message.author, texto, detectadas)
    except ConnectionError:
        print("Não consegui falar com o Ollama. Ele está aberto?")
        await message.reply("Minha IA está desligada agora (o Ollama não está aberto no PC).")
        return
    except ollama.ResponseError as e:
        print(f"Erro do Ollama: {e.error}")
        if e.status_code == 404:
            print(f"O modelo não foi baixado. Rode: ollama pull {MODELO_IA}")
        await message.reply("Tive um problema para responder agora. Tenta de novo?")
        return

    # O Discord aceita no máximo 2000 caracteres por mensagem.
    partes = [resposta[i:i + 2000] for i in range(0, len(resposta), 2000)]
    await message.reply(partes[0])
    for parte in partes[1:]:
        await message.channel.send(parte)


# ---------------------------------------------------------------------------
# Estatísticas (salvas no arquivo emocoes.db: continuam depois de reiniciar)
# ---------------------------------------------------------------------------

# Guarda só a emoção principal de cada mensagem, nunca o texto.
banco = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "emocoes.db"))
banco.execute("""
    CREATE TABLE IF NOT EXISTS mensagens (
        id          INTEGER PRIMARY KEY,
        servidor_id INTEGER,            -- NULL quando a mensagem foi no privado
        usuario_id  INTEGER NOT NULL,
        emocao      TEXT NOT NULL,
        data        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- em UTC
        mensagem_id INTEGER             -- id da mensagem no Discord (evita contar 2 vezes)
    )
""")
# Bancos criados antes do !historico não têm a coluna mensagem_id.
if "mensagem_id" not in {c[1] for c in banco.execute("PRAGMA table_info(mensagens)")}:
    banco.execute("ALTER TABLE mensagens ADD COLUMN mensagem_id INTEGER")
banco.execute("CREATE INDEX IF NOT EXISTS idx_usuario ON mensagens (usuario_id)")
banco.execute("CREATE INDEX IF NOT EXISTS idx_servidor ON mensagens (servidor_id, usuario_id)")
banco.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_mensagem ON mensagens (mensagem_id)")
# Registros antigos guardavam as 28 emoções do modelo: converte para as 5 principais.
for _rotulo, _grupo in GRUPOS.items():
    banco.execute("UPDATE mensagens SET emocao = ? WHERE emocao = ?", (_grupo, _rotulo))
banco.commit()


def registrar(servidor_id, usuario_id: int, emocao: str, mensagem: discord.Message = None) -> bool:
    """Salva a emoção de uma mensagem. Retorna False se ela já estava salva."""
    cursor = banco.execute(
        "INSERT OR IGNORE INTO mensagens (servidor_id, usuario_id, emocao, mensagem_id, data) "
        "VALUES (?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))",
        (
            servidor_id, usuario_id, emocao,
            mensagem.id if mensagem else None,
            mensagem.created_at.strftime("%Y-%m-%d %H:%M:%S") if mensagem else None,
        ),
    )
    banco.commit()
    return cursor.rowcount > 0


def _filtros(servidor_id=None, usuario_id=None):
    filtros, valores = [], []
    if servidor_id is not None:
        filtros.append("servidor_id = ?")
        valores.append(servidor_id)
    if usuario_id is not None:
        filtros.append("usuario_id = ?")
        valores.append(usuario_id)
    return filtros, valores


def contar(servidor_id=None, usuario_id=None) -> Counter:
    """Quantas mensagens de cada emoção. Sem filtros, conta tudo."""
    filtros, valores = _filtros(servidor_id, usuario_id)
    onde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    linhas = banco.execute(
        f"SELECT emocao, COUNT(*) FROM mensagens {onde} GROUP BY emocao", valores
    )
    return Counter(dict(linhas))


def contar_por_dia(dias: int, servidor_id=None, usuario_id=None) -> dict:
    """{data: Counter(emoção)} dos últimos `dias` dias, no fuso horário do PC."""
    filtros, valores = _filtros(servidor_id, usuario_id)
    filtros.append("date(data, 'localtime') >= date('now', 'localtime', ?)")
    valores.append(f"-{dias - 1} days")
    linhas = banco.execute(
        "SELECT date(data, 'localtime') AS dia, emocao, COUNT(*) FROM mensagens "
        f"WHERE {' AND '.join(filtros)} GROUP BY dia, emocao",
        valores,
    )
    resultado = defaultdict(Counter)
    for dia, emocao, n in linhas:
        resultado[date.fromisoformat(dia)][emocao] = n
    return resultado


def apagar_usuario(usuario_id: int) -> int:
    apagadas = banco.execute("DELETE FROM mensagens WHERE usuario_id = ?", (usuario_id,)).rowcount
    banco.commit()
    return apagadas


def resumo_texto(contagem: Counter) -> str:
    """Ex.: 'Alegria 12, Tristeza 3, Neutro 20 (35 no total)'"""
    total = sum(contagem.values())
    partes = [f"{nome(e)} {contagem[e]}" for e in EMOCOES if contagem[e]]
    return f"{', '.join(partes)} ({total} no total)" if total else "nenhuma mensagem ainda"


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

# Cores do tema escuro do Discord.
FUNDO = "#313338"
TINTA = "#DBDEE1"         # texto principal
TINTA_FRACA = "#949BA4"   # texto secundário e eixos
GRADE = "#3F4147"


def gerar_grafico(titulo: str, contagem: Counter, diario: dict, dias: int) -> io.BytesIO:
    """
    Desenha uma imagem com:
      - em cima, quantas mensagens houve de cada emoção (barras com nome e número);
      - embaixo, um gráfico pequeno por emoção mostrando como ela mudou dia a dia.
    """
    total = sum(contagem.values())
    emocoes = list(EMOCOES)
    hoje = date.today()
    datas = [hoje - timedelta(days=i) for i in range(dias - 1, -1, -1)]

    fig = plt.figure(figsize=(10, 8.4), dpi=110, facecolor=FUNDO)
    grade = fig.add_gridspec(3, 3, height_ratios=[1.25, 1, 1], hspace=0.5, wspace=0.18,
                             left=0.1, right=0.97, top=0.88, bottom=0.06)
    fig.text(0.1, 0.95, titulo, color=TINTA, fontsize=16, fontweight="bold")
    fig.text(0.1, 0.915, f"{total} mensagens analisadas · evolução nos últimos {dias} dias",
             color=TINTA_FRACA, fontsize=10.5)

    # --- Total de cada emoção -------------------------------------------------
    ax = fig.add_subplot(grade[0, :], facecolor=FUNDO)
    valores = [contagem[e] for e in emocoes]
    posicoes = range(len(emocoes))
    ax.barh(posicoes, valores, height=0.62, color=[EMOCOES[e][2] for e in emocoes])
    ax.set_yticks(list(posicoes), [nome(e) for e in emocoes], color=TINTA, fontsize=11)
    ax.invert_yaxis()
    maior = max(valores) or 1
    for y, n in zip(posicoes, valores):
        pct = f" ({n / total:.0%})" if total else ""
        ax.text(n + maior * 0.01, y, f"{n}{pct}", va="center", color=TINTA_FRACA, fontsize=10)
    ax.set_xlim(0, maior * 1.15)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)
    for lado in ax.spines.values():
        lado.set_visible(False)

    # --- Evolução por dia: um gráfico pequeno por emoção, mesma escala ----------
    teto = max([diario.get(d, Counter())[e] for d in datas for e in emocoes] + [1])
    marcar = dias <= 14
    for i, e in enumerate(emocoes):
        ax = fig.add_subplot(grade[1 + i // 3, i % 3], facecolor=FUNDO)
        serie = [diario.get(d, Counter())[e] for d in datas]
        cor = EMOCOES[e][2]
        ax.plot(datas, serie, color=cor, linewidth=2, clip_on=False,
                marker="o" if marcar else None, markersize=4.5)
        ax.fill_between(datas, serie, color=cor, alpha=0.15, linewidth=0)
        ax.set_title(f"{nome(e)} · {sum(serie)}", color=TINTA, fontsize=11, loc="left", pad=6)
        ax.set_ylim(0, teto * 1.15)
        ax.set_xlim(datas[0], datas[-1])
        ax.set_xticks([datas[0], datas[len(datas) // 2], datas[-1]],
                      [d.strftime("%d/%m") for d in (datas[0], datas[len(datas) // 2], datas[-1])])
        ax.tick_params(colors=TINTA_FRACA, labelsize=8.5, length=0)
        if i % 3:
            ax.set_yticklabels([])
        ax.grid(axis="y", color=GRADE, linewidth=0.8)
        ax.set_axisbelow(True)
        for lado in ax.spines.values():
            lado.set_visible(False)

    imagem = io.BytesIO()
    fig.savefig(imagem, format="png", facecolor=FUNDO)
    plt.close(fig)
    imagem.seek(0)
    return imagem


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True  # também precisa estar ativado no Developer Portal

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user} (id: {bot.user.id})")
    if ia:
        asyncio.create_task(preparar_ia())


async def preparar_ia():
    """Carrega o modelo na placa de vídeo já ao ligar, para a 1ª resposta não demorar."""
    print(f"Preparando a IA de conversa ({MODELO_IA})...")
    try:
        await ia.generate(model=MODELO_IA, prompt="", keep_alive="1h")
        print("IA de conversa pronta!")
    except ConnectionError:
        print("AVISO: o Ollama não está aberto. Abra o Ollama para o bot conseguir conversar.")
    except ollama.ResponseError as e:
        print(f"AVISO: problema com a IA de conversa: {e.error}")
        if e.status_code == 404:
            print(f"Baixe o modelo rodando no terminal: ollama pull {MODELO_IA}")


def texto_da_mensagem(message: discord.Message) -> str:
    """Texto da mensagem sem a menção ao bot."""
    return (
        message.content
        .replace(f"<@{bot.user.id}>", "")
        .replace(f"<@!{bot.user.id}>", "")
        .strip()
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    marcado = message.guild is None or bot.user in message.mentions
    texto = texto_da_mensagem(message)
    if not texto:
        if CONVERSAR and marcado and not message.attachments:
            texto = "oi"  # só marcou o bot
        else:
            return  # só imagem/arquivo

    detectadas, ordenadas = await classificar(texto)
    principal = detectadas[0]

    registrar(message.guild.id if message.guild else None, message.author.id, principal, message)

    top = ", ".join(f"{nome(e)} {p:.0%}" for e, p in ordenadas[:3])
    print(f"[{message.author}] {texto[:60]!r} -> {nome(principal).upper()}  ({top})")

    if REAGIR and principal not in NEUTRAS:
        try:
            await message.add_reaction(emoji(principal))
        except (discord.Forbidden, discord.HTTPException):
            print("Não consegui adicionar a reação neste canal.")

    if ia and marcado:
        await conversar(message, texto, detectadas)


def _embed_resumo(titulo: str, contagem: Counter) -> discord.Embed:
    total = sum(contagem.values())
    embed = discord.Embed(
        title=titulo,
        description=f"{total} mensagens analisadas",
        color=discord.Color.blurple(),
    )
    linhas = []
    for e in EMOCOES:
        n = contagem[e]
        pct = n / total
        barra = "█" * (max(1, round(pct * 15)) if n else 0)
        linhas.append(f"{emoji(e)} **{nome(e)}** `{barra:<15}` {pct:.0%} ({n})")
    embed.add_field(name="Emoções", value="\n".join(linhas), inline=False)
    embed.set_footer(text="Use !grafico para ver como as emoções mudaram dia a dia")
    return embed


@bot.command(name="emocoes", aliases=["emoções"])
async def resumo(ctx: commands.Context, membro: discord.Member = None):
    """!emocoes  ou  !emocoes @usuario"""
    if not ctx.guild:
        await minhas(ctx)  # no privado, mostra as suas
        return

    if membro:
        contagem = contar(servidor_id=ctx.guild.id, usuario_id=membro.id)
        titulo = f"🧠 Emoções de {membro.display_name}"
    else:
        contagem = contar(servidor_id=ctx.guild.id)
        titulo = "🧠 Emoções do servidor"

    if not contagem:
        await ctx.send("Ainda não analisei nenhuma mensagem para isso.")
        return
    await ctx.send(embed=_embed_resumo(titulo, contagem))


@bot.command(name="minhas", aliases=["eu"])
async def minhas(ctx: commands.Context):
    """!minhas  -> suas emoções em todos os servidores e no privado"""
    contagem = contar(usuario_id=ctx.author.id)
    if not contagem:
        await ctx.send("Ainda não analisei nenhuma mensagem sua.")
        return
    await ctx.send(embed=_embed_resumo(f"🧠 Suas emoções, {ctx.author.display_name}", contagem))


@bot.command(name="grafico", aliases=["gráfico"])
async def grafico(ctx: commands.Context, membro: Optional[discord.Member] = None, dias: int = 30):
    """!grafico  ou  !grafico @usuario  ou  !grafico @usuario 7"""
    dias = max(2, min(dias, 365))
    if not ctx.guild:
        filtro = {"usuario_id": ctx.author.id}
        titulo = f"Emoções de {ctx.author.display_name}"
    elif membro:
        filtro = {"servidor_id": ctx.guild.id, "usuario_id": membro.id}
        titulo = f"Emoções de {membro.display_name}"
    else:
        filtro = {"servidor_id": ctx.guild.id}
        titulo = f"Emoções do servidor {ctx.guild.name}"

    contagem = contar(**filtro)
    if not contagem:
        await ctx.send("Ainda não analisei nenhuma mensagem para isso. "
                       "Dica: `!historico` analisa as mensagens antigas do canal.")
        return

    async with ctx.typing():
        imagem = await asyncio.to_thread(
            gerar_grafico, titulo, contagem, contar_por_dia(dias, **filtro), dias
        )
    await ctx.send(resumo_texto(contagem), file=discord.File(imagem, "emocoes.png"))


@bot.command(name="historico", aliases=["histórico"])
async def historico_canal(ctx: commands.Context, membro: Optional[discord.Member] = None,
                          quantidade: int = 300):
    """!historico  ou  !historico 1000  ou  !historico @usuario 500"""
    if ctx.guild and not ctx.author.guild_permissions.manage_messages:
        await ctx.send("Só quem pode gerenciar mensagens no servidor pode usar o `!historico`.")
        return

    quantidade = max(1, min(quantidade, LIMITE_HISTORICO))
    de_quem = f" de {membro.display_name}" if membro else ""
    aviso = await ctx.send(f"🔎 Lendo as últimas {quantidade} mensagens do canal{de_quem}...")

    mensagens = []
    try:
        async for msg in ctx.channel.history(limit=quantidade, before=ctx.message):
            if msg.author.bot or msg.content.startswith(bot.command_prefix):
                continue
            if membro and msg.author.id != membro.id:
                continue
            if texto_da_mensagem(msg):
                mensagens.append(msg)
    except discord.Forbidden:
        await aviso.edit(content="Não tenho permissão para ler o histórico deste canal "
                                 "(preciso de **Ler histórico de mensagens**).")
        return

    if not mensagens:
        await aviso.edit(content="Não achei mensagens para analisar.")
        return

    await aviso.edit(content=f"🧠 Analisando {len(mensagens)} mensagens{de_quem}...")
    contagem, novas = Counter(), 0
    servidor_id = ctx.guild.id if ctx.guild else None
    for i in range(0, len(mensagens), 32):  # em lotes, para ser mais rápido
        lote = mensagens[i:i + 32]
        resultados = await asyncio.to_thread(_classificar_varios, [texto_da_mensagem(m) for m in lote])
        for msg, (detectadas, _) in zip(lote, resultados):
            contagem[detectadas[0]] += 1
            novas += registrar(servidor_id, msg.author.id, detectadas[0], msg)

    ja_tinha = len(mensagens) - novas
    detalhe = f" ({ja_tinha} já estavam salvas e não foram contadas de novo)" if ja_tinha else ""
    await aviso.edit(content=f"✅ Analisei {len(mensagens)} mensagens antigas{de_quem}{detalhe}.")
    embed = _embed_resumo(f"🕰️ Mensagens antigas{de_quem}", contagem)
    await ctx.send(embed=embed)


@bot.command(name="apagardados")
async def apagardados(ctx: commands.Context):
    """!apagardados  -> apaga as suas estatísticas de emoções"""
    apagadas = apagar_usuario(ctx.author.id)
    await ctx.send(f"Pronto, apaguei {apagadas} registros de emoções seus. 🧹")


@bot.command(name="analisar")
async def analisar_texto(ctx: commands.Context, *, texto: str):
    """!analisar estou muito feliz hoje"""
    detectadas, ordenadas = await classificar(texto)
    resultado = " + ".join(f"{emoji(e)} {nome(e)}" for e in detectadas)
    linhas = [f"{emoji(e)} {nome(e)}: {p:.0%}" for e, p in ordenadas]
    await ctx.send(f"**Resultado: {resultado}**\n\n" + "\n".join(linhas))


@bot.command(name="esquecer")
async def esquecer(ctx: commands.Context):
    """!esquecer  -> apaga a memória da conversa neste canal"""
    historico.pop(ctx.channel.id, None)
    await ctx.send("Pronto, esqueci nossa conversa neste canal. 🧹")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Defina DISCORD_TOKEN no arquivo .env")
    bot.run(TOKEN)
