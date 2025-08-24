# inst.py
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class Inst:
    raw: int
    pc: int
    op: str
    rd: Optional[int] = None
    rs1: Optional[int] = None
    rs2: Optional[int] = None
    imm: Optional[int] = None
    pred: Optional[int] = None
    endpkt: bool = True
    meta: Dict[str, Any] = None
