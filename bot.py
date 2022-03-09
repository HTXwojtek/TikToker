import re
from typing import Optional

import aiohttp
import dis_snek as dis
from dis_snek.ext.paginators import Paginator
from dotenv import get_key

from models import *
from tiktok import get_tiktok

import motor
from beanie import init_beanie

from database import Config, UsageData, Shortener, OptedOut

from base64 import urlsafe_b64encode
from os import urandom

bot = dis.Snake(
    intents=dis.Intents.MESSAGES | dis.Intents.DEFAULT,
    sync_interactions=True,
    delete_unused_application_cmds=False,
)


@dis.listen(dis.events.Startup)
async def on_startup():
    client = motor.motor_asyncio.AsyncIOMotorClient(get_key(".env", "MONGODB_URL"))
    await init_beanie(
        database=client.tiktoker,
        document_models=[Config, UsageData, Shortener, OptedOut],
    )


@dis.slash_command("help", "All the help you need")
async def help(ctx: dis.InteractionContext):
    embeds = [
        dis.Embed(
            title="Tiktoker",
            description="Tiktoker is a bot that allows you to send Tiktok videos to your discord server.",
            color="#00FFF0",
            fields=[
                dis.EmbedField(
                    "Help Menu",
                    "Bellow is some buttons that will guide you through some features of the bot.",
                ).to_dict(),
            ],
        ),
        dis.Embed(
            "Configuration",
            "Here are some configuration options for the bot.\nThese can be changed by using the `/config <option> <vaulue>` command.\nExample: `/config delete_origin:True`\nTo view the current configuration, use `/config` without any arguments.",
            color="#00FFF0",
            fields=[
                dis.EmbedField(
                    "Auto Embed",
                    "When enabled, the bot will automatically embed the Tiktok link that is sent.",
                ).to_dict(),
                dis.EmbedField(
                    "Delete Origin",
                    "When enabled and _Auto Embed_ is enabled, the bot will delete the message that sent the Tiktok link.",
                ).to_dict(),
                dis.EmbedField(
                    "Suppress Origin Embed",
                    "Toggles the suppress origin embed feature.",
                ).to_dict(),
            ],
        ),
        dis.Embed(
            "Commands",
            "Here are some commands that can be used to interact with the bot.",
            color="#00FFF0",
            fields=[
                dis.EmbedField(
                    "Convert 📸",
                    "Right click a message then go to *`Apps > Convert 📸`*. \nMeant for when *Auto Embed* is disabled in the server's config.",
                ).to_dict(),
            ],
        ),
    ]

    paginator = Paginator.create_from_embeds(bot, *embeds, timeout=20)
    paginator.default_button_color = dis.ButtonStyles.GRAY
    paginator.first_button_emoji = "<:first_arrow:948778200224370768>"
    paginator.last_button_emoji = "<:last_arrow:948778201264582806>"
    paginator.next_button_emoji = "<:next:948778200295673886>"
    paginator.back_button_emoji = "<:back:948778200257941576>"

    await paginator.send(ctx)


@dis.slash_command(
    name="privacy",
    description="Inform yourself on some of the data we collect.",
    sub_cmd_name="policy",
    sub_cmd_description="Review our Privacy Policy.",
)
async def privacy_policy(ctx: dis.InteractionContext):
    await ctx.defer(True)
    await ctx.send("Dont")  # TODO: Make a privacy policy


