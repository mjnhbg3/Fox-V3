import io
import logging
from typing import Optional, TYPE_CHECKING
import discord
from discord import app_commands
from discord.ext.commands import BadArgument, Converter
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.commands import Cog
import openai

log = logging.getLogger("red.fox_v3.tts")

if TYPE_CHECKING:
    VoiceConverter = str
else:
    class VoiceConverter(Converter):
        async def convert(self, ctx, argument) -> str:
            valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
            if argument.lower() not in valid_voices:
                raise BadArgument(f"Voice not supported: {argument}. Valid voices are: {', '.join(valid_voices)}")
            return argument.lower()

class TTS(Cog):
    """
    Send Text-to-Speech messages
    """
    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9811198108111121, force_registration=True)
        default_global = {"api_key": None}
        default_guild = {"voice": "alloy"}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def cog_load(self):
        self.bot.tree.add_command(self.tts_slash)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    @commands.is_owner()
    @commands.command()
    async def set_openai_key(self, ctx: commands.Context, api_key: str):
        """
        Sets the OpenAI API key for the bot
        """
        await self.config.api_key.set(api_key)
        await ctx.send("OpenAI API key has been set.")

    @commands.mod()
    @commands.command()
    async def ttsvoice(self, ctx: commands.Context, voice: VoiceConverter):
        """
        Sets the default voice for TTS in this guild.
        Default is `alloy`. Other options: echo, fable, onyx, nova, shimmer
        """
        await self.config.guild(ctx.guild).voice.set(voice)
        await ctx.send(f"Default TTS voice set to {voice}")

    @commands.command(aliases=["t2s", "text2"])
    @commands.guild_only()
    async def tts(
        self,
        ctx: commands.Context,
        voice: Optional[VoiceConverter] = None,
        *,
        text: str,
    ):
        """
        Send Text to speech messages as an mp3 or play in voice channel
        """
        if voice is None:
            voice = await self.config.guild(ctx.guild).voice()

        api_key = await self.config.api_key()
        if not api_key:
            return await ctx.send("OpenAI API key is not set. Please ask the bot owner to set it.")

        openai.api_key = api_key

        try:
            response = openai.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )

            mp3_fp = io.BytesIO(response.content)
            mp3_fp.seek(0)

            if ctx.author.voice:
                await self.play_audio(ctx, mp3_fp)
            else:
                await ctx.send(file=discord.File(mp3_fp, "tts_audio.mp3"))
        except Exception as e:
            log.error(f"Error in TTS command: {str(e)}", exc_info=True)
            await ctx.send(f"An error occurred while generating the TTS: {str(e)}")

    @app_commands.command(name="tts", description="Send Text to speech messages")
    @app_commands.describe(
        voice="The voice to use for TTS (optional)",
        text="The text to convert to speech"
    )
    async def tts_slash(
        self,
        interaction: discord.Interaction,
        voice: Optional[str] = None,
        text: str = None,
    ):
        if voice is None:
            voice = await self.config.guild(interaction.guild).voice()
        else:
            try:
                voice = await VoiceConverter().convert(None, voice)
            except BadArgument as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return

        if text is None:
            await interaction.response.send_message("Please provide some text to convert to speech.", ephemeral=True)
            return

        await interaction.response.defer()

        api_key = await self.config.api_key()
        if not api_key:
            return await interaction.followup.send("OpenAI API key is not set. Please ask the bot owner to set it.")

        openai.api_key = api_key

        try:
            response = openai.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )

            mp3_fp = io.BytesIO(response.content)
            mp3_fp.seek(0)

            if interaction.user.voice:
                await self.play_audio(interaction, mp3_fp)
                await interaction.followup.send("TTS message played in voice channel.")
            else:
                await interaction.followup.send(file=discord.File(mp3_fp, "tts_audio.mp3"))
        except Exception as e:
            log.error(f"Error in TTS slash command: {str(e)}", exc_info=True)
            await interaction.followup.send(f"An error occurred while generating the TTS: {str(e)}")

    async def play_audio(self, ctx, audio: io.BytesIO):
        if isinstance(ctx, discord.Interaction):
            voice_state = ctx.user.voice
        else:
            voice_state = ctx.author.voice

        if not voice_state:
            raise ValueError("You need to be in a voice channel to use this command.")

        voice_channel = voice_state.channel
        voice_client = ctx.guild.voice_client

        if voice_client is None:
            voice_client = await voice_channel.connect()
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)

        audio.seek(0)
        voice_client.play(discord.FFmpegPCMAudio(audio, pipe=True))
        while voice_client.is_playing():
            await discord.asyncio.sleep(0.1)
        await voice_client.disconnect()
