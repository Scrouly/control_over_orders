import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from asgiref.sync import sync_to_async

from telegram.models import TelegramUser


@sync_to_async
def register_telegram_user(tg_user):
    """
    Создаёт нового пользователя или обновляет данные существующего.
    update_or_create — в отличие от get_or_create — всегда актуализирует
    username, first_name и last_name при повторных вызовах /start.
    """
    user, created = TelegramUser.objects.update_or_create(
        telegram_id=str(tg_user.id),
        defaults={
            'username':   tg_user.username,
            'first_name': tg_user.first_name,
            'last_name':  tg_user.last_name,
        }
    )
    return user, created


class Command(BaseCommand):
    help = 'Запуск Telegram-бота на aiogram 3.x (Long Polling)'

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.INFO)
        self.stdout.write(self.style.SUCCESS('Запуск Telegram-бота...'))
        try:
            asyncio.run(self.start_bot())
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write(self.style.WARNING('Бот остановлен.'))

    async def start_bot(self):
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        dp  = Dispatcher()

        @dp.message(CommandStart())
        async def cmd_start(message: types.Message):
            user, created = await register_telegram_user(message.from_user)
            name = message.from_user.first_name or "Пользователь"

            if created:
                text = (
                    f"Добрый день, <b>{name}</b>.\n\n"
                    f"Ваш аккаунт зарегистрирован в системе контроля исполнения"
                    f" поручений ОАО «Доломит».\n\n"
                    f"<b>Ваш Telegram ID:</b> <code>{message.from_user.id}</code>\n\n"
                    f"<i>После того как администратор привяжет ваш профиль к учётной"
                    f" записи сотрудника, вы начнёте получать уведомления о поручениях.</i>"
                )
            else:
                linked = user.employee is not None
                if linked:
                    emp = user.employee
                    pos  = emp.position.name   if emp.position   else "должность не указана"
                    dept = emp.department.name if emp.department else "подразделение не указано"
                    text = (
                        f"Добрый день, <b>{name}</b>.\n\n"
                        f"Ваш профиль привязан к учётной записи сотрудника:\n"
                        f"<b>{emp.last_name} {emp.first_name} {emp.middle_name}</b>\n"
                        f"<i>{pos}  ·  {dept}</i>\n\n"
                        f"Уведомления о поручениях будут поступать на этот аккаунт."
                    )
                else:
                    text = (
                        f"Добрый день, <b>{name}</b>.\n\n"
                        f"Ваш аккаунт зарегистрирован, однако ещё не привязан"
                        f" к учётной записи сотрудника.\n\n"
                        f"<i>Обратитесь к администратору системы для завершения настройки.</i>"
                    )

            await message.answer(text, parse_mode='HTML')

        await dp.start_polling(bot, skip_updates=True)