"""
Fanlar integratsiyasi — darsga tayyorlovchi Telegram bot.
Ishga tushirish: python main.py   (sozlamalar: README.md)
"""
import logging
import sys

from telegram import Update

from edu.app import build_application
from edu.config import load_config


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    # httpx so‘rov manzillarida bot tokeni bo‘ladi — logga chiqmasin
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    cfg = load_config()
    if not cfg.token:
        print("❌ TOKEN topilmadi. Serverning Variables bo‘limiga TOKEN=<BotFather bergan token> qo‘shing.")
        sys.exit(1)
    if not cfg.admin_ids:
        logging.warning("ADMIN_ID ko‘rsatilmagan — admin panel ishlamaydi.")
    app = build_application(cfg)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
