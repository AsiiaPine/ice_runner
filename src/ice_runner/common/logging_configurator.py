"""The module is used to configure logging using yaml file"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import datetime
import logging.config
from os import path
import os
import yaml

def get_logger(script_part: str, log_dir: str) -> logging.Logger:
    for _, parent_logger in logging.root.manager.loggerDict.items():
        parent_logger.disabled = True
        parent_logger.propagate = False

    # open the file in read mode
    absolute_path = path.dirname(path.abspath(__file__))

    with open(os.path.join(absolute_path, path.normpath('logg_config.yml')), 'r') as file:
        log_conf_file = yaml.safe_load(file)

    # Get full path of the script
    folder, name = path.split(script_part)
    module = path.split(folder)[-1]
    log_directory = path.join(log_dir, module)
    log_filename = datetime.datetime.now().strftime(f"{name}_%Y_%m_%d-%H_%M_%S.log")

    if not os.path.exists(log_directory):
        os.makedirs(log_directory)
    full_log_path = path.join(log_directory, log_filename)
    print(full_log_path)

    # Update the filename in the logging configuration
    log_conf_file['handlers']['fileHandler']['filename'] = full_log_path
    # Apply the modified logging configuration
    logging.config.dictConfig(log_conf_file)
    logger = logging.getLogger(name)

    return logger
