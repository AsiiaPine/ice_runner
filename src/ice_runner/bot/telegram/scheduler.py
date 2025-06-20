"""The module defines scheduler for the Telegram Bot"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import logging
import os
from typing import Dict
from aiogram import Bot
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.mqtt.client import MqttClient
from bot.telegram.helper import send_media_group

class Scheduler:
    """The class is used to schedule tasks for the Telegram Bot"""
    bot: Bot
    scheduler: AsyncIOScheduler
    CHAT_ID: int
    jobs: Dict[int, Job] = {}

    @classmethod
    async def start(cls, bot: Bot, chat_id: int):
        """The function starts the scheduler"""
        cls.bot: Bot = bot
        cls.scheduler: AsyncIOScheduler = AsyncIOScheduler(timezone='Europe/Moscow')
        cls.CHAT_ID = chat_id
        cls.scheduler.start()
        while True:
            await asyncio.sleep(1)

    @classmethod
    def guard_runner(cls, runner_id: int):
        """The function guards the RP state and waits until it stops"""
        if runner_id in cls.scheduler.get_jobs():
            return
        cls.jobs[runner_id] = cls.scheduler.add_job(cls.check_rp_state, 'interval',
                                                seconds=1, kwargs={"runner_id": runner_id}).id
        logging.info("Waiting for RP %d to stop", runner_id)

    @classmethod
    async def check_rp_state(cls, runner_id: int):
        """The function checks the RP state and sends logs and stop reason
            if runner stops"""
        if runner_id not in MqttClient.rp_logs:
            return
        await cls._send_logs(runner_id=runner_id)
        MqttClient.rp_logs.pop(runner_id)
        if runner_id not in MqttClient.rp_stop_handlers:
            return
        await cls.send_stop_reason(runner_id=runner_id)
        cls.scheduler.remove_job(cls.jobs[runner_id])
        cls.jobs.pop(runner_id)
        MqttClient.rp_states.pop(runner_id)

    @classmethod
    async def _send_logs(cls, runner_id: int):
        """The function sends logs to the specified RPi"""
        log_files: Dict = MqttClient.rp_logs[runner_id]
        if not log_files:
            return

        all_logs_are_good = True
        for log_file in log_files.values():
            if os.stat(log_file).st_size == 0:
                all_logs_are_good = False
                break

        if all_logs_are_good:
            caption = "Обкатка завершена успешно."
        else:
            caption = "Обкатка завершена. Запись следующих логов не удалась:\n"

        files = []
        for name, log_file in log_files.items():
            if os.stat(log_file).st_size > 0:
                files.append(log_file)
            else:
                caption += f"- {name}\n"

        send_media_group(
            telegram_bot_token=os.getenv("BOT_TOKEN"),
            telegram_chat_id=os.getenv("CHAT_ID"),
            files=files,
            caption=caption
        )

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

    @classmethod
    def on_keyboard_interrupt(cls, task: asyncio.Task):
        """The function is called when KeyboardInterrupt is received"""
        logging.info("Scheduler shutting down...")
        cls.scheduler.shutdown()

        # Try to send exit message, but don't fail if bot is already down
        for job in cls.jobs.values():
            try:
                cls.scheduler.remove_job(job)
                logging.info(f"Removed job {job.id}")
            except Exception as e:
                logging.debug(f"Error removing job: {e}")
        cls.jobs.clear()
