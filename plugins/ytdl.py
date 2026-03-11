# Enhanced ytdl.py with rate limiting and inline keyboard
# Save-Restricted-Content-Bot-v3 - Fixed version

import yt_dlp
import os
import tempfile
import time
import asyncio
import random
import string
import requests
import logging
import math
import re
from datetime import datetime
from shared_client import client, app
from telethon import events, Button
from telethon.tl.types import DocumentAttributeVideo
from utils.func import get_video_metadata, screenshot
from devgagantools import fast_upload
from concurrent.futures import ThreadPoolExecutor
import aiohttp 
import aiofiles
from config import YT_COOKIES, INSTA_COOKIES, FREEMIUM_LIMIT, PREMIUM_LIMIT
from mutagen.id3 import ID3, TIT2, TPE1, COMM, APIC
from mutagen.mp3 import MP3
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

thread_pool = ThreadPoolExecutor(max_workers=4)
ongoing_downloads = {}
daily_downloads = {}
pending_urls = {}

TELEGRAM_MAX_SIZE = 2 * 1024 * 1024 * 1024
MAX_FREE_DAILY = FREEMIUM_LIMIT
MAX_PREMIUM_DAILY = PREMIUM_LIMIT

# Track if MongoDB is available
mongodb_available = True

def is_premium_user_safe(user_id):
    """Safe wrapper for is_premium_user that handles MongoDB errors"""
    global mongodb_available
    try:
        from utils.func import is_premium_user
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return False
        else:
            return loop.run_until_complete(is_premium_user(user_id))
    except Exception as e:
        logger.warning(f"MongoDB error in premium check: {e}")
        mongodb_available = False
        return False

def d_thumbnail(thumbnail_url, save_path):
    try:
        response = requests.get(thumbnail_url, stream=True)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return save_path
    except Exception as e:
        logger.error(f"Failed to download thumbnail: {e}")
        return None

def get_random_string(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def is_valid_url(url):
    url_pattern = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return bool(url_pattern.match(url))

async def check_rate_limit(user_id, is_premium, increment=True):
    today = datetime.now().date()
    if user_id not in daily_downloads:
        daily_downloads[user_id] = {"date": today, "count": 0}
    if daily_downloads[user_id]["date"] != today:
        daily_downloads[user_id] = {"date": today, "count": 0}
    limit = MAX_PREMIUM_DAILY if is_premium else MAX_FREE_DAILY
    if daily_downloads[user_id]["count"] >= limit:
        return False, limit
    if increment:
        daily_downloads[user_id]["count"] += 1
    return True, limit

def is_valid_cookies(cookies_content):
    if not cookies_content or len(cookies_content.strip()) < 10:
        return False
    stripped = cookies_content.strip().lower()
    if stripped.startswith("#") and "cookie" in stripped:
        return False
    if "write" in stripped and "here" in stripped:
        return False
    has_domain = ".youtube.com" in cookies_content or ".instagram.com" in cookies_content or ".facebook.com" in cookies_content
    has_true_false = "TRUE" in cookies_content or "FALSE" in cookies_content
    has_tab_separated = "\t" in cookies_content
    return (has_domain or has_true_false) and has_tab_separated

async def fetch_video_info(url, ydl_opts):
    def sync_fetch():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    return await asyncio.get_event_loop().run_in_executor(thread_pool, sync_fetch)

async def process_audio(client, event, url, cookies_env_var=None, reply_message=None):
    cookies = cookies_env_var if cookies_env_var else None
    temp_cookie_path = None
    if cookies and is_valid_cookies(cookies):
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
            temp_cookie_file.write(cookies)
            temp_cookie_path = temp_cookie_file.name
    else:
        cookies = None

    random_filename = f"@team_RSK_pro_{event.sender_id}"
    download_path = f"{random_filename}.m4a"

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': f"{random_filename}.%(ext)s",
        'cookiefile': temp_cookie_path,
        'quiet': False,
        'noplaylist': True,
    }

    progress_msg = reply_message if reply_message else await event.reply("**__Starting audio download...__**")

    try:
        info_ydl_opts = {'cookiefile': temp_cookie_path, 'quiet': True}
        info_dict = await fetch_video_info(url, info_ydl_opts)
        title = info_dict.get('title', 'Extracted Audio') if info_dict else 'Extracted Audio'
        
        await progress_msg.edit("**__Downloading audio...__**")
        
        def sync_download_audio():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.download([url])
        
        await asyncio.get_event_loop().run_in_executor(thread_pool, sync_download_audio)

        if os.path.exists(download_path):
            await progress_msg.edit("**__Adding metadata...__**")
            try:
                if download_path.endswith('.mp3'):
                    def edit_metadata():
                        audio_file = MP3(download_path, ID3=ID3)
                        try:
                            audio_file.add_tags()
                        except:
                            pass
                        audio_file.tags["TIT2"] = TIT2(encoding=3, text=title)
                        audio_file.tags["TPE1"] = TPE1(encoding=3, text="Team RSK")
                        audio_file.save()
                    await asyncio.to_thread(edit_metadata)
            except Exception as e:
                logger.warning(f"Could not add metadata: {e}")

        chat_id = event.chat_id
        if os.path.exists(download_path):
            await progress_msg.delete()
            prog = await client.send_message(chat_id, "**__Starting Upload...__**")
            file_size = os.path.getsize(download_path)
            if file_size > TELEGRAM_MAX_SIZE:
                await prog.edit(f"**__Audio file too large ({file_size/(1024*1024):.2f} MB). Telegram limit is 2GB.__**")
                await prog.delete()
            else:
                uploaded = await fast_upload(client, download_path, reply=prog, name=None,
                    progress_bar_function=lambda done, total: progress_callback(done, total, chat_id))
                await client.send_file(chat_id, uploaded, caption=f"**{title}**\n\n**__Powered by Team RSK__**")
                if prog:
                    await prog.delete()
        else:
            await event.reply("**__Audio file not found!__**")

    except Exception as e:
        logger.exception("Error during audio extraction")
        try:
            await progress_msg.edit("please enter a valid url")
        except:
            await event.reply("please enter a valid url")
    finally:
        if os.path.exists(download_path):
            try:
                os.remove(download_path)
            except:
                pass
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            try:
                os.remove(temp_cookie_path)
            except:
                pass

