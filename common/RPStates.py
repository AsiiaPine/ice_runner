# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import ast
import math
from enum import IntEnum

class RunnerState(IntEnum):
    NOT_CONNECTED=-1,
    RUNNING=0,
    STARTING=1,
    STOPPED=2
    STOPPING=3,
    FAULT=4

def safe_literal_eval(val):
    try:
        res = ast.literal_eval(val)
        return res
    except ValueError as e:
        if 'nan' in val:
            # Replace standalone `nan` occurrences with `math.nan`
            val_fixed = val.replace('nan', 'math.nan')
            val_fixed = val_fixed.replace('null', 'math.nan')
            global_vars = {'math': math}  # Allow use of math namespace
            return eval(val_fixed, {"__builtins__": None}, global_vars)
        else:
            raise e
