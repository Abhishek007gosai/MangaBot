import enum
import shutil
from ast import arg
import asyncio
import re
from dataclasses import dataclass
import datetime as dt
import json

import pyrogram.errors
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaDocument

from config import env_vars, dbname
from img2cbz.core import fld2cbz
from img2pdf.core import fld2pdf, fld2thumb
from plugins import *
import os

from pyrogram import Client, filters
from typing import Dict, Tuple, List, TypedDict
from loguru import logger

from models.db import DB, ChapterFile, Subscription, LastChapter, MangaName, MangaOutput
from pagination import Pagination
from plugins.client import clean
from tools.aqueue import AQueue
from tools.flood import retry_on_flood

mangas: Dict[str, MangaCard] = dict()
chapters: Dict[str, MangaChapter] = dict()
pdfs: Dict[str, str] = dict()
paginations: Dict[int, Pagination] = dict()
queries: Dict[str, Tuple[MangaClient, str]] = dict()
full_pages: Dict[str, List[str]] = dict()
favourites: Dict[str, MangaCard] = dict()
language_query: Dict[str, Tuple[str, str]] = dict()
users_in_channel: Dict[int, dt.datetime] = dict()
locks: Dict[int, asyncio.Lock] = dict()
all_search: Dict[str, str] = dict()

plugin_dicts: Dict[str, Dict[str, MangaClient]] = {
    "🇬🇧 EN": {
        "MangaDex": MangaDexClient(),
        "Mgeko": MgekoClient(),
        "MagaKakalot": MangaKakalotClient(),
        "Manganelo": ManganeloClient(),
        "Manganato": ManganatoClient(),
        "MangaSee":  MangaSeeClient(),
        "MangaBuddy": MangaBuddyClient(),
        "AsuraScans": AsuraScansClient(),
        "NineManga": NineMangaClient(),        
        "LikeManga": LikeMangaClient(),
        "FlameComics": FlameComicsClient(),
        "MangaPark": MangaParkClient(),
        "ReaperScans": ReaperScansClient(),
        "ManhwaClan": ManhwaClanClient(),
          },
    "🇪🇸 ES": {
        "MangaDex": MangaDexClient(language=("es-la", "es")),
        "ManhuaKo": ManhuaKoClient(),
        "TMO": TMOClient(),
        "Mangatigre": MangatigreClient(),
        "NineManga": NineMangaClient(language='es'),
        "MangasIn": MangasInClient(),
    },
    "🔞 18+": {
        "Manga18fx": Manga18fxClient(),
        "MangaDistrict": MangaDistrictClient(),
        "OmgeaScans": OmgeaScansClient(),
    }
}

cache_dir = "cache"
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)
with open("tools/help_message.txt", "r") as f:
    help_msg = f.read()


class OutputOptions(enum.IntEnum):
    PDF = 1
    CBZ = 2

    def __and__(self, other):
        return self.value & other

    def __xor__(self, other):
        return self.value ^ other

    def __or__(self, other):
        return self.value | other


#disabled = ["[🇬🇧 EN] McReader", "[🇬🇧 EN] Manhuaplus", "[🇪🇸 ES] MangasIn", "[🇪🇸 ES] Likemanga"]
disabled = []

plugins = dict()
for lang, plugin_dict in plugin_dicts.items():
    for name, plugin in plugin_dict.items():
        identifier = f'[{lang}] {name}'
        if identifier in disabled:
            continue
        plugins[identifier] = plugin

# subsPaused = ["[🇪🇸 ES] TMO"]
subsPaused = disabled + []


def split_list(li):
    return [li[x: x + 2] for x in range(0, len(li), 2)]


def get_buttons_for_options(user_options: int):
    buttons = []
    for option in OutputOptions:
        checked = "✅" if option & user_options else "❌"
        text = f'{checked} {option.name}'
        buttons.append([InlineKeyboardButton(text, f"options_{option.value}")])
    return InlineKeyboardMarkup(buttons)


bot = Client('bot',
             api_id=int(env_vars.get('API_ID')),
             api_hash=env_vars.get('API_HASH'),
             bot_token=env_vars.get('BOT_TOKEN'),
             max_concurrent_transmissions=3)

pdf_queue = AQueue()

if dbname:
    DB(dbname)
else:
    DB()


@bot.on_message(filters=~(filters.private & filters.incoming))
async def on_chat_or_channel_message(client: Client, message: Message):
    pass