async def process_video(client, event, url, cookies_env_var=None, reply_message=None):
    logger.info(f"Received link: {url}")
    cookies = cookies_env_var if cookies_env_var else None
    random_filename = get_random_string() + ".mp4"
    download_path = os.path.abspath(random_filename)

    temp_cookie_path = None
    if cookies and cookies.strip() and not cookies.startswith("#") and len(cookies) > 10:
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as temp_cookie_file:
            temp_cookie_file.write(cookies)
            temp_cookie_path = temp_cookie_file.name

    thumbnail_file = None
    metadata = {'width': None, 'height': None, 'duration': None}

    ydl_opts = {
        'outtmpl': download_path,
        'format': 'best',
        'cookiefile': temp_cookie_path if temp_cookie_path else None,
        'writethumbnail': False,
        'quiet': False,
    }

    progress_msg = reply_message if reply_message else await event.reply("**__Starting download...__**")

    try:
        info_dict = await fetch_video_info(url, ydl_opts)
        if not info_dict:
            await progress_msg.edit("**__Could not fetch video information.__**")
            return

        title = info_dict.get('title', 'Powered by Team RSK') if info_dict else 'Powered by Team RSK'
        duration = info_dict.get('duration', 0)

        if duration and duration > 3 * 3600:
            await progress_msg.edit("**__Video longer than 3 hours. Aborted.__**")
            return

        await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))

        k = await get_video_metadata(download_path)
        W = k['width']
        H = k['height']
        D = k['duration']
        metadata['width'] = info_dict.get('width') or W
        metadata['height'] = info_dict.get('height') or H
        metadata['duration'] = int(info_dict.get('duration') or 0) or D

        thumbnail_url = info_dict.get('thumbnail', None)
        THUMB = None

        if thumbnail_url:
            thumbnail_file = os.path.join(tempfile.gettempdir(), get_random_string() + ".jpg")
            downloaded_thumb = d_thumbnail(thumbnail_url, thumbnail_file)
            if downloaded_thumb:
                THUMB = downloaded_thumb

        if not THUMB and os.path.exists(download_path):
            if thumbnail_file and os.path.exists(thumbnail_file):
                try:
                    os.remove(thumbnail_file)
                except:
                    pass
            thumbnail_file = None
            
            THUMB = await screenshot(download_path, metadata['duration'], str(event.sender_id))
            if THUMB and os.path.basename(THUMB) != f"{event.sender_id}.jpg":
                thumbnail_file = THUMB

        chat_id = event.chat_id

        if os.path.exists(download_path):
            file_size = os.path.getsize(download_path)
            if file_size > TELEGRAM_MAX_SIZE:
                await progress_msg.edit("**__File too large. Splitting and uploading...__**")
                await split_and_upload_file(app, chat_id, download_path, f"**{title}**")
                await progress_msg.delete()
            else:
                await progress_msg.delete()
                prog = await client.send_message(chat_id, "**__Starting Upload...__**")
                try:
                    uploaded = await fast_upload(client, download_path, reply=prog,
                        progress_bar_function=lambda done, total: progress_callback(done, total, chat_id))
                    await client.send_file(event.chat_id, uploaded, caption=f"**{title}**",
                        attributes=[DocumentAttributeVideo(duration=metadata['duration'], w=metadata['width'],
                            h=metadata['height'], supports_streaming=True)],
                        thumb=THUMB if THUMB else None)
                finally:
                    if prog:
                        try:
                            await prog.delete()
                        except:
                            pass
        else:
            await event.reply("**__File not found after download.__**")

    except Exception as e:
        logger.exception("Error during download/upload")
        try:
            await progress_msg.edit("please enter a valid url")
        except:
            await event.reply("please enter a valid url")
    finally:
        if os.path.exists(download_path):
            try:
                os.remove(download_path)
            except:
                pass
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            try:
                os.remove(temp_cookie_path)
            except:
                pass
        if thumbnail_file and os.path.exists(thumbnail_file):
            try:
                os.remove(thumbnail_file)
            except:
                pass

