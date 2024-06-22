import io
import logging
from typing import Optional, TYPE_CHECKING
import discord
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
    Send Text-to-Speech messages using OpenAI's TTS
    """
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9811198108111121, force_registration=True)
        default_global = {"api_key": None}
        default_guild = {"voice": "alloy"}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

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
        Send Text to speech messages as an mp3 using OpenAI's TTS
        """
        api_key = await self.config.api_key()
        if not api_key:
            return await ctx.send("OpenAI API key is not set. Please ask the bot owner to set it.")

        if voice is None:
            voice = await self.config.guild(ctx.guild).voice()

        openai.api_key = api_key

        try:
            response = openai.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )

            mp3_fp = io.BytesIO(response.content)
            await ctx.send(file=discord.File(mp3_fp, "tts_audio.mp3"))
        except Exception as e:
            log.error(f"Error in TTS command: {str(e)}", exc_info=True)
            await ctx.send(f"An error occurred while generating the TTS: {str(e)}")
