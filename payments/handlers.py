from datetime import timedelta
from decimal import Decimal

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
from managers.models import ProfileChangeRequest
from .models import Payment, Withdrawal
from .services import calculate_available_balance, create_payment, create_withdrawal, get_balance_stats, get_usdt_rate

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

MENU_BUTTONS = set()

_BAL_PERIODS = [('today', 'Сегодня'), ('month', 'Месяц')]
_BAL_PERIOD_LABEL = {'today': 'сегодня', 'month': 'за месяц'}


def _balance_kb(period: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f'✓ {lbl}' if p == period else lbl,
            callback_data=f'bal:{p}',
        )
        for p, lbl in _BAL_PERIODS
    ]])

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


class ProfileChange(StatesGroup):
    value = State()


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


# ── Баланс ───────────────────────────────────────────────────────────────────

@sync_to_async
def _fetch_balance(manager, period: str) -> dict:
    stats = get_balance_stats(manager, period)
    stats['usdt_rate'] = get_usdt_rate()
    return stats


def _balance_text(stats: dict, period: str) -> str:
    label = _BAL_PERIOD_LABEL[period]
    rate = stats.get('usdt_rate', Decimal('0'))

    def usdt(rub: Decimal) -> str:
        if rate > 0:
            return f' (~{(rub / rate).quantize(Decimal("0.01"))} USDT)'
        return ''

    lines = [f'💰 Баланс {label}\n']
    if rate > 0:
        lines.append(f'💱 Курс USDT (Garantex): {rate:,.2f} RUB\n')
    lines += [
        f'✅ Успешных платежей:   {stats["total"]:,.2f} RUB{usdt(stats["total"])}',
        f'📤 Выведено:            {stats["withdrawn"]:,.2f} RUB{usdt(stats["withdrawn"])}',
        f'🏦 Удержано комиссий:   {stats["retained_fee"]:,.2f} RUB{usdt(stats["retained_fee"])}',
        f'\n💵 Доступно к выводу: {stats["available"]:,.2f} RUB{usdt(stats["available"])}',
    ]
    return '\n'.join(lines)


@router.message(F.text == '💰 Баланс')
async def balance_start(message: Message, manager):
    stats = await _fetch_balance(manager, 'today')
    await message.answer(
        _balance_text(stats, 'today'),
        reply_markup=_balance_kb('today'),
    )


@router.callback_query(F.data.startswith('bal:'))
async def balance_filter(call: CallbackQuery, manager):
    if not call.message:
        await call.answer()
        return
    _, period = call.data.split(':')
    if period not in ('today', 'month'):
        await call.answer()
        return
    stats = await _fetch_balance(manager, period)
    await call.message.edit_text(
        _balance_text(stats, period),
        reply_markup=_balance_kb(period),
    )
    await call.answer()


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


# ── Вывод средств ────────────────────────────────────────────────────────────

WITHDRAW_CONFIRM_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text='✅ Подать заявку', callback_data='withdraw_confirm'),
    InlineKeyboardButton(text='❌ Отмена',         callback_data='withdraw_cancel'),
]])


@sync_to_async
def _get_withdrawal_info(manager):
    balance = calculate_available_balance(manager)
    active = Withdrawal.objects.filter(
        manager=manager, status=Withdrawal.Status.PENDING,
    ).order_by('-created_at').first()
    return balance, active


@router.message(F.text == '📤 Вывод')
async def withdrawal_start(message: Message, manager):
    balance, active = await _get_withdrawal_info(manager)

    if active:
        await message.answer(
            f'📤 Вывод средств\n\n'
            f'У вас уже есть активная заявка на вывод.\n'
            f'💰 Сумма: {active.amount:,.2f} RUB\n'
            f'📅 Дата подачи: {timezone.localtime(active.created_at).strftime("%d.%m.%Y %H:%M")}\n\n'
            f'Заявка будет обработана администратором вручную.',
        )
        return

    if not manager.usdt_wallet:
        await message.answer(
            '📤 Вывод средств\n\n'
            '⚠️ USDT-кошелёк не указан. Обратитесь к администратору для его добавления.',
        )
        return

    if balance <= 0:
        await message.answer(
            '📤 Вывод средств\n\n'
            'Доступных средств для вывода нет.\n\n'
            'К выводу учитываются успешные платежи, совершённые до начала текущего дня.',
        )
        return

    await message.answer(
        f'📤 Вывод средств\n\n'
        f'Доступно к выводу: {balance:,.2f} RUB\n\n'
        f'Средства будут переведены на USDT-кошелёк:\n'
        f'<code>{manager.usdt_wallet}</code>\n\n'
        f'Подтвердите заявку:',
        parse_mode='HTML',
        reply_markup=WITHDRAW_CONFIRM_KB,
    )


