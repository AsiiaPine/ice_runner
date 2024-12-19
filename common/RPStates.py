import ast
import math

RPStatesDict = {
    "NOT_CONNECTED" : -1,
    "RUNNING" : 0,
    "STARTING" : 1,
    "STOPPED" : 2,
    "STOPPING" : 3,
    "FAULT" : 4
}

def get_rp_state_name(state):
    if state == RPStatesDict["NOT_CONNECTED"]:
        return "NOT_CONNECTED"
    elif state == RPStatesDict["RUNNING"]:
        return "RUNNING"
    elif state == RPStatesDict["STARTING"]:
        return "STARTING"
    elif state == RPStatesDict["STOPPED"]:
        return "STOPPED"
    elif state == RPStatesDict["STOPPING"]:
        return "STOPPING"
    elif state == RPStatesDict["FAULT"]:
        return "FAULT"
    else:
        return "UNKNOWN"

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
