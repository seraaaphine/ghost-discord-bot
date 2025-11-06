import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import os
import subprocess
import lyricsgenius
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

SPOTIFY_CLIENT_ID = "CLIENT_ID"
SPOTIFY_CLIENT_SECRET = "SECRET_CLIENT"

sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

genius = lyricsgenius.Genius("GENIUS_TOKEN")

os.environ["PATH"] += os.pathsep + "E:\\FFMpeg\\ffmpeg-8.0-full_build\\ffmpeg-8.0-full_build\\bin"

try:
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
    print("FFmpeg encontrado! Versão:")
    print(result.stdout.split("\n")[0])
except FileNotFoundError:
    print("ERRO: FFmpeg NÃO encontrado. Verifique o caminho:")
    print(r"E:\FFMpeg\ffmpeg-8.0-full_build\ffmpeg-8.0-full_build\bin")
    exit()
except Exception as e:
    print(f"Erro ao testar FFmpeg: {e}")
    exit()

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -ac 2 -ar 48000 -b:a 96k -loglevel quiet'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class MusicPlayer:
    def __init__(self):
        self.queue = []
        self.current = None
        self.loop = False

    def add(self, track):
        self.queue.append(track)

    def get_next(self):
        if not self.queue:
            return None
        return self.queue.pop(0)

    def clear(self):
        self.queue.clear()
        self.current = None

async def play_next(voice_client: discord.VoiceClient):
    guild_id = voice_client.guild.id
    player = bot.players.get(guild_id)
    if not player:
        return

    next_track = player.get_next()
    if not next_track:
        player.current = None
        if voice_client.is_connected():
            await voice_client.disconnect()
        return

    player.current = next_track

    for attempt in range(3):
        try:
            source = discord.FFmpegPCMAudio(next_track['url'], **ffmpeg_options)
            voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(voice_client), bot.loop))

            if voice_client.is_connected():
                channel = bot.get_channel(voice_client.channel.id)
                if channel:
                    await channel.send(f"Tocando: *{next_track['title']}*")

            break 

        except Exception as e:
            print(f"[ERRO VOZ] Tentativa {attempt + 1}: {e}")
            if voice_client.is_connected():
                await voice_client.disconnect()
            await asyncio.sleep(2)
            try:
                voice_client = await voice_client.channel.connect(reconnect=True, timeout=10)
            except:
                await asyncio.sleep(3)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(url, download=False)
        )
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url']
        return cls(discord.FFmpegPCMAudio(filename, executable=r"E:\FFMpeg\ffmpeg-8.0-full_build\ffmpeg-8.0-full_build\bin\ffmpeg.exe", **ffmpeg_options), data=data)

class GhostBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.players = {}

    async def setup_hook(self):
        guild_id = 1425902464976031767
        guild = discord.Object(id=guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"[SYNC] {len(synced)} comandos sincronizados para o servidor {guild_id}")

    async def on_ready(self):
        print(f"O Bot {self.user} foi ligado com sucesso.")

bot = GhostBot()

@bot.tree.command(name="interact", description="Interagir com o Bot")
async def oiamundo(interaction: discord.Interaction):
    await interaction.response.send_message(f"Olá, {interaction.user.mention}! Eu sou o Ghost. Em que posso ajudar?")

@bot.tree.command(name="adição", description="Some dois numeros distintos")
async def adicao(interaction: discord.Interaction, numero1: int, numero2: int):
    numero_somado = numero1 + numero2
    await interaction.response.send_message(f"O resultado é ... {numero_somado}", ephemeral=True)

@bot.tree.command(name="subtração", description="Subtraia dois números distintos")
async def subtracao(interaction: discord.Interaction, numero1: int, numero2: int):
    numero_subtraido = numero1 - numero2
    await interaction.response.send_message(f"O resultado é ... {numero_subtraido}", ephemeral=True)

@bot.tree.command(name="stop-interact", description="Parar a interação com o Bot")
async def comando(interaction: discord.Interaction):
    await interaction.response.send_message(f"Se vemos numa próxima, {interaction.user.mention}! Até depois.")

@bot.tree.command(name="play-music", description="Adiciona música à fila")
async def play(interaction: discord.Interaction, url: str):
    if not interaction.user.voice:
        await interaction.response.send_message("Você precisa estar em um canal de voz para usar este comando!", ephemeral=True)
        return

    # Defer para ganhar tempo (evita o erro 10062)
    await interaction.response.defer(ephemeral=False)

    channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client or await channel.connect(reconnect=True)

    guild_id = interaction.guild.id
    player = bot.players.setdefault(guild_id, MusicPlayer())

    data = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    if 'entries' in data:
        data = data['entries'][0]

    track = {
        'title': data['title'],
        'url': data['url'],
        'requester': interaction.user
    }

    player.add(track)

    if not voice_client.is_playing():
        await play_next(voice_client)
        await interaction.followup.send(f"**Tocando:** {track['title']}")
    else:
        await interaction.followup.send(f"**Adicionado à fila:** {track['title']}")

