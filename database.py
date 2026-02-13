import aiosqlite
import logging
from pathlib import Path

# Log
logger = logging.getLogger(__name__)

DB_NAME = "bot.db"
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / DB_NAME

async def init_db():
    """Baza jadvallarini yaratish"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                audio TEXT,
                image TEXT,
                text TEXT,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("📦 Baza ishga tushdi: pages jadvali tayyor")

async def add_page(page_id: str, user_id: int):
    """Yangi sahifa qo'shish"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO pages (id, user_id) VALUES (?, ?)",
            (page_id, user_id)
        )
        await db.commit()

async def get_page(page_id: str) -> dict:
    """Sahifani olish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM pages WHERE id = ?", (page_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return {}

async def get_user_page(user_id: int) -> dict:
    """Userning sahifasini topish"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Oxirgi yaratilgan sahifani olamiz (agar ko'p bo'lsa)
        async with db.execute(
            "SELECT * FROM pages WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return {}

async def update_page(page_id: str, data: dict):
    """Sahifani yangilash (audio, image, text)"""
    # data dict bo'sh bo'lsa hech narsa qilmaymiz
    if not data:
        return

    set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
    values = list(data.values())
    values.append(page_id)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE pages SET {set_clause} WHERE id = ?",
            values
        )
        await db.commit()

async def delete_page_content(page_id: str):
    """Sahifa kontentini tozalash (o'chirish emas, null qilish)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE pages SET audio = NULL, image = NULL, text = NULL WHERE id = ?",
            (page_id,)
        )
        await db.commit()
