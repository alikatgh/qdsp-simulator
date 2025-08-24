# trace.py
import json
from typing import Optional

class TraceSink:
    def __init__(self, path: Optional[str]=None):
        self.path = path
        self.fp = open(path, 'w') if path else None

    def emit_inst(self, cycle, inst, regs_before, regs_after, memops):
        rec = {
            "cycle": cycle,
            "pc": hex(inst.pc),
            "op": inst.op,
            "rd": inst.rd,
            "rs1": inst.rs1,
            "rs2": inst.rs2,
            "imm": inst.imm,
            "pred": inst.pred,
            "raw": hex(inst.raw),
            "regs_before": {k: hex(v) for k,v in regs_before.items()},
            "regs_after": {k: hex(v) for k,v in regs_after.items()},
            "memops": memops
        }
        line = json.dumps(rec)
        if self.fp:
            self.fp.write(line + "\n")
        else:
            print(line)

    def close(self):
        if self.fp:
            self.fp.close()
