import io
import logging
from typing import Optional
import discord
from discord import app_commands
from discord.ext.commands import BadArgument, Converter
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.commands import Cog
import openai

log = logging.getLogger("red.fox_v3.tts")

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
    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9811198108111121, force_registration=True)
        default_global = {"api_key": None}
        default_guild = {"voice": "alloy"}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def cog_load(self):
        self.tts_slash = app_commands.Command(
            name="tts",
            description="Send Text to speech messages",
            callback=self.tts_slash_callback
        )
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
        Send Text to speech messages
        """
        await self.tts_logic(ctx, voice, text)

    async def tts_slash_callback(
        self,
        interaction: discord.Interaction,
        voice: Optional[str] = None,
        text: str = "",
    ):
        """
        Slash command version of TTS
        """
        ctx = await self.bot.get_context(interaction)
        if voice:
            try:
                voice = await VoiceConverter().convert(ctx, voice)
            except BadArgument as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return
        await interaction.response.defer()
        await self.tts_logic(ctx, voice, text, is_slash=True)

    async def tts_logic(
        self,
        ctx: commands.Context,
        voice: Optional[str] = None,
        text: str = "",
        is_slash: bool = False,
    ):
        """
        Common logic for both regular and slash TTS commands
        """
        if voice is None:
            voice = await self.config.guild(ctx.guild).voice()

        api_key = await self.config.api_key()
        if not api_key:
            return await self.send_response(ctx, "OpenAI API key is not set. Please ask the bot owner to set it.", is_slash)

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
                vc = await ctx.author.voice.channel.connect()
                vc.play(discord.FFmpegPCMAudio(mp3_fp, pipe=True))
                while vc.is_playing():
                    await discord.asyncio.sleep(0.1)
                await vc.disconnect()
                await self.send_response(ctx, "TTS message played in voice channel.", is_slash)
            else:
                await self.send_response(ctx, file=discord.File(mp3_fp, "tts_audio.mp3"), is_slash)
        except Exception as e:
            log.error(f"Error in TTS command: {str(e)}", exc_info=True)
            await self.send_response(ctx, f"An error occurred while generating the TTS: {str(e)}", is_slash)

    async def send_response(self, ctx, content=None, is_slash=False, **kwargs):
        """
        Helper method to send responses for both regular and slash commands
        """
        if is_slash:
            if isinstance(ctx, discord.Interaction):
                if ctx.response.is_done():
                    await ctx.followup.send(content, **kwargs)
                else:
                    await ctx.response.send_message(content, **kwargs)
            else:
                await ctx.send(content, **kwargs)
        else:
            await ctx.send(content, **kwargs)
