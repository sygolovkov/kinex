from aiogram import BaseMiddleware
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.db.models import Q
from managers.models import Manager

ACCESS_DENIED = (
    'Доступ закрыт. Этот сервис доступен только авторизованным операторам. '
    'Для подключения свяжитесь с Администратором.'
)


@sync_to_async
def get_manager(user_id: int, username: str | None):
    q = Q(telegram_id=str(user_id))
    if username:
        q |= Q(telegram_username=username)
    manager = Manager.objects.filter(q, is_active=True).first()
    if manager:
        update_fields = []
        if not manager.telegram_id:
            manager.telegram_id = str(user_id)
            update_fields.append('telegram_id')
        if username and not manager.telegram_username:
            manager.telegram_username = username
            update_fields.append('telegram_username')
        if update_fields:
            update_fields.append('updated_at')
            manager.save(update_fields=update_fields)
    return manager


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