@bot.on_message()
async def on_private_message(client: Client, message: Message):
    channel = env_vars.get('CHANNEL')
    if not channel:
        return message.continue_propagation()
    if in_channel_cached := users_in_channel.get(message.from_user.id):
        if dt.datetime.now() - in_channel_cached < dt.timedelta(days=1):
            return message.continue_propagation()
    try:
        if await client.get_chat_member(channel, message.from_user.id):
            users_in_channel[message.from_user.id] = dt.datetime.now()
            return message.continue_propagation()
    except pyrogram.errors.UsernameNotOccupied:
        logger.debug("Channel does not exist, therefore bot will continue to operate normally")
        return message.continue_propagation()
    except pyrogram.errors.ChatAdminRequired:
        logger.debug("Bot is not admin of the channel, therefore bot will continue to operate normally")
        return message.continue_propagation()
    except pyrogram.errors.UserNotParticipant:
        await message.reply("In order to use the bot you must join it's update channel.",
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton('Join!', url=f't.me/{channel}')]]
                            ))
    except pyrogram.ContinuePropagation:
        raise
    except pyrogram.StopPropagation:
        raise
    except BaseException as e:
        logger.exception(e)


@bot.on_message(filters=filters.command(['start']))
async def on_start(client: Client, message: Message):
    logger.info(f"User {message.from_user.id} started the bot")
    await message.reply("Welcome to the best manga pdf bot in telegram!!\n"
                        "\n"
                        "How to use? Just type the name of some manga you want to keep up to date.\n"
                        "\n"
                        "For example:\n"
                        "`One Piece`\n"
                        "\n"
                        "Check /help for more information.")
    logger.info(f"User {message.from_user.id} finished the start command")
    

@bot.on_message(filters=filters.command(['help']))
async def on_help(client: Client, message: Message):
    await message.reply(help_msg)


@bot.on_message(filters=filters.command(['queue']))
async def on_queue(client: Client, message: Message):
    await message.reply(f'Queue size: {pdf_queue.qsize()}')


@bot.on_message(filters=filters.command(['refresh']))
async def on_refresh(client: Client, message: Message):
    text = message.reply_to_message.text or message.reply_to_message.caption
    if text:
        regex = re.compile(r'\[Read on telegraph]\((.*)\)')
        match = regex.search(text.markdown)
    else:
        match = None
    document = message.reply_to_message.document
    if not (message.reply_to_message and message.reply_to_message.outgoing and
            ((document and document.file_name[-4:].lower() in ['.pdf', '.cbz']) or match)):
        return await message.reply("This command only works when it replies to a manga file that bot sent to you")
    db = DB()
    if document:
        chapter = await db.get_chapter_file_by_id(document.file_unique_id)
    else:
        chapter = await db.get_chapter_file_by_id(match.group(1))
    if not chapter:
        return await message.reply("This file was already refreshed")
    await db.erase(chapter)
    return await message.reply("File refreshed successfully!")


@bot.on_message(filters=filters.command(['subs']))
async def on_subs(client: Client, message: Message):
    db = DB()

    filter_ = message.text.split(maxsplit=1)[1] if message.text.split(maxsplit=1)[1:] else ''
    filter_list = [filter_.strip() for filter_ in filter_.split(' ') if filter_.strip()]

    subs = await db.get_subs(str(message.from_user.id), filter_list)

    lines = []
    for sub in subs[:10]:
        lines.append(f'<a href="{sub.url}">{sub.name}</a>')
        lines.append(f'`/cancel {sub.url}`')
        lines.append('')

    if not lines:
        if filter_:
            return await message.reply("You have no subscriptions with that filter.")
        return await message.reply("You have no subscriptions yet.")

    text = "\n".join(lines)
    await message.reply(f'Your subscriptions:\n\n{text}\nTo see more subscriptions use `/subs filter`', disable_web_page_preview=True)


@bot.on_message(filters=filters.regex(r'^/cancel ([^ ]+)$'))
async def on_cancel_command(client: Client, message: Message):
    db = DB()
    sub = await db.get(Subscription, (message.matches[0].group(1), str(message.from_user.id)))
    if not sub:
        return await message.reply("You were not subscribed to that manga.")
    await db.erase(sub)
    return await message.reply("You will no longer receive updates for that manga.")


@bot.on_message(filters=filters.command(['options']))
async def on_options_command(client: Client, message: Message):
    db = DB()
    user_options = await db.get(MangaOutput, str(message.from_user.id))
    user_options = user_options.output if user_options else (1 << 30) - 1
    buttons = get_buttons_for_options(user_options)
    return await message.reply("Select the desired output format.", reply_markup=buttons)


@bot.on_message(filters=filters.regex(r'^/'))
async def on_unknown_command(client: Client, message: Message):
    await message.reply("Unknown command")


@bot.on_message(filters=filters.text)
async def on_message(client, message: Message):
    language_query[f"lang_None_{hash(message.text)}"] = (None, message.text)
    for language in plugin_dicts.keys():
        language_query[f"lang_{language}_{hash(message.text)}"] = (language, message.text)
    await bot.send_message(message.chat.id, "Select search languages.", reply_markup=InlineKeyboardMarkup(
        split_list([InlineKeyboardButton(language, callback_data=f"lang_{language}_{hash(message.text)}")
                    for language in plugin_dicts.keys()])
    ))


