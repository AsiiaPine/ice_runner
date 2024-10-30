import logging.config
from os import path
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

logging.config.dictConfig(log_conf_file)