@dis.slash_command(
    name="privacy",
    description="Inform yourself on some of the data we collect.",
    group_name="usage",
    sub_cmd_name="data",
    sub_cmd_description="Choose what we can collect about you.",
)
@dis.slash_option(
    "collect",
    "Save usage data?",
    dis.OptionTypes.STRING,
    choices=[
        dis.SlashCommandChoice("yes", "yes"),
        dis.SlashCommandChoice("no", "no"),
        dis.SlashCommandChoice("delete", "delete"),
    ],
)
async def privacy_options(ctx: dis.InteractionContext, collect: str = None):
    await ctx.defer(True)

    if collect is None:
        await ctx.send(
            f"You are currently: {'Opted Out' if get_opted_out(ctx.author.id) else 'Opted In'} \n\n**We take your privacy seriously.**\nYour data is not shared with the public. **Usage data is used to share statistics like total videos converted and total users.** \nPlease consider sharing your data with us if you want to help us improve the bot. \nYou can change this setting by using `/config collect:True` or `/config collect:False`. \n\nYou can also delete your usage data by using `/config collect:delete`."
        )
        return

    if collect == "yes":
        await ctx.send(
            "Thank you for sharing your data with us. Remember this is not shared with anyone."
        )
        await remove_opted_out(ctx.author.id)

    elif collect == "no":
        await ctx.send(
            "You have opted out of usage data collection. Thank you for your time."
        )
        await add_opted_out(ctx.author.id)

    elif collect == "delete":
        await ctx.send("Your usage data for this server has been deleted.")
        await remove_usage_data(ctx.guild.id, ctx.author.id)


@dis.slash_command(
    "config",
    "Configures the bot for your server. (Leave options blank to view current settings)",
)
@dis.slash_option(
    "auto_embed", "Toggles auto embedding of tiktok links.", dis.OptionTypes.BOOLEAN
)
@dis.slash_option(
    "delete_origin",
    "Toggles deleting of the origin message. (When auto_embed True)",
    dis.OptionTypes.BOOLEAN,
)
@dis.slash_option(
    "suppress_origin_embed",
    "Toggles suppression of the origin message embed.",
    dis.OptionTypes.BOOLEAN,
)
async def setup_config(
    ctx: dis.InteractionContext,
    auto_embed: bool = None,
    delete_origin: bool = None,
    suppress_origin_embed: bool = None,
):
    """
    Sets up the config for the guild.
    """
    if not ctx.author.has_permission(dis.Permissions.MANAGE_GUILD | dis.Permissions.ADMINISTRATOR):
        await ctx.send("You do not have permission to use this command. Reason: `Missing Manage Server Permission`", ephemeral=True)
        return

    guild_id = ctx.guild.id
    await ctx.defer()
    config = await get_guild_config(guild_id)
    if auto_embed is None and delete_origin is None and suppress_origin_embed is None:
        embed = dis.Embed(
            "Current Config", "To change a setting, use `/config <setting> <value>`"
        )
        embed.add_field("Auto Embed", "☑️" if config.auto_embed else "❌", inline=True)
        embed.add_field(
            "Delete Origin", "☑️" if config.delete_origin else "❌", inline=True
        )
        embed.add_field(
            "Suppress Origin Embed",
            "☑️" if config.suppress_origin_embed else "❌",
            inline=True,
        )
        await ctx.send(embed=embed)
        return

    if auto_embed is not None:
        config.auto_embed = auto_embed
    if delete_origin is not None:
        config.delete_origin = delete_origin
    if suppress_origin_embed is not None:
        config.suppress_origin_embed = suppress_origin_embed

    await config.save()

    embed = dis.Embed(
        "Current Config", "To change a setting, use `/config <setting> <value>`"
    )
    embed.add_field("Auto Embed", "☑️" if config.auto_embed else "❌", inline=True)
    embed.add_field("Delete Origin", "☑️" if config.delete_origin else "❌", inline=True)
    embed.add_field(
        "Suppress Origin Embed",
        "☑️" if config.suppress_origin_embed else "❌",
        inline=True,
    )
    await ctx.send(embed=embed)


