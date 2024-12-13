import datetime
import errno
import logging.config
from logging.handlers import QueueHandler
from os import path
import os
import sys
import yaml

# disable existing modules
for name, logger in logging.root.manager.loggerDict.items():
    logger.disabled=True
    logger.propagate=False

# open the file in read mode
log_conf_file = None
absolute_path = path.dirname(path.abspath(__file__))

with open(absolute_path + path.normpath('/logg_config.yml'), 'r') as file:
    log_conf_file = yaml.safe_load(file)

def getLogger(filepath):
    # Get full path of the script
    folder, name = path.split(filepath)
    folder = path.split(folder)[-1]
    log_directory = path.join('logs', folder)
    log_filename = datetime.datetime.now().strftime(f"{name}_%Y_%m_%d-%H:%M:%S.log")
    dir = path.join(path.split(__file__)[0], log_directory)
    if not os.path.exists(dir):
        os.makedirs(dir)
    full_log_path = path.join(dir, log_filename)
    print(full_log_path)
    # Update the filename in the logging configuration
    log_conf_file['handlers']['fileHandler']['filename'] = full_log_path
    # Apply the modified logging configuration
    logging.config.dictConfig(log_conf_file)
    logger = logging.getLogger(name)
    logger.propagate = True
    return logger


import concurrent.futures 
import logging

class AsyncLogger():
    def __init__(self, name):
        self.name = name
        self.logger = logging.getLogger(name)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1) 

    def info(self, msg, *args):
        self.executor.submit(logging.info, msg, *args)

    def debug(self, msg, *args):
        self.executor.submit(logging.debug, msg, *args)

    def warning(self, msg, *args):
        self.executor.submit(logging.warning, msg, *args)

    def error(self, msg, *args):
        self.executor.submit(logging.error, msg, *args)

    def critical(self, msg, *args):
        self.executor.submit(logging.critical, msg, *args)

    def exception(self, msg, *args, exc_info=True):
        self.executor.submit(logging.exception, msg, *args, exc_info=exc_info)
