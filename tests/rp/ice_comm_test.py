import asyncio
import logging
import os
import sys
import time

import pytest
from typing import Any, Callable, Dict, List, Tuple
import dronecan
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.common.device_manager import DeviceManager

from common.RunnerState import RunnerState
from common.IceRunnerConfiguration import IceRunnerConfiguration
from raspberry.can_control.node import CanNode, start_dronecan_handlers, stop_dronecan_handlers
from raspberry.can_control.ice_commander import ICECommander
from common.ICEState import ICEState, RecipState
from StoppableThread import StoppableThread

logger = logging.getLogger()
logger.level = logging.INFO


class BaseTest():
    def setup_method(self, test_method):
        CanNode.state = ICEState()
    
    def teardown_method(self, test_method):
        CanNode.messages = {}
    
    async def wait_for_bool(self, expression: Callable, timeout: float = 3) -> bool:
        start_time = time.time()
        while (not expression()) and (time.time() - start_time < timeout):
            await self.commander.spin()
            await asyncio.sleep(0.1)
        if expression():
            return True
        return False

