"""
🔳 QR Code Generator Telegram Bot v2
Audio, surat, matn → chiroyli landing sahifa → QR kod
"""

import io
import os
import re
import json
import uuid
import logging
import asyncio
from pathlib import Path

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from dotenv import load_dotenv
import uvicorn
from server import app, load_pages, save_pages, MEDIA_DIR

# ─── Sozlamalar ─────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
PORT = int(os.getenv("PORT", "8000"))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN topilmadi! .env faylga token yozing.")

# ─── Logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Bot ────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# 🔒 Faqat shu adminlarga ruxsat
ADMIN_IDS = [730841948, 7290906386]
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

dp.include_router(router)

# ─── States ─────────────────────────────────────────────────
class PageStates(StatesGroup):
    waiting_audio = State()
    waiting_image = State()
    waiting_text = State()

# ─── Yordamchi ──────────────────────────────────────────────
MEDIA_DIR.mkdir(exist_ok=True)

# User sahifalari: {user_id: page_id}
def get_user_page(user_id: int) -> tuple[str, dict]:
    """User sahifasini olish yoki yangi yaratish"""
    pages = load_pages()
    # User ID bo'yicha sahifa qidirish
    for pid, pdata in pages.items():
        if pdata.get("user_id") == user_id:
            return pid, pdata
    # Yangi sahifa
    page_id = uuid.uuid4().hex[:10]
    pages[page_id] = {"user_id": user_id}
    save_pages(pages)
    return page_id, pages[page_id]


