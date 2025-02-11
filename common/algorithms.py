"""This module contains common algorithms"""
import ast
import math

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
