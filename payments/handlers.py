from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

router = Router()

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='🔗 Генерация линка'), KeyboardButton(text='💳 Платежи')],
        [KeyboardButton(text='💰 Баланс'),           KeyboardButton(text='📤 Вывод')],
        [KeyboardButton(text='👤 Профиль'),           KeyboardButton(text='🆘 Поддержка')],
    ],
    resize_keyboard=True,
)

MENU_BUTTONS = {
    '🔗 Генерация линка',
    '💳 Платежи',
    '💰 Баланс',
    '📤 Вывод',
    '👤 Профиль',
    '🆘 Поддержка',
}


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer('Выберите раздел:', reply_markup=MENU)


@router.message(F.text.in_(MENU_BUTTONS))
async def menu_handler(message: Message):
    await message.answer('Раздел в разработке 🛠')
