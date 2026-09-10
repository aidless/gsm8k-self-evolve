import json
from datetime import datetime, timezone
from pathlib import Path

class VersionRegistry:
    def __init__(self, path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def transition(self, vid, level, evidence, reason=""):
        cur = self.data["versions"][vid]["level"]
        evt = {"vid": vid, "from": cur, "to": level, "reason": reason,
               "at": datetime.now(timezone.utc).isoformat(), "evidence": evidence}
        self.data["versions"][vid]["level"] = level
        self.data["versions"][vid].setdefault("evidence", {}).update(evidence)
        self.data.setdefault("events", []).append(evt)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        return evt