async def split_and_upload_file(app, sender, file_path, caption):
    if not os.path.exists(file_path):
        await app.send_message(sender, "❌ File not found!")
        return

    file_size = os.path.getsize(file_path)
    start = await app.send_message(sender, f"ℹ️ File size: {file_size / (1024 * 1024):.2f} MB")
    PART_SIZE = int(1.9 * 1024 * 1024 * 1024)

    part_number = 0
    try:
        async with aiofiles.open(file_path, mode="rb") as f:
            while True:
                chunk = await f.read(PART_SIZE)
                if not chunk:
                    break

                base_name, file_ext = os.path.splitext(file_path)
                part_file = f"{base_name}.part{str(part_number).zfill(3)}{file_ext}"

                async with aiofiles.open(part_file, mode="wb") as part_f:
                    await part_f.write(chunk)

                edit = await app.send_message(sender, f"⬆️ Uploading part {part_number + 1}...")
                part_caption = f"{caption} \n\n**Part : {part_number + 1}**"

                await app.send_document(sender, document=part_file, caption=part_caption,
                    progress=progress_bar, progress_args=("Uploading...", edit, time.time()))

                await edit.delete()
                try:
                    os.remove(part_file)
                except:
                    pass

                part_number += 1

        await start.delete()
    except Exception as e:
        await app.send_message(sender, f"**__Error: {e}__**")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

def progress_callback(done, total, user_id):
    percent = (done / total) * 100
    completed_blocks = int(percent // 10)
    progress_bar = "♦" * completed_blocks + "◇" * (10 - completed_blocks)
    done_mb = done / (1024 * 1024)
    total_mb = total / (1024 * 1024)
    return (
        f"╭──────────────────╮\n"
        f"│ **__Uploading...__**\n"
        f"├──────────\n"
        f"│ {progress_bar}\n\n"
        f"│ **__Progress:__** {percent:.2f}%\n"
        f"│ **__Done:__** {done_mb:.2f} MB / {total_mb:.2f} MB\n"
        f"╰──────────────────╯\n\n"
        f"**__Powered by Team RSK__**"
    )

async def progress_bar(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
    if round(diff % 10) == 0 or current == total:
        percentage = (current * 100) / total
        try:
            await message.edit(text=f"{ud_type}\n│ Progress: {percentage:.2f}%")
        except:
            pass

# Command Handlers - FIXED: Using Pyrogram app for inline buttons

@client.on(events.NewMessage(pattern="/adl"))
async def adl_handler(event):
    user_id = event.sender_id

    if user_id in ongoing_downloads:
        await event.reply("**You already have an ongoing download. Please wait!**")
        return

    if len(event.message.text.split()) < 2:
        # FIXED: Use Pyrogram app with reply_markup (not Telethon's buttons)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎧 Download Audio", callback_data="adl_help")],
            [InlineKeyboardButton("❓ Help", callback_data="help_ytdl")]
        ])
        await app.send_message(
            chat_id=event.chat_id,
            text="**Usage:** `/adl <video-link>`\n\n"
            "Send your link below 👇\n\n"
            "**Supported:** YouTube, Instagram, Facebook, Twitter, 100+ sites.",
            reply_markup=keyboard
        )
        return

    url = event.message.text.split()[1]

    if not is_valid_url(url):
        await event.reply("**Please provide a valid URL!**")
        return

    premium = is_premium_user_safe(user_id)
    allowed, limit = await check_rate_limit(user_id, premium)

    if not allowed:
        await event.reply(
            f"**❌ Daily limit reached!**\n\n"
            f"You have reached {limit} downloads/day.\n"
            f"Premium: {MAX_PREMIUM_DAILY}, Free: {MAX_FREE_DAILY}"
        )
        return

    ongoing_downloads[user_id] = True

    try:
        if "instagram.com" in url:
            await process_audio(client, event, url, cookies_env_var=INSTA_COOKIES)
        elif "youtube.com" in url or "youtu.be" in url:
            await process_audio(client, event, url, cookies_env_var=YT_COOKIES)
        else:
            await process_audio(client, event, url)

        await event.reply(f"**✅ Download complete!**\n**Downloads today:** {daily_downloads[user_id]['count']}/{limit}")

    except Exception as e:
        logger.exception("Error in /adl handler")
        await event.reply("please enter a valid url")
    finally:
        ongoing_downloads.pop(user_id, None)

