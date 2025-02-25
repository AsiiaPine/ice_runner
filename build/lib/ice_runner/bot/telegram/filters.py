"""The module defines filters for the Bot messages handlers"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message

class ChatIdFilter(BaseFilter):
    """The class is used to filter messages by chat id"""
    chat_id = None
    def __init__(self, chat_id: Union[int, list] = None, invert: bool = False):
        if chat_id is not None:
            self.chat_id = chat_id
        self.invert = invert

    async def __call__(self, message: Message) -> bool:
        """The function checks if the message is from the specified chat id"""
        if isinstance(self.chat_id, int):
            return message.chat.id == self.chat_id if not self.invert\
                                else message.chat.id != self.chat_id
        return message.chat.id in self.chat_id if not self.invert\
                                else message.chat.id not in self.chat_id