@bot.tree.command(name="playlist", description="Adiciona playlist inteira à fila")
async def playlist(interaction: discord.Interaction, url: str):
    if not interaction.user.voice:
        await interaction.response.send_message("Entre em um canal de voz!", ephemeral=True)
        return

    await interaction.response.send_message("Carregando playlist...", ephemeral=False)

    channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client or await channel.connect(reconnect=True)
    player = bot.players.setdefault(interaction.guild.id, MusicPlayer())

    data = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    if not data or 'entries' not in data:
        await interaction.followup.send("Playlist não encontrada ou vazia.")
        return

    adicionadas = 0
    for entry in data['entries']:
        if entry:
            track = {
                'title': entry.get('title', 'Desconhecido'),
                'url': entry.get('url'),
                'requester': interaction.user
            }
            player.add(track)
            adicionadas += 1

    if not voice_client.is_playing():
        await play_next(voice_client)

    await interaction.followup.send(f"**{adicionadas} músicas** adicionadas da playlist!")

@bot.tree.command(name="lyrics", description="Mostra a letra da música atual")
async def lyrics(interaction: discord.Interaction):
    player = bot.players.get(interaction.guild.id)
    if not player or not player.current:
        await interaction.response.send_message("Nenhuma música tocando.", ephemeral=True)
        return

    title = player.current['title']
    artist = player.current.get('artist', "")

    await interaction.response.send_message(f"Buscando a letra de **{title}**...", ephemeral=True)

    song = genius.search_song(title, artist=artist)

    if not song:
        await interaction.followup.send("Letra não encontrada.", ephemeral=True)
        return

    lyrics = song.lyrics
    if len(lyrics) > 1900:
        lyrics = lyrics[:1900] + "\n\n[... letra cortada]"

    embed = discord.Embed(
        title=f"Letra: {song.title}",
        description=lyrics,
        color=0xffd700
    )
    embed.set_footer(text="Fonte: Genius.com")
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="pause", description="Pausa a música")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("Música pausada.")
    else:
        await interaction.response.send_message("Nenhuma música está tocando no momento.", ephemeral=True)

@bot.tree.command(name="resume", description="Continua a música pausada")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("Música continuada.")
    else:
        await interaction.response.send_message("A música não está mais pausada.", ephemeral=True)

@bot.tree.command(name="music-queue", description="Mostra a fila de músicas")
async def queue(interaction: discord.Interaction):
    await interaction.response.send_message("Carregando fila...", ephemeral=True)

    player = bot.players.get(interaction.guild.id)
    if not player or not player.queue and not player.current:
        await interaction.followup.send("A fila está vazia.", ephemeral=True)
        return

    embed = discord.Embed(title="Fila de Músicas", color=0x00ff00)

    if player.current:
        embed.add_field(name="Tocando Agora", value=f"**{player.current['title']}**", inline=False)

    if player.queue:
        queue_list = "\n".join([f"{i+1}. **{t['title']}**" for i, t in enumerate(player.queue[:10])])
        embed.add_field(name="Próximas", value=queue_list, inline=False)
        if len(player.queue) > 10:
            embed.set_footer(text=f"E mais {len(player.queue) - 10} músicas...")

    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="remove", description="Remove música da fila")
async def remove(interaction: discord.Interaction, posicao: int):
    player = bot.players.get(interaction.guild.id)
    if not player or not player.queue or posicao < 1 or posicao > len(player.queue):
        await interaction.response.send_message("Posição inválida ou fila vazia.", ephemeral=True)
        return

    removida = player.queue.pop(posicao - 1)
    await interaction.response.send_message(f"Removido: **{removida['title']}**")

@bot.tree.command(name="skip-music", description="Pula a música atual")
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if not voice_client or not voice_client.is_playing():
        await interaction.response.send_message("Nenhuma música está tocando agora.", ephemeral=True)
        return

    voice_client.stop()
    await interaction.response.send_message("Música pulada.")

@bot.tree.command(name="stop-music", description="Para e limpa a fila")
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_connected():
        player = bot.players.get(interaction.guild.id)
        if player:
            player.clear()
        voice_client.stop()
        await voice_client.disconnect()
        await interaction.response.send_message("Fila limpa e desconectado.")
    else:
        await interaction.response.send_message("Não estou em voz.", ephemeral=True)

bot.run("DISCORD_TOKEN")
