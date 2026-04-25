import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
MASTER_CHAT_ID: int = int(os.environ["MASTER_CHAT_ID"])
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "orders.db")

DEVICE_LABELS = {
    "phone": "Телефон",
    "laptop": "Ноутбук",
    "tablet": "Планшет",
}
