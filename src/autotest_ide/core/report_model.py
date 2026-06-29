from dataclasses import dataclass


@dataclass
class ReportStep:
    index: int
    name: str
    status: str
    screenshot: str
    error: str
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "status": self.status,
            "screenshot": self.screenshot,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class ReportSummary:
    script: str
    device_type: str
    device_serial: str
    start_time: float
    end_time: float
    total_steps: int
    passed: int
    failed: int
    status: str

    def to_dict(self) -> dict:
        return {
            "script": self.script,
            "device_type": self.device_type,
            "device_serial": self.device_serial,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_steps": self.total_steps,
            "passed": self.passed,
            "failed": self.failed,
            "status": self.status,
        }
