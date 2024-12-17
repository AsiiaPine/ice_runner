import ast
from enum import IntEnum
import math

# RPStatesDict = {
#     -1: "NOT_CONNECTED",
#     0: "RUNNING",
#     1: "STARTING",
#     2: "STOPPED",
#     3: "STOPPING",
#     4: "FAULT"
# }
RPStatesDict = {
    "NOT_CONNECTED" : -1,
    "RUNNING" : 0,
    "STARTING" : 1,
    "STOPPED" : 2,
    "STOPPING" : 3,
    "FAULT" : 4
}

# class RPStates(IntEnum):
#     NOT_CONNECTED = -1
#     RUNNING  = 0
#     STARTING = 1
#     STOPPED  = 2
#     STOPPING = 3
#     FAULT    = 4

def safe_literal_eval(val):
    try:
        res = ast.literal_eval(val)
        return res
    except ValueError as e:
        print("val ",val)
        if 'nan' in val:
            # Replace standalone `nan` occurrences with `math.nan`
            val_fixed = val.replace('nan', 'math.nan')
            val_fixed = val_fixed.replace('null', 'math.nan')
            global_vars = {'math': math}  # Allow use of math namespace
            return eval(val_fixed, {"__builtins__": None}, global_vars)
        else:
            raise e
