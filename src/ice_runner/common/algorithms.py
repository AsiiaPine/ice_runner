"""This module contains common algorithms"""
import ast
import math
from typing import Any

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
        raise e

def is_float(element: any) -> bool:
    # https://stackoverflow.com/a/20929881
    #If you expect None to be passed:
    if element is None: 
        return False
    try:
        float(element)
        return True
    except ValueError:
        return False

def get_type_from_str(type_str: str) -> Any:
    """The function returns the type of the specified type string"""
    if type_str == "int":
        return int
    if type_str == "float":
        return float
    if type_str == "str":
        return str
    raise ValueError(f"No type for {type_str}")