@client.on(events.NewMessage(pattern="/dl"))
async def dl_handler(event):
    user_id = event.sender_id

    if user_id in ongoing_downloads:
        await event.reply("**You already have an ongoing download. Please wait!**")
        return

    if len(event.message.text.split()) < 2:
        # FIXED: Use Pyrogram app with reply_markup (not Telethon's buttons)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬇️ Download Video", callback_data="dl_help")],
            [InlineKeyboardButton("🎧 Download Audio", callback_data="adl_help")],
            [InlineKeyboardButton("❓ Help", callback_data="help_ytdl")]
        ])
        await app.send_message(
            chat_id=event.chat_id,
            text="**Usage:** `/dl <video-link>`\n\n"
            "Send your link below 👇\n\n"
            "**Supported:** YouTube, Instagram, Facebook, Twitter, 100+ sites.",
            reply_markup=keyboard
        )
        return

    url = event.message.text.split()[1]

    if not is_valid_url(url):
        await event.reply("**Please provide a valid URL!**")
        return

    premium = is_premium_user_safe(user_id)
    allowed, limit = await check_rate_limit(user_id, premium)

    if not allowed:
        await event.reply(
            f"**❌ Daily limit reached!**\n\n"
            f"You have reached {limit} downloads/day.\n"
            f"Premium: {MAX_PREMIUM_DAILY}, Free: {MAX_FREE_DAILY}"
        )
        return

    ongoing_downloads[user_id] = True

    try:
        if "instagram.com" in url:
            await process_video(client, event, url, "INSTA_COOKIES")
        elif "youtube.com" in url or "youtu.be" in url:
            await process_video(client, event, url, "YT_COOKIES")
        else:
            await process_video(client, event, url, None)

        await event.reply(f"**✅ Download complete!**\n**Downloads today:** {daily_downloads[user_id]['count']}/{limit}")

    except Exception as e:
        logger.exception("Error in /dl handler")
        await event.reply("please enter a valid url")
    finally:
        ongoing_downloads.pop(user_id, None)

# URL pattern for detecting links
URL_PATTERN = re.compile(
    r'(?:https?|ftp)://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
)

@client.on(events.NewMessage(incoming=True))
async def handle_url_messages(event):
    if not event.is_private:
        return
    if event.message.text and event.message.text.startswith('/'):
        return

    text = event.message.text or ""
    urls = URL_PATTERN.findall(text)

    if not urls:
        return

    url = urls[0]

    # FIXED: Use Pyrogram inline keyboard
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬇️ Download Video", callback_data="dl"),
         InlineKeyboardButton("🎧 Download Audio", callback_data="adl")],
        [InlineKeyboardButton("▶️ Preview", callback_data="preview")]
    ])

    user_id = event.sender_id
    pending_urls[user_id] = url
    
    premium = is_premium_user_safe(user_id)
    allowed, limit = await check_rate_limit(user_id, premium, increment=False)

    limit_text = f"({daily_downloads[user_id]['count']}/{limit})" if user_id in daily_downloads else ""

    # FIXED: Use Pyrogram app
    await app.send_message(
        event.chat_id,
        f"**🔗 URL Detected:** `{url[:50]}...`\n\n**Select an action:** {limit_text}",
        reply_markup=keyboard
    )