def generate_qr_code(data: str) -> bytes:
    """Chiroyli QR kod yaratish"""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=3,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255, 255, 255),
            front_color=(30, 58, 138),
        ),
    )

    if not isinstance(img, Image.Image):
        img = img.convert("RGB")

    qr_w, qr_h = img.size
    pad = 40
    cap_h = 50
    canvas = Image.new("RGB", (qr_w + pad * 2, qr_h + pad + cap_h + pad), (255, 255, 255))
    canvas.paste(img, (pad, pad // 2))

    draw = ImageDraw.Draw(canvas)
    caption = "📱 QR Code Generator Bot"
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except (OSError, IOError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), caption, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((canvas.width - tw) // 2, qr_h + pad), caption, fill=(100, 116, 139), font=font)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf.getvalue()


def get_main_keyboard(page_id: str) -> InlineKeyboardMarkup:
    """Asosiy tugmalar"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 Audio qo'shish", callback_data="add_audio"),
            InlineKeyboardButton(text="📸 Surat qo'shish", callback_data="add_image"),
        ],
        [
            InlineKeyboardButton(text="📝 Matn qo'shish", callback_data="add_text"),
        ],
        [
            InlineKeyboardButton(text="🔳 QR kod olish", callback_data="get_qr"),
            InlineKeyboardButton(text="👁 Sahifani ko'rish", callback_data="view_page"),
        ],
        [
            InlineKeyboardButton(text="🗑 Hammasini o'chirish", callback_data="delete_all"),
        ],
    ])


def get_page_status(page: dict) -> str:
    """Sahifa holatini ko'rsatish"""
    audio = "✅" if page.get("audio") else "❌"
    image = "✅" if page.get("image") else "❌"
    text = "✅" if page.get("text") else "❌"
    return (
        f"📋 <b>Sahifangiz holati:</b>\n\n"
        f"🎵 Audio: {audio}\n"
        f"📸 Surat: {image}\n"
        f"📝 Matn: {text}"
    )


# ─── /start ─────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    page_id, page = get_user_page(message.from_user.id)

    welcome = (
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🔳 Men <b>QR Code Generator</b> botman.\n\n"
        "📱 Menga <b>audio, surat yoki matn</b> yuboring —\n"
        "men chiroyli sahifa yarataman va QR kod beraman!\n\n"
        "QR kodni skanerlagan odam sizning sahifangizni\n"
        "ko'radi — ovozingizni eshitadi! 🎧\n\n"
        "─────────────────────\n\n"
        f"{get_page_status(page)}\n\n"
        "─────────────────────\n"
        "⬇️ Quyidagi tugmalardan birini tanlang:"
    )
    await message.answer(welcome, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(page_id))


# ─── /help ───────────────────────────────────────────────────
@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>Yordam</b>\n\n"
        "🎵 <b>Audio qo'shish</b> — ovozli xabar yoki audio fayl yuboring\n"
        "📸 <b>Surat qo'shish</b> — rasm yuboring\n"
        "📝 <b>Matn qo'shish</b> — matn yozing\n"
        "🔳 <b>QR kod</b> — sahifangiz uchun QR kod olasiz\n"
        "👁 <b>Ko'rish</b> — sahifangizni brauzerda ko'ring\n"
        "🗑 <b>O'chirish</b> — hammasini tozalash\n\n"
        "─────────────────────\n"
        "/start — Bosh menyu\n"
        "/help — Yordam\n"
        "/myqr — QR kodingizni olish"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)


# ─── /myqr ───────────────────────────────────────────────────
@router.message(Command("myqr"))
async def cmd_myqr(message: Message):
    page_id, page = get_user_page(message.from_user.id)
    page_url = f"{BASE_URL}/page/{page_id}"

    qr_bytes = generate_qr_code(page_url)
    photo = BufferedInputFile(file=qr_bytes, filename="qrcode.png")

    caption = (
        f"✅ <b>QR kodingiz tayyor!</b>\n\n"
        f"🔗 <b>Sahifa:</b>\n"
        f"<code>{page_url}</code>\n\n"
        f"📷 QR kodni skanerlang — sahifangiz ochiladi!"
    )
    await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML)


# ─── Callback: Audio qo'shish ───────────────────────────────
@router.callback_query(F.data == "add_audio")
async def cb_add_audio(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PageStates.waiting_audio)
    await callback.message.answer(
        "🎵 <b>Audio yuboring!</b>\n\n"
        "Ovozli xabar yoki audio fayl yuboring.\n"
        "Bekor qilish: /start",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ─── Callback: Surat qo'shish ───────────────────────────────
@router.callback_query(F.data == "add_image")
async def cb_add_image(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PageStates.waiting_image)
    await callback.message.answer(
        "📸 <b>Surat yuboring!</b>\n\n"
        "Rasm yuboring (faylsiz, surat sifatida).\n"
        "Bekor qilish: /start",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ─── Callback: Matn qo'shish ────────────────────────────────
@router.callback_query(F.data == "add_text")
async def cb_add_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PageStates.waiting_text)
    await callback.message.answer(
        "📝 <b>Matn yozing!</b>\n\n"
        "Sahifada ko'rsatiladigan matnni yozing.\n"
        "Bekor qilish: /start",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ─── Callback: QR kod olish ─────────────────────────────────
@router.callback_query(F.data == "get_qr")
async def cb_get_qr(callback: CallbackQuery):
    page_id, page = get_user_page(callback.from_user.id)
    page_url = f"{BASE_URL}/page/{page_id}"

    has_content = bool(page.get("audio") or page.get("image") or page.get("text"))
    if not has_content:
        await callback.message.answer(
            "⚠️ <b>Sahifangiz bo'sh!</b>\n\n"
            "Avval audio, surat yoki matn qo'shing.",
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
        return

    processing = await callback.message.answer("⏳ QR kod yaratilmoqda...")
    qr_bytes = generate_qr_code(page_url)
    photo = BufferedInputFile(file=qr_bytes, filename="qrcode.png")

    caption = (
        f"✅ <b>QR kodingiz tayyor!</b>\n\n"
        f"🔗 <b>Sahifa:</b>\n"
        f"<code>{page_url}</code>\n\n"
        f"{get_page_status(page)}\n\n"
        f"📷 QR kodni skanerlang — sahifangiz ochiladi!"
    )
    await callback.message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML)
    await processing.delete()
    await callback.answer()


# ─── Callback: Sahifani ko'rish ──────────────────────────────
@router.callback_query(F.data == "view_page")
async def cb_view_page(callback: CallbackQuery):
    page_id, _ = get_user_page(callback.from_user.id)
    page_url = f"{BASE_URL}/page/{page_id}"

    await callback.message.answer(
        f"👁 <b>Sahifangiz:</b>\n\n"
        f"🔗 <a href=\"{page_url}\">{page_url}</a>\n\n"
        f"Linkni bosing yoki brauzerga nusxalang!",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=False
    )
    await callback.answer()


# ─── Callback: Hammasini o'chirish ───────────────────────────
@router.callback_query(F.data == "delete_all")
async def cb_delete_all(callback: CallbackQuery):
    page_id, page = get_user_page(callback.from_user.id)
    pages = load_pages()

    # Media fayllarni o'chirish
    for key in ["audio", "image"]:
        filename = page.get(key)
        if filename:
            filepath = MEDIA_DIR / filename
            if filepath.exists():
                filepath.unlink()

    # Sahifani tozalash
    pages[page_id] = {"user_id": callback.from_user.id}
    save_pages(pages)

    await callback.message.answer(
        "🗑 <b>Sahifangiz tozalandi!</b>\n\n"
        "Yangi kontent qo'shish uchun /start bosing.",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ─── Audio qabul qilish ─────────────────────────────────────
@router.message(PageStates.waiting_audio, F.audio | F.voice)
async def receive_audio(message: Message, state: FSMContext):
    page_id, page = get_user_page(message.from_user.id)
    pages = load_pages()

    # Eski audioni o'chirish
    old_audio = page.get("audio")
    if old_audio and (MEDIA_DIR / old_audio).exists():
        (MEDIA_DIR / old_audio).unlink()

    # Yangi audio yuklash
    if message.audio:
        file_id = message.audio.file_id
        ext = "mp3"
    else:
        file_id = message.voice.file_id
        ext = "ogg"

    filename = f"{page_id}_audio.{ext}"
    filepath = MEDIA_DIR / filename
    await bot.download(file_id, destination=filepath)

    # Saqlash
    pages[page_id]["audio"] = filename
    save_pages(pages)
    await state.clear()

    await message.answer(
        f"✅ <b>Audio saqlandi!</b>\n\n"
        f"{get_page_status(pages[page_id])}\n\n"
        "Bosh menyu: /start",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(page_id)
    )


# ─── Surat qabul qilish ─────────────────────────────────────
@router.message(PageStates.waiting_image, F.photo)
async def receive_image(message: Message, state: FSMContext):
    page_id, page = get_user_page(message.from_user.id)
    pages = load_pages()

    # Eski suratni o'chirish
    old_image = page.get("image")
    if old_image and (MEDIA_DIR / old_image).exists():
        (MEDIA_DIR / old_image).unlink()

    # Eng katta o'lchamli suratni olish
    photo = message.photo[-1]

    filename = f"{page_id}_image.jpg"
    filepath = MEDIA_DIR / filename
    await bot.download(photo.file_id, destination=filepath)

    # Saqlash
    pages[page_id]["image"] = filename
    save_pages(pages)
    await state.clear()

    await message.answer(
        f"✅ <b>Surat saqlandi!</b>\n\n"
        f"{get_page_status(pages[page_id])}\n\n"
        "Bosh menyu: /start",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(page_id)
    )


# ─── Matn qabul qilish ──────────────────────────────────────
@router.message(PageStates.waiting_text, F.text)
async def receive_text(message: Message, state: FSMContext):
    page_id, page = get_user_page(message.from_user.id)
    pages = load_pages()

    pages[page_id]["text"] = message.text
    save_pages(pages)
    await state.clear()

    await message.answer(
        f"✅ <b>Matn saqlandi!</b>\n\n"
        f"{get_page_status(pages[page_id])}\n\n"
        "Bosh menyu: /start",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(page_id)
    )


# ─── URL QR kod (eski funksiya ham ishlaydi) ────────────────
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

@router.message(F.text)
async def handle_url(message: Message):
    """Oddiy URL yuborilsa — QR kod yaratish (eski funksiya)"""
    urls = URL_PATTERN.findall(message.text.strip())
    if not urls:
        await message.answer(
            "💡 <b>Nima qilmoqchisiz?</b>\n\n"
            "Bosh menyu uchun /start bosing.\n"
            "Yoki istalgan link yuboring — QR kod yarataman!",
            parse_mode=ParseMode.HTML
        )
        return

    for url in urls:
        try:
            processing = await message.answer("⏳ QR kod yaratilmoqda...")
            qr_bytes = generate_qr_code(url)
            photo = BufferedInputFile(file=qr_bytes, filename="qrcode.png")
            caption = (
                f"✅ <b>QR kod tayyor!</b>\n\n"
                f"🔗 <code>{url}</code>\n\n"
                f"📷 Skanerlang — link ochiladi!"
            )
            await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML)
            await processing.delete()
        except Exception as e:
            logger.error(f"QR kod xato: {e}")
            await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.", parse_mode=ParseMode.HTML)


# ─── Botni ishga tushirish ──────────────────────────────────
async def start_bot():
    """Bot polling"""
    logger.info("🤖 Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def start_server():
    """FastAPI server"""
    logger.info(f"🌐 Server ishga tushmoqda: port {PORT}")
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    logger.info("🚀 QR Code Generator Bot + Server ishga tushmoqda...")
    logger.info(f"🌐 Landing sahifalar: {BASE_URL}")

    # Bot va Server'ni parallel ishga tushirish
    await asyncio.gather(
        start_bot(),
        start_server()
    )


if __name__ == "__main__":
    asyncio.run(main())
