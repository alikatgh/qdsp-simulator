# fu.py - functional unit classes
from dataclasses import dataclass
from typing import Optional
from time import time

@dataclass
class FU:
    name: str
    latency: int
    busy_until: int = 0
    cur_inst: Optional[object] = None

    def can_accept(self, curr_cycle: int) -> bool:
        return curr_cycle >= self.busy_until

    def start(self, inst, curr_cycle: int):
        self.cur_inst = inst
        self.busy_until = curr_cycle + self.latency

    def tick(self, curr_cycle: int):
        if self.cur_inst and curr_cycle >= self.busy_until:
            finished = self.cur_inst
            self.cur_inst = None
            return finished
        return None

class ALU(FU):
    def __init__(self, name, latency=1):
        super().__init__(name, latency)

class LSU(FU):
    def __init__(self, name, latency=3):
        super().__init__(name, latency)

class VEC(FU):
    def __init__(self, name, latency=2, lanes=4):
        super().__init__(name, latency)
        self.lanes = lanes
