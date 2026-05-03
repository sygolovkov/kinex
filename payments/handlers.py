from datetime import timedelta

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from asgiref.sync import sync_to_async
from django.utils import timezone

from core.models import Settings
from .models import Payment
from .services import create_payment

router = Router()

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='🔗 Генерация линка'), KeyboardButton(text='💳 Платежи')],
        [KeyboardButton(text='💰 Баланс'),           KeyboardButton(text='📤 Вывод')],
        [KeyboardButton(text='👤 Профиль'),           KeyboardButton(text='🆘 Поддержка')],
    ],
    resize_keyboard=True,
)

SKIP_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='Пропустить'), KeyboardButton(text='Отмена')]],
    resize_keyboard=True,
)

CANCEL_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='Отмена')]],
    resize_keyboard=True,
)

CONFIRM_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text='✅ Подтвердить', callback_data='pay_confirm'),
    InlineKeyboardButton(text='❌ Отменить',    callback_data='pay_cancel'),
]])

MENU_BUTTONS = {
    '💰 Баланс', '📤 Вывод',
    '👤 Профиль',
}

_PERIODS = [('day', 'День'), ('week', 'Неделя'), ('month', 'Месяц')]
_STATUSES = [('all', 'Все'), ('in_process', 'В процессе'), ('success', 'Успешно')]
_PERIOD_DELTA = {'day': timedelta(days=1), 'week': timedelta(weeks=1), 'month': timedelta(days=30)}
_PERIOD_LABEL = {'day': 'день', 'week': 'неделю', 'month': 'месяц'}
_STATUS_LABEL = {'all': 'все', 'in_process': 'в процессе', 'success': 'успешно'}
_STATUS_EMOJI = {0: '🆕', 1: '⏳', 2: '✅', 6: '❌', -6: '⚠️'}


def _payments_kb(period: str, status: str) -> InlineKeyboardMarkup:
    period_row = [
        InlineKeyboardButton(
            text=f'✓ {lbl}' if p == period else lbl,
            callback_data=f'pay_list:{p}:{status}',
        )
        for p, lbl in _PERIODS
    ]
    status_row = [
        InlineKeyboardButton(
            text=f'✓ {lbl}' if s == status else lbl,
            callback_data=f'pay_list:{period}:{s}',
        )
        for s, lbl in _STATUSES
    ]
    return InlineKeyboardMarkup(inline_keyboard=[period_row, status_row])


@sync_to_async
def _fetch_payments(manager, period: str, status: str):
    since = timezone.now() - _PERIOD_DELTA[period]
    qs = Payment.objects.filter(manager=manager, created_at__gte=since)
    if status == 'in_process':
        qs = qs.filter(status=Payment.Status.IN_PROCESS)
    elif status == 'success':
        qs = qs.filter(status=Payment.Status.SUCCESS)
    return list(qs.order_by('-created_at')[:15])


def _payments_text(payments, period: str, status: str) -> str:
    header = f'💳 Платежи за {_PERIOD_LABEL[period]} · {_STATUS_LABEL[status]}\n\n'
    if not payments:
        return header + 'Платежей не найдено.'
    total = sum(p.amount for p in payments)
    lines = [f'Найдено: {len(payments)} | Сумма: {total:,.2f} RUB\n']
    for p in payments:
        emoji = _STATUS_EMOJI.get(p.status, '❓')
        desc = (p.description[:30] + '…') if len(p.description) > 30 else (p.description or '—')
        lines.append(f'{emoji} {p.amount:,.2f} RUB · {desc}')
    return header + '\n'.join(lines)


class PaymentLink(StatesGroup):
    description = State()
    amount = State()
    confirm = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('Выберите раздел:', reply_markup=MENU)


# ── Генерация линка ──────────────────────────────────────────────────────────

@router.message(F.text == '🔗 Генерация линка')
async def link_start(message: Message, state: FSMContext):
    await state.set_state(PaymentLink.description)
    await message.answer(
        'Кому назначается платёж? (необязательно)',
        reply_markup=SKIP_KB,
    )


