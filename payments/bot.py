import os
from aiogram import Bot, Dispatcher

bot = Bot(token=os.environ['BOT_TOKEN'])
dp = Dispatcher()
