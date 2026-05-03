from aiogram import BaseMiddleware
from aiogram.types import Message
from asgiref.sync import sync_to_async
from managers.models import Manager

ACCESS_DENIED = (
    'Доступ закрыт. Этот сервис доступен только авторизованным операторам. '
    'Для подключения свяжитесь с Администратором.'
)


@sync_to_async
def get_manager(user_id: int, username: str | None):
    candidates = [str(user_id)]
    if username:
        candidates += [username, f'@{username}']
    return Manager.objects.filter(telegram_id__in=candidates, is_active=True).first()


class ManagerAccessMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        if not event.from_user:
            return
        manager = await get_manager(event.from_user.id, event.from_user.username)
        if not manager:
            await event.answer(ACCESS_DENIED)
            return
        data['manager'] = manager
        return await handler(event, data)
