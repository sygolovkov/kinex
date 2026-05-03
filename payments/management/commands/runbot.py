import asyncio
from django.core.management.base import BaseCommand
from payments.bot import bot, dp
from payments.middleware import ManagerAccessMiddleware
from payments import handlers


class Command(BaseCommand):
    help = 'Run Telegram bot'

    def handle(self, *args, **kwargs):
        dp.message.middleware(ManagerAccessMiddleware())
        dp.callback_query.middleware(ManagerAccessMiddleware())
        dp.include_router(handlers.router)
        asyncio.run(dp.start_polling(bot))