@router.message(PaymentLink.description)
async def link_description(message: Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.clear()
        await message.answer('Выберите раздел:', reply_markup=MENU)
        return

    description = '' if message.text == 'Пропустить' else message.text
    await state.update_data(description=description)
    await state.set_state(PaymentLink.amount)
    await message.answer('Введите сумму платежа (RUB):', reply_markup=CANCEL_KB)


@router.message(PaymentLink.amount)
async def link_amount(message: Message, state: FSMContext):
    if message.text == 'Отмена':
        await state.clear()
        await message.answer('Выберите раздел:', reply_markup=MENU)
        return

    try:
        amount = float((message.text or '').replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer('Введите корректную сумму:')
        return

    data = await state.get_data()
    description = data.get('description') or '—'
    await state.update_data(amount=amount)
    await state.set_state(PaymentLink.confirm)

    await message.answer(
        f'Подтвердите платёж:\n\n'
        f'💰 Сумма: {amount:.2f} RUB\n'
        f'📝 Назначение: {description}',
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer('Подтвердить?', reply_markup=CONFIRM_KB)


@router.callback_query(PaymentLink.confirm, F.data == 'pay_cancel')
async def link_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    if call.message:
        await call.message.answer('Выберите раздел:', reply_markup=MENU)


@router.callback_query(PaymentLink.confirm, F.data == 'pay_confirm')
async def link_confirm(call: CallbackQuery, state: FSMContext, manager):
    if not call.message:
        await call.answer()
        return

    data = await state.get_data()
    await state.clear()
    await call.answer()
    await call.message.answer('Создаю платёж...')

    try:
        result = await sync_to_async(create_payment)(
            amount=data['amount'],
            description=data.get('description', ''),
            manager=manager,
        )
    except Exception:
        await call.message.answer(
            '⚠️ Ошибка связи с платёжной системой. Попробуйте позже.',
            reply_markup=MENU,
        )
        return

    status_code = result.get('status_code')

    if status_code == -6:
        await call.message.answer(
            '❌ Платёжная система вернула ошибку. Попробуйте создать новый платёж.',
            reply_markup=MENU,
        )
        return

    text = '✅ Платёж создан\n\n'
    if result.get('url'):
        text += f'🔗 Ссылка: {result["url"]}'
    elif result.get('qr_code'):
        text += f'QR payload: {result["qr_code"]["payload"]}'
    else:
        text += str(result)

    await call.message.answer(text, reply_markup=MENU)


# ── Платежи ──────────────────────────────────────────────────────────────────

@router.message(F.text == '💳 Платежи')
async def payments_start(message: Message, manager):
    payments = await _fetch_payments(manager, 'day', 'all')
    await message.answer(
        _payments_text(payments, 'day', 'all'),
        reply_markup=_payments_kb('day', 'all'),
    )


@router.callback_query(F.data.startswith('pay_list:'))
async def payments_filter(call: CallbackQuery, manager):
    if not call.message:
        await call.answer()
        return
    _, period, status = call.data.split(':')
    payments = await _fetch_payments(manager, period, status)
    await call.message.edit_text(
        _payments_text(payments, period, status),
        reply_markup=_payments_kb(period, status),
    )
    await call.answer()


# ── Поддержка ────────────────────────────────────────────────────────────────

@router.message(F.text == '🆘 Поддержка')
async def support_handler(message: Message):
    settings = await sync_to_async(Settings.get)()
    text = 'По всем вопросам обращайтесь к Администратору'
    if settings.admin_telegram_username:
        username = settings.admin_telegram_username.lstrip('@')
        text += f'\n\n👤 @{username}'
    await message.answer(text)


# ── Остальные разделы ────────────────────────────────────────────────────────

@router.message(F.text.in_(MENU_BUTTONS))
async def menu_handler(message: Message):
    await message.answer('Раздел в разработке 🛠')
