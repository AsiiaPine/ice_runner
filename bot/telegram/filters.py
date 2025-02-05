# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message

class ChatIdFilter(BaseFilter):  # [1]
    CHAT_ID = None
    def __init__(self, chat_id: Union[int, list] = None, invert: bool = False):
        if chat_id is not None:
            self.CHAT_ID = chat_id
        self.invert = invert

    async def __call__(self, message: Message) -> bool:  # [3]
        if isinstance(self.CHAT_ID, int):
            return message.chat.id == self.CHAT_ID if not self.invert else message.chat.id != self.CHAT_ID
        else:
            return message.chat.id in self.CHAT_ID if not self.invert else message.chat.id not in self.CHAT_ID