@dis.context_menu("Convert 📸", dis.CommandTypes.MESSAGE)
async def menu_convert_video(ctx: dis.InteractionContext):
    await ctx.defer()
    link = check_for_link(ctx.target.content)
    if not link:
        await ctx.send("I don't see a link in that message.", ephemeral=True)
        return
    config = await get_guild_config(ctx.guild.id)

    if link.type == VideoIdType.SHORT:
        video_id = await get_video_id(link.url)
    else:
        video_id = link.id

    try:
        tiktok = await get_tiktok(video_id)
    except Exception as e:
        await ctx.send(f"Error: {e}", ephemeral=True)
        return

    short_url = await create_short_url(tiktok.video.video_uri)

    more_info_btn = dis.Button(
        dis.ButtonStyles.GRAY,
        "Info",
        "🌐",
        custom_id=f"v_id{video_id}",
    )
    delete_msg_btn = dis.Button(
        dis.ButtonStyles.RED,
        emoji="🗑️",
        custom_id=f"delete{ctx.author.id}",
    )
    if config.suppress_origin_embed:
        await ctx.target.suppress_embeds()
    sent_msg = await ctx.send(
        short_url + f" | [Origin]({ctx.target.jump_url})",
        components=[more_info_btn, delete_msg_btn],
    )
    await insert_usage_data(ctx.guild.id, ctx.author.id, video_id, sent_msg.id)


@dis.slash_command("tiktok", "Convert a tiktok link to a video.")
@dis.slash_option("link", "The link to convert.", dis.OptionTypes.STRING, True)
async def slash_tiktok(ctx: dis.InteractionContext, link: str):
    link = check_for_link(link)
    if not link:
        await ctx.send("That doesn't seem to be a valid link.", ephemeral=True)
        return

    if link.type == VideoIdType.SHORT:
        video_id = await get_video_id(link.url)
    else:
        video_id = link.id

    try:
        tiktok = await get_tiktok(video_id)
    except Exception as e:
        await ctx.send(f"Error: {e}", ephemeral=True)
        return

    short_url = await create_short_url(tiktok.video.video_uri)
    more_info_btn = dis.Button(
        dis.ButtonStyles.GRAY,
        "Info",
        "🌐",
        custom_id=f"v_id{video_id}",
    )
    delete_msg_btn = dis.Button(
        dis.ButtonStyles.RED,
        emoji="🗑️",
        custom_id=f"delete{ctx.author.id}",
    )
    sent_msg = await ctx.send(
        short_url,
        components=[more_info_btn, delete_msg_btn],
    )
    await insert_usage_data(ctx.guild.id, ctx.author.id, video_id, sent_msg.id)


@dis.listen(dis.events.MessageCreate)
async def on_message_create(event: dis.events.MessageCreate):
    if event.message.author.id == bot.user.id:
        return
    content = event.message.content
    link = check_for_link(content)
    if not link:
        return

    config = await get_guild_config(event.message.guild.id)

    if not config.auto_embed:
        return

    if link.type == VideoIdType.SHORT:
        video_id = await get_video_id(link.url)
    else:
        video_id = link.id

    try:
        tiktok = await get_tiktok(video_id)
    except Exception as e:
        print(f"Error: {e}")
        return

    short_url = await create_short_url(tiktok.video.video_uri)

    more_info_btn = dis.Button(
        dis.ButtonStyles.GRAY,
        "Info",
        "🌐",
        custom_id=f"v_id{video_id}",
    )
    delete_msg_btn = dis.Button(
        dis.ButtonStyles.RED,
        emoji="🗑️",
        custom_id=f"delete{event.message.author.id}",
    )

    if config.delete_origin:
        sent_msg = await event.message.channel.send(
            short_url + f" | From: {event.message.author.mention}",
            components=[more_info_btn, delete_msg_btn],
            allowed_mentions=dis.AllowedMentions.none(),
        )
        try:
            await event.message.delete()
        except dis.errors.NotFound:
            pass
    elif config.suppress_origin_embed:
        await event.message.suppress_embeds()
        await bot.fetch_channel(event.message._channel_id)
        sent_msg = await event.message.reply(
            short_url, components=[more_info_btn, delete_msg_btn]
        )
    else:
        await bot.fetch_channel(event.message._channel_id)
        sent_msg = await event.message.reply(
            short_url, components=[more_info_btn, delete_msg_btn]
        )

    await insert_usage_data(
        event.message.guild.id, event.message.author.id, video_id, sent_msg.id
    )


