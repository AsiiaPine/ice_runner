"""The module defines scheduler for the Telegram Bot"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
from typing import Dict
from aiogram import Bot
from aiogram.types import FSInputFile
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from mqtt.client import MqttClient
from common.RunnerState import RunnerState


class Scheduler:
    """The class is used to schedule tasks for the Telegram Bot"""
    bot: Bot
    scheduler: AsyncIOScheduler
    CHAT_ID: int
    jobs: Dict[int, Job] = {}

    @classmethod
    def start(cls, bot: Bot, chat_id: int):
        """The function starts the scheduler"""
        cls.bot: Bot = bot
        cls.scheduler: AsyncIOScheduler = AsyncIOScheduler(timezone='Europe/Moscow')
        cls.CHAT_ID = chat_id
        cls.scheduler.start()

    @classmethod
    def guard_runner(cls, rp_id: int):
        """The function guards the RP state and waits until it stops"""
        cls.jobs[rp_id] = cls.scheduler.add_job(cls.check_rp_state, 'interval',
                                                seconds=1, kwargs={"rp_id": rp_id})
        logging.info("Waiting for RP %d to stop", rp_id)

    @classmethod
    async def check_rp_state(cls, rp_id: int):
        """The function checks the RP state and sends logs and stop reason
            if runner stops"""
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
            cls.jobs.pop(rp_id)
            MqttClient.rp_states.pop(rp_id)
            MqttClient.rp_logs.pop(rp_id)

    @classmethod
    async def send_log(cls, rp_id):
        """The function sends logs to the specified RPi"""
        log_files: Dict = MqttClient.rp_logs[rp_id]
        if not log_files:
            logging.debug("No logs to send")
            return
        for name, log_file in log_files.items():
            logging.info("Sending log %s", name)
            try:
                log = FSInputFile(log_file)
                await cls.bot.send_document(cls.CHAT_ID, document=log, caption=name)
            except Exception as e:
                await cls.bot.send_message(cls.CHAT_ID, f"Ошибка при отправке лога {name}: {e}")
                logging.error("Error sending log %s: %s", name, e)
        MqttClient.rp_logs[rp_id] = {}

    @classmethod
    async def send_stop_reason(cls, rp_id: int):
        """The function sends stop reason to the specified RPi"""
        if rp_id not in MqttClient.rp_stop_handlers:
            logging.debug("No stop reason to send")
            return
        stop_reason = MqttClient.rp_stop_handlers[rp_id]
        await cls.bot.send_message(cls.CHAT_ID, f"Остановлено по причине: {stop_reason}")
        MqttClient.rp_stop_handlers[rp_id] = {}