async def options_click(client, callback: CallbackQuery):
    db = DB()
    user_options = await db.get(MangaOutput, str(callback.from_user.id))
    if not user_options:
        user_options = MangaOutput(user_id=str(callback.from_user.id), output=(2 << 30) - 1)
    option = int(callback.data.split('_')[-1])
    user_options.output ^= option
    buttons = get_buttons_for_options(user_options.output)
    await db.add(user_options)
    return await callback.message.edit_reply_markup(reply_markup=buttons)


async def language_click(client, callback: CallbackQuery):
    lang, query = language_query[callback.data]
    if not lang:
        return await callback.message.edit("Select search languages.", reply_markup=InlineKeyboardMarkup(
            split_list([InlineKeyboardButton(language, callback_data=f"lang_{language}_{hash(query)}")
                        for language in plugin_dicts.keys()])
        ))
    for identifier, manga_client in plugin_dicts[lang].items():
        queries[f"query_{lang}_{identifier}_{hash(query)}"] = (manga_client, query)
    all_search[f"search_{lang}_{hash(query)}"] = (lang, query)
    await callback.message.edit(f"Language: {lang}\n\nSelect search plugin.", reply_markup=InlineKeyboardMarkup(
        split_list([InlineKeyboardButton(identifier, callback_data=f"query_{lang}_{identifier}_{hash(query)}")
                    for identifier in plugin_dicts[lang].keys() if f'[{lang}] {identifier}' not in disabled]) + [
            [InlineKeyboardButton("• All •", callback_data=f"search_{lang}_{hash(query)}"), InlineKeyboardButton("◀️ Back", callback_data=f"lang_None_{hash(query)}")]]
    ))



async def plugin_click(client, callback: CallbackQuery):
    manga_client, query = queries[callback.data]
    results = await manga_client.search(query)
    if not results:
        await bot.send_message(callback.from_user.id, "No manga found for given query.")
        return
    for result in results:
        mangas[result.unique()] = result
    await bot.send_message(callback.from_user.id,
                           "This is the result of your search",
                           reply_markup=InlineKeyboardMarkup([
                               [InlineKeyboardButton(result.name, callback_data=result.unique())] for result in results
                           ]))


async def all_click(client, callback: CallbackQuery):
    lang, query = all_search[callback.data]
    if not lang:
        return await callback.message.edit("Select search languages.", reply_markup=InlineKeyboardMarkup(
            split_list([InlineKeyboardButton(language, callback_data=f"lang_{language}_{hash(query)}")
                        for language in plugin_dicts.keys()])
        ))
    results = []
    for identifier, manga_client in plugin_dicts[lang].items():
        try:
            re = await manga_client.search(query)
            if re: 
                results.append(re[:2])
        except:
            pass
    if not results:
        await bot.send_message(callback.from_user.id, "No manga found for given query.")
        return 
    for res in results:
        for result in res:
            mangas[result.unique()] = result
    await bot.send_message(callback.from_user.id,
                           "This is the result of your search",
                           reply_markup=InlineKeyboardMarkup([
                               [InlineKeyboardButton(result.name, callback_data=result.unique())] for res in results for result in res
                           ]))


async def manga_click(client, callback: CallbackQuery, pagination: Pagination = None):
    if pagination is None:
        pagination = Pagination()
        paginations[pagination.id] = pagination

    if pagination.manga is None:
        manga = mangas[callback.data]
        pagination.manga = manga

    results = await pagination.manga.client.get_chapters(pagination.manga, pagination.page)

    if not results:
        await callback.answer("Ups, no chapters there.", show_alert=True)
        return

    full_page_key = f'full_page_{hash("".join([result.unique() for result in results]))}'
    full_pages[full_page_key] = []
    for result in results:
        chapters[result.unique()] = result
        full_pages[full_page_key].append(result.unique())

    db = DB()
    subs = await db.get(Subscription, (pagination.manga.url, str(callback.from_user.id)))

    prev = [InlineKeyboardButton('<<', f'{pagination.id}_{pagination.page - 1}')]
    next_ = [InlineKeyboardButton('>>', f'{pagination.id}_{pagination.page + 1}')]
    footer = [prev + next_] if pagination.page > 1 else [next_]

    fav = [[InlineKeyboardButton(
        "Unsubscribe" if subs else "Subscribe",
        f"{'unfav' if subs else 'fav'}_{pagination.manga.unique()}"
    )]]
    favourites[f"fav_{pagination.manga.unique()}"] = pagination.manga
    favourites[f"unfav_{pagination.manga.unique()}"] = pagination.manga

    full_page = [[InlineKeyboardButton('Full Page', full_page_key)]]

    buttons = InlineKeyboardMarkup(fav + footer + [
        [InlineKeyboardButton(result.name, result.unique())] for result in results
    ] + full_page + footer)

    if pagination.message is None:
        try:
            message = await bot.send_photo(callback.from_user.id,
                                           pagination.manga.picture_url,
                                           f'{pagination.manga.name}\n'
                                           f'{pagination.manga.get_url()}', reply_markup=buttons)
            pagination.message = message
        except pyrogram.errors.BadRequest as e:
            file_name = f'pictures/{pagination.manga.unique()}.jpg'
            await pagination.manga.client.get_cover(pagination.manga, cache=True, file_name=file_name)
            message = await bot.send_photo(callback.from_user.id,
                                           f'./cache/{pagination.manga.client.name}/{file_name}',
                                           f'{pagination.manga.name}\n'
                                           f'{pagination.manga.get_url()}', reply_markup=buttons)
            pagination.message = message
    else:
        await bot.edit_message_reply_markup(
            callback.from_user.id,
            pagination.message.id,
            reply_markup=buttons
        )