@dis.listen(dis.events.Button)
async def on_button_click(event: dis.events.Button):
    ctx = event.context
    if ctx.custom_id.startswith("delete"):
        if dis.Permissions.MANAGE_MESSAGES in ctx.author.channel_permissions(
            ctx.channel
        ) or ctx.author.has_permission(dis.Permissions.MANAGE_MESSAGES):
            await ctx.message.delete()
        elif ctx.author.id == ctx.custom_id[6:]:
            await ctx.delete()
        else:
            await ctx.send(
                "You don't have the permissions to delete this message.", ephemeral=True
            )
    elif ctx.custom_id.startswith("v_id"):
        await ctx.defer(ephemeral=True)
        tiktok = await get_tiktok(int(ctx.custom_id[4:]))

        video = tiktok.video
        author = tiktok.author
        stats = tiktok.statistics

        embed = dis.Embed(
            tiktok.description.cleaned[:256]
            if tiktok.description.cleaned != ""
            else None,
            description=tiktok.share_url,
        )

        embed.set_author(name=author.nickname, icon_url=author.avatar, url=author.url)
        embed.set_thumbnail(url=video.cover_url)
        embed.add_field("Views 👁️", stats.play_count, True)
        embed.add_field("Likes ❤️", stats.like_count, True)
        embed.add_field("Comments 💬", stats.comment_count, True)
        embed.add_field("Shares 🔃", stats.share_count, True)
        embed.add_field("Downloads 📥", stats.download_count, True)
        embed.add_field("Created", tiktok.created, True)
        download_btn = dis.Button(
            dis.ButtonStyles.URL, "Download", url=video.download_url
        )
        if len(tiktok.description.tags) > 0:
            embed.add_field(
                "Tags 🔖",
                ", ".join(
                    [
                        f"[`#{tag}`](https://www.tiktok.com/tag/{tag})"
                        for tag in tiktok.description.tags
                    ]
                ),
                True,
            )

        audio_btn = dis.Button(
            dis.ButtonStyles.GRAY,
            "Audio",
            emoji="🎵",
            custom_id=f"m_id{tiktok.id}",
        )

        await ctx.send(embed=embed, components=[download_btn, audio_btn])
        return

    elif ctx.custom_id.startswith("m_id"):  # TODO: Use aweme instead of music
        await ctx.defer(ephemeral=True)

        try:
            tiktok = await get_tiktok(int(ctx.custom_id[4:]))
        except Exception as e:
            await ctx.send("Seems this audio has been deleted/taken down.")
            print(f"Error: {e}")
            return

        music = tiktok.music
        embed = dis.Embed(
            title=music.title,
            url="https://www.tiktok.com/music/id-" + str(music.id),
        )

        if extra_music_data := await get_music_data(music.id):
            video_count = extra_music_data["musicInfo"]["stats"]["videoCount"]
            embed.add_field(name="Video Count 📱", value=video_count, inline=False)

        embed.set_author(
            name=music.owner_nickname, url=music.owner_url, icon_url=music.avatar_url
        )
        embed.set_thumbnail(url=music.cover_url)

        await ctx.send(
            embed=embed,
            components=dis.Button(
                dis.ButtonStyles.URL, url=music.play_url, label="Download"
            ),
        )


async def create_short_url(video_uri: str) -> str:
    """
    Shortens a url if not in cache.

    args:
        video_uri: The uri of the video.

    returns:
        The shortened url.
    """

    if existing_entry := await Shortener.find_one({"video_uri": video_uri}):
        return existing_entry.shortened_url

    slug = urlsafe_b64encode(urandom(6)).decode()
    while len(await Shortener.find({"slug": slug}).to_list()) > 0:
        print("Note: slug collision, regenerating")
        slug = urlsafe_b64encode(urandom(6)).decode()

    shortener = Shortener(
        video_uri=video_uri,
        slug=slug,
        shortened_url=f"https://m.tiktoker.win/{slug}",
    )
    await shortener.insert()
    return shortener.shortened_url


