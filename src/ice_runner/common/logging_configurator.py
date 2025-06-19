"""The module is used to configure logging using yaml file"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
from logging.handlers import TimedRotatingFileHandler

from os import path
import os

def get_logger(file_name: str, log_dir: str) -> logging.Logger:
    folder, name = path.split(file_name)
    name = name.split('.py')[0]

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    module = path.split(folder)[-1]
    log_directory = path.join(log_dir, module)
    full_name = path.join(log_directory, name)

    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    # new file every minute
    rotation_logging_handler = TimedRotatingFileHandler(full_name, 
                                when='h', 
                                interval=1, 
                                backupCount=5)
    rotation_logging_handler.setLevel(logging.DEBUG)

    format = u'%(asctime)s\t%(levelname)s\t%(filename)s:%(lineno)d\t%(message)s'
    rotation_logging_handler.setFormatter(logging.Formatter(format))
    rotation_logging_handler.suffix = '_%Y-%m-%d_%H-%M-%S.log'

    logger = logging.getLogger()
    logger.addHandler(rotation_logging_handler)

    return logger
