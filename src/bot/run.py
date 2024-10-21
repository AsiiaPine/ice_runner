import asyncio
import logging
import sys
from os import getenv
from aiogram import flags

from aiogram import Bot, Dispatcher, types

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Filter, Command, CommandObject
from aiogram.types import Message

# Bot token can be obtained via https://t.me/BotFather
TOKEN = getenv("BOT_TOKEN")

# All handlers should be attached to the Router (or Dispatcher)

dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_settimer(
        message: Message,
        command: CommandObject
):
    # Если не переданы никакие аргументы, то
    # command.args будет None
    if command.args is None:
        await message.answer(
            "Ошибка: не переданы аргументы"
        )
        return
    # Пробуем разделить аргументы на две части по первому встречному пробелу
    try:
        delay_time, text_to_send = command.args.split(" ", maxsplit=1)
    # Если получилось меньше двух частей, вылетит ValueError
    except ValueError:
        await message.answer(
            "Ошибка: неправильный формат команды. Пример:\n"
            "/settimer <time> <message>"
        )
        return
    await message.answer(
        "Таймер добавлен!\n"
        f"Время: {delay_time}\n"
        f"Текст: {text_to_send}"
    )

# Define a filter to handle commands /status /start /help /stop /echo
class MyFilter(Filter):
    def __init__(self, my_text: str) -> None:
        self.my_text = my_text

    async def __call__(self, message: Message) -> bool:
        return message.text == self.my_text

CommandStart    = MyFilter("/start")
CommandStatus   = MyFilter("/status")
CommandHelp     = MyFilter("/help")
CommandStop     = MyFilter("/stop")
CommandEcho     = MyFilter("/echo")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply("start")

# Хэндлер на команду /test2
async def cmd_test2(message: types.Message):
    await message.reply("Test 2")

# Где-то в другом месте, например, в функции main():
dp.message.register(cmd_test2, Command("test2"))

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    # Most event objects have aliases for API methods that can be called in events' context
    # For example if you want to answer to incoming message you can use `message.answer(...)` alias
    # and the target chat will be passed to :ref:`aiogram.methods.send_message.SendMessage`
    # method automatically or call API method directly via
    # Bot instance: `bot.send_message(chat_id=message.chat.id, ...)`
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")

@dp.message(CommandHelp())
async def command_help_handler(message: Message, ) -> None:
    """
    This handler receives messages with `/help` command
    """
    # Send a message with a list of commands
    await message.answer(
        "I can help you with the following commands:\n"
        "/start - to start the automatic ICE runner\n"
        "/status - to get the status of the connected ICE\n"
        "/help - to get this message\n"
        "/stop - to stop the automatic running immediately."
    )

@dp.message(..., flags={'--max-temperature': , '--max-gas-throttle', '--max-vibration'})
async def echo_handler(message: Message) -> None:
    """
    Handler will forward receive a message back to the sender

    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    try:
        # Send a copy of the received message
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        # But not all the types is supported to be copied so need to handle it
        await message.answer("Nice try!")


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
