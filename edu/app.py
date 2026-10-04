"""Telegram ilovasini yig‘ish: handlerlar, ishga tushirishdagi ishlar (miya yuklash), xatolarni ushlash."""
from __future__ import annotations

import asyncio
import logging

from telegram import BotCommand, Update
from telegram.ext import (Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from . import admin, handlers, miya
from .ai import AIService
from .config import Config
from .db import Database

log = logging.getLogger(__name__)

COMMANDS = [
    BotCommand("start", "Bosh menyu"),
    BotCommand("dars", "Dars tayyorlash"),
    BotCommand("darslar", "AI bilan tayyorlangan darslarim"),
    BotCommand("yordam", "Yordam"),
    BotCommand("bekor", "Joriy amalni bekor qilish"),
]


async def _post_init(app: Application) -> None:
    cfg: Config = app.bot_data["cfg"]
    db: Database = app.bot_data["db"]
    if app.bot_data.get("seed_miya", True):
        try:
            result = await asyncio.to_thread(miya.seed_from_bundle, db)
            log.info(result)
        except Exception:
            log.exception("Miyani yuklashda xato")
    try:
        await app.bot.set_my_commands(COMMANDS)
    except Exception as exc:
        log.warning("Buyruqlar ro‘yxatini o‘rnatib bo‘lmadi: %s", exc)
    log.info("Bot tayyor. Tayyor darslar: %s. AI: matn=%s, rasm=%s. Adminlar: %s",
             db.count_catalog(), cfg.text_provider or "yo‘q", cfg.image_provider or "yo‘q",
             ", ".join(map(str, cfg.admin_ids)) or "yo‘q")


async def _post_shutdown(app: Application) -> None:
    jobs = list(app.bot_data.get("jobs", set()))
    for job in jobs:
        job.cancel()
    if jobs:
        await asyncio.gather(*jobs, return_exceptions=True)
    ai: AIService = app.bot_data.get("ai")
    if ai:
        await ai.close()
    db: Database = app.bot_data.get("db")
    if db:
        db.close()


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Kutilmagan xato: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.callback_query:
        try:
            await update.callback_query.answer("Xatolik yuz berdi, qayta urinib ko‘ring.")
        except Exception:
            pass


def build_application(cfg: Config, db: Database | None = None, ai: AIService | None = None,
                      request=None, rate_limit: bool = True, seed_miya: bool = True) -> Application:
    db = db or Database(cfg.database_url, cfg.sqlite_path)
    ai = ai or AIService(cfg)
    builder: ApplicationBuilder = (Application.builder().token(cfg.token).concurrent_updates(True)
                                   .post_init(_post_init).post_shutdown(_post_shutdown))
    if request is not None:
        builder = builder.request(request).get_updates_request(request)
    else:
        builder = builder.connect_timeout(20).read_timeout(40).write_timeout(60).pool_timeout(30)
    if rate_limit:
        try:
            from telegram.ext import AIORateLimiter
            builder = builder.rate_limiter(AIORateLimiter(max_retries=3))
        except (ImportError, RuntimeError) as exc:
            log.warning("Rate limiter o‘rnatilmadi (pip install \"python-telegram-bot[rate-limiter]\"): %s", exc)
    app = builder.build()
    app.bot_data.update(cfg=cfg, db=db, ai=ai, running=set(), jobs=set(),
                        sem=asyncio.Semaphore(cfg.max_parallel), seed_miya=seed_miya)

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler(["dars", "new"], handlers.new_lesson))
    app.add_handler(CommandHandler("darslar", handlers.archive))
    app.add_handler(CommandHandler(["yordam", "help"], handlers.help_cmd))
    app.add_handler(CommandHandler(["bekor", "cancel"], handlers.cancel_cmd))
    app.add_handler(CommandHandler("admin", admin.admin_cmd))
    app.add_handler(CommandHandler("stat", admin.stat_cmd))
    app.add_handler(CommandHandler("miya_import", admin.miya_import_cmd))
    app.add_handler(CommandHandler("miya_export", admin.miya_export_cmd))
    app.add_handler(CommandHandler("block", admin.block_cmd))
    app.add_handler(CommandHandler("unblock", admin.unblock_cmd))

    app.add_handler(CallbackQueryHandler(handlers.wizard_cb, pattern=r"^w:"))
    app.add_handler(CallbackQueryHandler(handlers.action_cb, pattern=r"^x:"))
    app.add_handler(CallbackQueryHandler(handlers.archive_cb, pattern=r"^a:"))
    app.add_handler(CallbackQueryHandler(handlers.help_cb, pattern=r"^h:"))
    app.add_handler(CallbackQueryHandler(admin.admin_cb, pattern=r"^adm:"))
    app.add_handler(CallbackQueryHandler(handlers.unknown_cb))

    private = filters.ChatType.PRIVATE   # guruhlarda oddiy xabarlarga javob bermaydi (faqat buyruqlar)
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, handlers.text_router))
    app.add_handler(MessageHandler(private & (filters.VOICE | filters.AUDIO), handlers.voice_router))
    app.add_handler(MessageHandler(private & filters.Document.ALL, handlers.document_router))
    app.add_handler(MessageHandler(private & ~filters.COMMAND & ~filters.StatusUpdate.ALL, handlers.other_router))
    app.add_error_handler(_on_error)
    return app
