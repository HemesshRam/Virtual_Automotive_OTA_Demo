from enum import Enum, auto


class ECUState(Enum):
    INIT = auto()
    READY = auto()
    DISCOVERED = auto()
    WAITING_FOR_UPDATE = auto()
    PROGRAMMING = auto()
    DOWNLOADING = auto()
    VERIFYING = auto()
    INSTALLING = auto()
    REBOOTING = auto()
    UPDATED = auto()
    CONFIRMED = auto()
    ROLLBACK_PENDING = auto()
    ERROR = auto()


class StateMachine:
    """
    Maintains the current operational state of an ECU.
    """

    def __init__(self):
        self._state = ECUState.INIT

    @property
    def current_state(self):
        return self._state

    def set_state(self, new_state: ECUState):
        print(f"[STATE] {self._state.name} -> {new_state.name}")
        self._state = new_state
