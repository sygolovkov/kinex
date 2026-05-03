from aiogram import Bot, Dispatcher
from core.models import get_bot_token

bot = Bot(token=get_bot_token())
dp = Dispatcher()
