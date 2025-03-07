"""The module defines scheduler for the Telegram Bot"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import logging
import os
from typing import Dict
from aiogram import Bot
from aiogram.types import FSInputFile
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.mqtt.client import MqttClient
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
    def guard_runner(cls, runner_id: int):
        """The function guards the RP state and waits until it stops"""
        if runner_id in cls.jobs.keys():
            return
        cls.jobs[runner_id] = cls.scheduler.add_job(cls.check_rp_state, 'interval',
                                                seconds=1, kwargs={"runner_id": runner_id})
        logging.info("Waiting for RP %d to stop", runner_id)

    @classmethod
    async def check_rp_state(cls, runner_id: int):
        """The function checks the RP state and sends logs and stop reason
            if runner stops"""
        if runner_id not in MqttClient.rp_logs:
            return
        await cls.send_log(runner_id=runner_id)
        MqttClient.rp_logs.pop(runner_id)
        if runner_id not in MqttClient.rp_stop_handlers:
            return
        await cls.send_stop_reason(runner_id=runner_id)
        cls.jobs[runner_id].pause()
        cls.jobs[runner_id].remove()
        cls.jobs.pop(runner_id)
        MqttClient.rp_states.pop(runner_id)

    @classmethod
    async def send_log(cls, runner_id):
        """The function sends logs to the specified RPi"""
        log_files: Dict = MqttClient.rp_logs[runner_id]
        if not log_files:
            return
        for name, log_file in log_files.items():
            try:
                if os.stat(log_file).st_size == 0:
                    logging.warning("Empty log %s", name)
                    await cls.bot.send_message(cls.CHAT_ID, f"Файл {name} пустой")
                    continue
                log = FSInputFile(log_file)
                await cls.bot.send_document(cls.CHAT_ID, document=log, caption=name)
            except Exception as e:
                await cls.bot.send_message(cls.CHAT_ID, f"Ошибка при отправке лога {name}: {e}")
                logging.error("Error sending log %s: %s", name, e)
            await asyncio.sleep(1)
        MqttClient.rp_logs[runner_id] = {}

    @classmethod
    async def send_stop_reason(cls, runner_id: int):
        """The function sends stop reason to the specified RPi"""
        if runner_id not in MqttClient.rp_stop_handlers:
            logging.debug("No stop reason to send")
            return
        stop_reason = MqttClient.rp_stop_handlers[runner_id]
        await cls.bot.send_message(cls.CHAT_ID, f"Остановлено по причине: {stop_reason}")
        MqttClient.rp_stop_handlers[runner_id] = {}
