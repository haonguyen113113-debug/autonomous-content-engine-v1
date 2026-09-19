from dataclasses import dataclass
@dataclass
class Job:
    id: str
    type: str
    status: str
    payload: dict