users_lock = asyncio.Lock()


async def get_user_lock(chat_id: int):
    async with users_lock:
        lock = locks.get(chat_id)
        if not lock:
            locks[chat_id] = asyncio.Lock()
        return locks[chat_id]


async def chapter_click(client, data, chat_id):
    await pdf_queue.put(chapters[data], int(chat_id))
    logger.debug(f"Put chapter {chapters[data].name} to queue for user {chat_id} - queue size: {pdf_queue.qsize()}")


async def send_manga_chapter(client: Client, chapter, chat_id):
    db = DB()

    chapter_file = await db.get(ChapterFile, chapter.url)
    options = await db.get(MangaOutput, str(chat_id))
    options = options.output if options else (1 << 30) - 1

    error_caption = '\n'.join([
        f'{chapter.manga.name} - {chapter.name}',
        f'{chapter.get_url()}'
    ])

    download = not chapter_file
    download = download or options & OutputOptions.PDF and not chapter_file.file_id
    download = download or options & OutputOptions.CBZ and not chapter_file.cbz_id
    download = download and options & ((1 << len(OutputOptions)) - 1) != 0

    if download:
        pictures_folder = await chapter.client.download_pictures(chapter)
        if not chapter.pictures:
            return await client.send_message(chat_id,
                                          f'There was an error parsing this chapter or chapter is missing' +
                                          f', please check the chapter at the web\n\n{error_caption}')
        if env_vars["THUMB"]:
            thumb_path = env_vars["THUMB"]
        else:
            thumb_path = fld2thumb(pictures_folder)

    chapter_file = chapter_file or ChapterFile(url=chapter.url)

    if env_vars["FNAME"]:
        try:
            try: chap_num = re.search(r"Vol (\d+(?:\.\d+)?) Chapter (\d+(?:\.\d+)?)", chapter.name).group(2)
            except: chap_num = re.search(r"(\d+(?:\.\d+)?)", chapter.name).group(1)
            chap_name = clean(chapter.manga.name, 20)
            ch_name = env_vars["FNAME"]
            ch_name = ch_name.replace("{chap_num}", str(chap_num))
            ch_name = ch_name.replace("{chap_name}", str(chap_name))
        except Exception as e:
            print(e)
    else:
        ch_name = clean(f'{chapter.name} - {clean(chapter.manga.name, 25)}', 45)
        
    success_caption = f"{ch_name}\n [Read on website]({chapter.get_url()})"

    media_docs = []

    if options & OutputOptions.PDF:
        if chapter_file.file_id:
            media_docs.append(InputMediaDocument(chapter_file.file_id))
        else:
            try:
                pdf = await asyncio.get_running_loop().run_in_executor(None, fld2pdf, pictures_folder, ch_name)
            except Exception as e:
                logger.exception(f'Error creating pdf for {chapter.name} - {chapter.manga.name}\n{e}')
                return await client.send_message(chat_id, f'There was an error making the pdf for this chapter. '
                                                       f'Forward this message to the bot group to report the '
                                                       f'error.\n\n{error_caption}')
            media_docs.append(InputMediaDocument(pdf, thumb=thumb_path))

    if options & OutputOptions.CBZ:
        if chapter_file.cbz_id:
            media_docs.append(InputMediaDocument(chapter_file.cbz_id))
        else:
            try:
                cbz = await asyncio.get_running_loop().run_in_executor(None, fld2cbz, pictures_folder, ch_name)
            except Exception as e:
                logger.exception(f'Error creating cbz for {chapter.name} - {chapter.manga.name}\n{e}')
                return await client.send_message(chat_id, f'There was an error making the cbz for this chapter. '
               
