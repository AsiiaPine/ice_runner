# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
from typing import Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from common.RPStates import RunnerState
from mqtt.client import MqttClient
from aiogram import Bot
from aiogram.types import FSInputFile
from apscheduler.job import Job

scheduler = AsyncIOScheduler(timezone='Europe/Moscow')

class Scheduler:
    bot: Bot
    scheduler: AsyncIOScheduler
    CHAT_ID: int
    jobs: Dict[int, Job]

    @classmethod
    def start(cls, bot: Bot, chat_id: int):
        cls.bot: Bot = bot
        cls.scheduler: AsyncIOScheduler = AsyncIOScheduler(timezone='Europe/Moscow')
        cls.jobs = {}
        cls.CHAT_ID = chat_id
        cls.scheduler.start()

    @classmethod
    def wait_untill_stop(cls, rp_id: int):
        cls.jobs[rp_id] = cls.scheduler.add_job(cls.check_rp_state, 'interval', seconds=1, kwargs={"rp_id": rp_id})
        logging.info(f"Waiting for RP {rp_id} to stop")

    @classmethod
    async def check_rp_state(cls, rp_id: int):
        if rp_id not in MqttClient.rp_states:
            return
        if MqttClient.rp_states[rp_id] == RunnerState.STOPPED:
            if rp_id not in MqttClient.rp_logs:
                return
            if rp_id not in MqttClient.rp_stop_handlers:
                return
            await cls.send_log(rp_id=rp_id)
            await cls.send_stop_reason(rp_id=rp_id)
            cls.jobs[rp_id].pause()
            cls.jobs[rp_id].remove()

    @classmethod
    async def send_log(cls, rp_id):
        log_files: Dict = MqttClient.rp_logs[rp_id]
        for name, log_file in log_files.items():
            logging.info(f"Sending log {name}")
            try:
                log = FSInputFile(log_file)
                await cls.bot.send_document(cls.CHAT_ID, document=log, caption=name)
            except Exception as e:
                await cls.bot.send_message(cls.CHAT_ID, f"Ошибка при отправке лога {name}: {e}")
                logging.getLogger(__name__).error(f"Error sending log {name}: {e}")
        MqttClient.rp_logs[rp_id] = {}

    @classmethod
    async def send_stop_reason(cls, rp_id: int):
        if rp_id not in MqttClient.rp_stop_handlers:
            return
        stop_reason = MqttClient.rp_stop_handlers[rp_id]
        await cls.bot.send_message(cls.CHAT_ID, f"Остановлено по причине: {stop_reason}")
        MqttClient.rp_stop_handlers[rp_id] = {}