@client.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode() if isinstance(event.data, bytes) else event.data
    user_id = event.sender_id

    url = None
    if data == "dl":
        url = pending_urls.get(user_id, None)
        if not url:
            await event.answer("❌ URL not found. Please send the link again.", alert=True)
            return
    elif data == "adl":
        url = pending_urls.get(user_id, None)
        if not url:
            await event.answer("❌ URL not found. Please send the link again.", alert=True)
            return
    elif data == "preview":
        url = pending_urls.get(user_id, None)
        if not url:
            await event.answer("❌ URL not found. Please send the link again.", alert=True)
            return
    elif data.startswith("dl_"):
        url = data[3:]
    elif data.startswith("adl_"):
        url = data[4:]
    elif data.startswith("preview_"):
        url = data[8:]
    
    premium = is_premium_user_safe(user_id)
    allowed, limit = await check_rate_limit(user_id, premium)

    if not allowed:
        await event.answer(f"❌ Daily limit reached! ({limit})", alert=True)
        return

    if data == "dl" or data.startswith("dl_"):
        await event.edit("**⬇️ Starting video download...**")
        ongoing_downloads[user_id] = True
        try:
            chat_id = event.chat_id
            if "instagram.com" in url:
                await process_video(client, event, url, "INSTA_COOKIES", reply_message=None)
            elif "youtube.com" in url or "youtu.be" in url:
                await process_video(client, event, url, "YT_COOKIES", reply_message=None)
            else:
                await process_video(client, event, url, None, reply_message=None)
        except Exception as e:
            await event.answer(f"**Error:** `{e}`", show_alert=True)
        finally:
            ongoing_downloads.pop(user_id, None)

    elif data == "adl" or data.startswith("adl_"):
        await event.edit("**🎧 Starting audio download...**")
        ongoing_downloads[user_id] = True
        try:
            if "instagram.com" in url:
                await process_audio(client, event, url, cookies_env_var=INSTA_COOKIES, reply_message=None)
            elif "youtube.com" in url or "youtu.be" in url:
                await process_audio(client, event, url, cookies_env_var=YT_COOKIES, reply_message=None)
            else:
                await process_audio(client, event, url, reply_message=None)
        except Exception as e:
            await event.answer(f"**Error:** `{e}`", show_alert=True)
        finally:
            ongoing_downloads.pop(user_id, None)

    elif data == "preview" or data.startswith("preview_"):
        await event.edit("**🔍 Fetching video info...**")
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            def get_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            info = await asyncio.get_event_loop().run_in_executor(thread_pool, get_info)

            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', 'Unknown')
            view_count = info.get('view_count', 0)

            if duration:
                duration_str = f"{duration//3600}:{(duration%3600)//60:02d}:{duration%60:02d}"
            else:
                duration_str = "Unknown"

            preview_text = (
                f"**📹 Video Preview**\n\n"
                f"**Title:** {title}\n"
                f"**Duration:** {duration_str}\n"
                f"**Uploader:** {uploader}\n"
                f"**Views:** {view_count:,}\n"
                f"**URL:** {url}"
            )

            keyboard = [
                [Button.inline("⬇️ Download Video", data=f"dl_{url}"),
                 Button.inline("🎧 Download Audio", data=f"adl_{url}")]
            ]

            await event.edit(preview_text, buttons=keyboard)

        except Exception as e:
            await event.edit(f"**❌ Could not fetch video info:** `{e}`")

    elif data == "dl_help":
        await event.edit("**⬇️ Download Video Help**\n\nSend `/dl <video-link>` to download a video.")

    elif data == "adl_help":
        await event.edit("**🎧 Download Audio Help**\n\nSend `/adl <video-link>` to download audio as MP3.")

    elif data == "help_ytdl":
        await event.edit(
            f"**❓ YouTube Downloader Help**\n\n"
            "**Commands:**\n"
            "• `/dl <url>` - Download video\n"
            "• `/adl <url>` - Download audio (MP3)\n\n"
            f"**Limits:**\n• Free: {MAX_FREE_DAILY}/day\n• Premium: {MAX_PREMIUM_DAILY}/day"
        )

    await event.answer()