async def get_video_id(url: str) -> int:
    """
    Gets the video id from short url.

    args:
        url: The url to get the id from.

    returns:
        The video id.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, allow_redirects=False) as response:
            if location := response.headers.get("Location"):
                if link := check_for_link(location):
                    return link.id


async def get_music_data(music_id: int = None) -> Optional[dict]:
    """
    Gets the music data.

    args:
        music_id: The music id.

    returns:
        The music data.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://tiktok.com/api/music/detail/?language=en&musicId={music_id}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
            },
        ) as response:
            if response.status == 200:
                if data := await response.json():
                    if data.get("statusCode") == 10218:
                        return None
                    return data
                return data
            else:
                return None


def check_for_link(content: str) -> Optional["LinkData"]:
    """
    Checks if the content has a TikTok video.

    args:
        content: The content to check.

    returns:
        LinkData
    """
    try:
        long_match = re.search(
            r"(?P<http>http:|https:\/\/)?(www\.)?tiktok\.com\/(@.{1,24})\/video\/(?P<id>\d{15,30})",
            content,
        )
        short_match = re.search(
            r"(?P<http>http:|https:\/\/)?(\w{2})\.tiktok.com\/(?P<short_id>\w{5,15})",
            content,
        )
        medium_match = re.search(
            r"(?P<http>http:|https:\/\/)?m\.tiktok\.com\/v\/(?P<id>\d{15,30})", content
        )
    except TypeError as e:
        print(f"{content} is not a string")
        print(type(content))
    if long_match:
        if not long_match.group("http"):
            return LinkData.from_list(
                [
                    VideoIdType.LONG,
                    long_match.group("id"),
                    f"https://{long_match.group(0)}",
                ]
            )
        return LinkData.from_list(
            [VideoIdType.LONG, long_match.group("id"), long_match.group(0)]
        )
    if short_match:
        if not short_match.group("http"):
            return LinkData.from_list(
                [
                    VideoIdType.SHORT,
                    short_match.group("short_id"),
                    f"https://{short_match.group(0)}",
                ]
            )
        return LinkData.from_list(
            [VideoIdType.SHORT, short_match.group("short_id"), short_match.group(0)]
        )
    if medium_match:
        if not medium_match.group("http"):
            return LinkData.from_list(
                [
                    VideoIdType.MEDIUM,
                    medium_match.group("id"),
                    f"https://{medium_match.group(0)}",
                ]
            )
        return LinkData.from_list(
            [VideoIdType.MEDIUM, medium_match.group("id"), medium_match.group(0)]
        )
    return None


async def get_guild_config(guild_id: int) -> "Config":
    """
    Gets the guild config.

    args:
        guild_id: The guild id.

    returns:
        The guild config.
    """
    if config := await Config.find_one({"guild_id": guild_id}):
        return config
    else:
        new_config = Config(guild_id=guild_id)
        await new_config.insert()
        return new_config


async def edit_guild_config(guild_id: int, **kwargs) -> "Config":
    config = await get_guild_config(guild_id)
    for key, value in kwargs.items():
        await config.update({key: value})
    return await get_guild_config(guild_id)


async def insert_usage_data(
    guild_id: int, user_id: int, video_id: int, message_id: int
) -> None:
    """
    Inserts usage data.

    args:
        guild_id: The guild id.
        user_id: The user id.
        video_id: The video id.
        message_id: The message id with the video.
    """

    if await get_opted_out(user_id):  # weirdos
        user_id = None
        message_id = None

    await UsageData(
        guild_id=guild_id, user_id=user_id, video_id=video_id, message_id=message_id
    ).insert()


async def add_opted_out(user_id: int) -> None:
    await OptedOut({user_id: True}).insert()


async def remove_opted_out(user_id: int) -> None:
    await OptedOut.delete({user_id: True})


async def remove_usage_data(guild_id: int, user_id: int) -> None:
    return  # TODO: remove usage data
    data = UsageData.find_all({guild_id: guild_id, user_id: user_id})


async def get_opted_out(user_id: int) -> bool:
    if opted_out := await OptedOut.find_one({"user_id": user_id}):
        return True
    else:
        return False


bot.start(get_key(".env", "TOKEN"))
