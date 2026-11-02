# Bot de análise de emoções para Discord

Identifica as 5 emoções principais de cada mensagem: **Alegria, Tristeza, Medo, Raiva e Nojo**
(ou Neutro). O modelo de IA detecta 28 emoções e cada uma entra num desses grupos: gratidão,
amor e diversão contam como Alegria; decepção e remorso como Tristeza; nervosismo como Medo;
irritação como Raiva. Surpresa, curiosidade e confusão contam como Neutro.
Uma mensagem pode ter mais de uma emoção ao mesmo tempo. O bot reage com o emoji da principal.

## 1. Criar o bot no Discord
1. Acesse https://discord.com/developers/applications e clique em **New Application**.
2. No menu lateral, vá em **Bot**, clique em **Reset Token** e copie o token (guarde em segredo!).
3. Ainda em **Bot**, ative **Message Content Intent** e salve.
4. Vá em **OAuth2 → URL Generator**:
   - Em *Scopes*, marque `bot`.
   - Em *Bot Permissions*, marque: `Read Messages/View Channels`, `Send Messages`,
     `Add Reactions`, `Embed Links`, `Read Message History`.
5. Abra a URL gerada no navegador e adicione o bot ao seu servidor.

## 2. Preparar o computador
Precisa do Python 3.9 ou mais novo (https://www.python.org/downloads/).

Na pasta dos arquivos, rode no terminal:

```
python -m venv venv
venv\Scripts\activate          (Windows)
source venv/bin/activate       (Mac/Linux)
pip install -r requirements.txt
```

> A instalação baixa o PyTorch e o modelo de IA (alguns centenas de MB). É normal demorar.

## 3. Configurar o token
Crie um arquivo chamado `.env` na mesma pasta com:

```
DISCORD_TOKEN=cole_seu_token_aqui
```

### Para o bot conversar
O bot conversa quando você o marca (`@Suri oi!`) ou fala com ele no privado, usando uma IA
que roda no próprio PC pelo **Ollama** (grátis, sem chave de API):
1. Instale o Ollama: https://ollama.com/download (ou `winget install Ollama.Ollama`).
2. Baixe o modelo no terminal: `ollama pull gemma3:4b` (uns 3 GB).

> O Ollama precisa estar aberto para o bot conversar (o `iniciar_bot.bat` abre ele sozinho).
> Para trocar de modelo, baixe outro com `ollama pull` e mude `MODELO_IA` no `main.py`.

## 4. Rodar
Dê dois cliques em `iniciar_bot.bat`.

> O Controle Inteligente de Aplicativos do Windows bloqueia `venv312\Scripts\python.exe`.
> Por isso o `iniciar_bot.bat` usa o Python base junto com o `iniciar.py`, que carrega as
> bibliotecas da `venv312`.

Quando aparecer `Bot conectado como ...`, mande mensagens no servidor e veja as reações.

## Comandos
- `!emocoes`: emoções mais frequentes do servidor
- `!emocoes @usuario`: emoções mais frequentes de um usuário
- `!minhas`: quantas mensagens suas foram de cada emoção (todos os servidores + privado)
- `!grafico`: imagem com o total de cada emoção e como elas mudaram dia a dia (últimos 30 dias)
- `!grafico @usuario 7`: o mesmo, para uma pessoa e para os últimos 7 dias
- `!historico`: analisa as últimas 300 mensagens antigas do canal e soma nas estatísticas
  (`!historico 1000` lê mais, até 2000; `!historico @usuario` só as de uma pessoa).
  Mensagens já analisadas não são contadas de novo. No servidor, só quem pode
  gerenciar mensagens consegue usar.
- `!analisar <texto>`: mostra a força de cada uma das 5 emoções num texto
- `!esquecer`: apaga a memória da conversa no canal
- `!apagardados`: apaga as suas estatísticas de emoções
- `@Suri <mensagem>` ou mensagem no privado: conversa com o bot

## Ajustes no main.py
- `CONFIANCA_MINIMA`: probabilidade mínima para uma emoção contar. Aumente para o bot ser mais exigente.
- `MAX_EMOCOES`: quantas emoções no máximo uma mensagem pode ter.
- `REAGIR = False`: o bot só analisa e registra, sem reagir nas mensagens.
- `PERSONALIDADE`: como o bot se comporta na conversa.
- `CONVERSAR = False`: desliga a conversa com IA.
- `HISTORICO_MAX`: quantas mensagens de cada canal o bot lembra.
- `EMOCOES`: nome, emoji e cor (nos gráficos) de cada uma das 5 emoções e do Neutro.
- `GRUPOS`: em qual das 5 emoções entra cada emoção que o modelo detecta.
- `LIMITE_HISTORICO`: máximo de mensagens antigas que o `!historico` lê de uma vez.

## Observações
- As estatísticas ficam salvas no arquivo `emocoes.db` e continuam depois de reiniciar o bot.
  Só a emoção principal de cada mensagem é guardada, nunca o texto. Apagar o arquivo zera tudo.
- A memória da conversa com a IA fica só na memória e some quando o bot é desligado.
- Ironia e sarcasmo ainda enganam o modelo às vezes.
- Avise os membros do servidor que as mensagens são analisadas.
