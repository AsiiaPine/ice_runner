from enum import IntEnum

class RPStates(IntEnum):
    STOPPED  = 0
    RUNNING  = 1
    WAITING  = 2
    FAULT    = 3
