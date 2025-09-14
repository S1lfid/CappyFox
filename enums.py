# enums.py
from enum import Enum, auto

class SelectionAction(Enum):
    SAVE = auto()
    COPY = auto()
    UPLOAD = auto()
    SCAN_QR = auto()
    CANCEL = auto()