@router.callback_query(F.data == 'withdraw_cancel')
async def withdrawal_cancel(call: CallbackQuery):
    await call.answer()
    if call.message:
        await call.message.answer('Выберите раздел:', reply_markup=MENU)


@router.callback_query(F.data == 'withdraw_confirm')
async def withdrawal_confirm(call: CallbackQuery, manager):
    await call.answer()
    if not call.message:
        return

    balance, active = await _get_withdrawal_info(manager)

    if active:
        await call.message.answer(
            '⚠️ У вас уже есть активная заявка на вывод.',
            reply_markup=MENU,
        )
        return

    if balance <= 0:
        await call.message.answer(
            '⚠️ Нет доступных средств для вывода.',
            reply_markup=MENU,
        )
        return

    try:
        withdrawal = await sync_to_async(create_withdrawal)(manager)
    except ValueError as e:
        if str(e) == 'active_withdrawal_exists':
            await call.message.answer(
                '⚠️ У вас уже есть активная заявка на вывод.',
                reply_markup=MENU,
            )
        elif str(e) == 'no_funds_available':
            await call.message.answer(
                '⚠️ Нет доступных средств для вывода.',
                reply_markup=MENU,
            )
        else:
            await call.message.answer(
                '⚠️ Ошибка при создании заявки. Попробуйте позже.',
                reply_markup=MENU,
            )
        return
    except Exception:
        await call.message.answer(
            '⚠️ Ошибка при создании заявки. Попробуйте позже.',
            reply_markup=MENU,
        )
        return

    await call.message.answer(
        f'✅ Заявка на вывод создана\n\n'
        f'💰 Сумма: {withdrawal.amount:,.2f} RUB\n'
        f'Администратор обработает заявку вручную.',
        reply_markup=MENU,
    )


# ── Профиль ──────────────────────────────────────────────────────────────────

PROFILE_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text='📧 Изменить email',        callback_data='profile_change:email'),
    InlineKeyboardButton(text='💳 Изменить USDT кошелёк', callback_data='profile_change:usdt_wallet'),
]])


@sync_to_async
def _get_active_change_request(manager):
    return ProfileChangeRequest.objects.filter(
        manager=manager, status=ProfileChangeRequest.Status.PENDING,
    ).order_by('-created_at').first()


def _profile_text(manager, active_request) -> str:
    lines = [
        '👤 Профиль\n',
        f'📛 Имя:            {manager.name or "—"}',
        f'📧 Email:          {manager.email or "—"}',
        f'💳 USDT кошелёк:  {manager.usdt_wallet or "—"}',
        f'💹 Комиссия:       {manager.commission}%',
    ]
    if active_request:
        field_label = ProfileChangeRequest.Field(active_request.field).label
        lines.append(
            f'\n⏳ Активная заявка на изменение: {field_label}\n'
            f'   Новое значение: {active_request.new_value}\n'
            f'   Ожидает обработки администратором.'
        )
    return '\n'.join(lines)


@router.message(F.text == '👤 Профиль')
async def profile_start(message: Message, manager):
    active = await _get_active_change_request(manager)
    kb = None if active else PROFILE_KB
    await message.answer(_profile_text(manager, active), reply_markup=kb)


@router.callback_query(F.data.startswith('profile_change:'))
async def profile_change_start(call: CallbackQuery, state: FSMContext, manager):
    await call.answer()
    if not call.message:
        return

    active = await _get_active_change_request(manager)
    if active:
        await call.message.answer(
            '⚠️ У вас уже есть активная заявка на изменение профиля. '
            'Дождитесь её обработки.',
        )
        return

    _, field = call.data.split(':')
    if field not in ('email', 'usdt_wallet'):
        return

    field_label = ProfileChangeRequest.Field(field).label
    await state.update_data(profile_field=field)
    await state.set_state(ProfileChange.value)
    await call.message.answer(
        f'Введите новый {field_label}:',
        reply_markup=CANCEL_KB,
    )


@router.message(ProfileChange.value)
async def profile_change_value(message: Message, state: FSMContext, manager):
    if message.text == 'Отмена':
        await state.clear()
        await message.answer('Выберите раздел:', reply_markup=MENU)
        return

    new_value = (message.text or '').strip()
    if not new_value:
        await message.answer('Значение не может быть пустым. Введите ещё раз:')
        return

    data = await state.get_data()
    field = data['profile_field']
    await state.clear()

    await sync_to_async(ProfileChangeRequest.objects.create)(
        manager=manager,
        field=field,
        new_value=new_value,
    )

    field_label = ProfileChangeRequest.Field(field).label
    await message.answer(
        f'✅ Заявка на изменение {field_label} отправлена.\n'
        f'Новое значение: {new_value}\n\n'
        f'Администратор рассмотрит заявку в ближайшее время.',
        reply_markup=MENU,
    )


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
