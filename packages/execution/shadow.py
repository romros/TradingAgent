"""Broker-neutral shadow ledger. It records hypothetical intents, never orders."""
from __future__ import annotations
import datetime as dt
import csv, json, os, tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class ShadowIntent:
    key: str
    strategy: str
    symbol: str
    action: str
    session: str
    reference_price: float
    quantity: int
    notional: float
    estimated_commission: float
    status: str = "HYPOTHETICAL_NOT_SENT"
    metadata: dict[str, Any] | None = None

def whole_share_size(capital: float, reference_price: float,
                     commission: float = 1.25, reserve_pct: float = .05) -> int:
    if capital <= 0 or reference_price <= 0 or commission < 0 or not 0 <= reserve_pct < 1:
        raise ValueError("invalid sizing input")
    budget=capital*(1-reserve_pct)-commission
    return max(0,int(budget//reference_price))

def load_ledger(path: Path) -> dict:
    if not path.exists():return {"schema_version":1,"mode":"shadow","intents":[]}
    value=json.loads(path.read_text())
    if value.get("mode")!="shadow":raise ValueError("not a shadow ledger")
    return value

def ensure_ledger(path: Path) -> dict:
    """Create an explicit empty JSON/CSV ledger when shadow has no signals yet."""
    ledger = load_ledger(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False,
                                         prefix="." + path.name) as stream:
            temp = Path(stream.name); json.dump(ledger, stream, indent=2); stream.write("\n")
            stream.flush(); os.fsync(stream.fileno())
        temp.replace(path)
    sync_csv(path, ledger)
    return ledger

def hypothetical_position(ledger: dict, symbol: str) -> int:
    quantity=0
    for intent in ledger.get("intents", []):
        if intent.get("symbol") != symbol:continue
        if intent.get("action") == "BUY":quantity += int(intent.get("quantity", 0))
        elif intent.get("action") == "SELL":quantity -= int(intent.get("quantity", 0))
        if quantity < 0:raise ValueError("shadow ledger contains short position")
    return quantity

def hypothetical_open_intent(ledger: dict, symbol: str) -> dict | None:
    opened = None
    for intent in ledger.get("intents", []):
        if intent.get("symbol") != symbol:
            continue
        if intent.get("action") == "BUY":
            opened = intent
        elif intent.get("action") == "SELL":
            opened = None
    return opened

def append_once(path: Path, intent: ShadowIntent) -> bool:
    ledger=load_ledger(path)
    if any(x["key"]==intent.key for x in ledger["intents"]):return False
    if intent.status!="HYPOTHETICAL_NOT_SENT":raise ValueError("unsafe intent status")
    ledger["intents"].append(asdict(intent));ledger["updated_at"]=dt.datetime.now(dt.timezone.utc).isoformat()
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,prefix='.'+path.name) as f:
        temp=Path(f.name);json.dump(ledger,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    temp.replace(path);sync_csv(path, ledger);return True

def append_many_once(path: Path, intents: list[ShadowIntent]) -> int:
    """Atomically append an idempotent group of hypothetical intents."""
    ledger = load_ledger(path)
    existing = {item["key"] for item in ledger["intents"]}
    pending = [intent for intent in intents if intent.key not in existing]
    if not pending:
        return 0
    if len({intent.key for intent in pending}) != len(pending):
        raise ValueError("duplicate key inside shadow intent group")
    if any(intent.status != "HYPOTHETICAL_NOT_SENT" for intent in pending):
        raise ValueError("unsafe intent status")
    ledger["intents"].extend(asdict(intent) for intent in pending)
    ledger["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False,
                                     prefix="." + path.name) as stream:
        temp = Path(stream.name); json.dump(ledger, stream, indent=2); stream.write("\n")
        stream.flush(); os.fsync(stream.fileno())
    temp.replace(path); sync_csv(path, ledger)
    return len(pending)

def sync_csv(path: Path, ledger: dict | None = None) -> Path:
    """Atomically mirror a JSON shadow ledger to a human/DuckDB-friendly CSV."""
    ledger = ledger or load_ledger(path)
    output = path.with_suffix(".csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["key", "strategy", "symbol", "action", "session", "reference_price",
              "quantity", "notional", "estimated_commission", "status", "stop",
              "target", "exit_type", "metadata_json"]
    with tempfile.NamedTemporaryFile("w", newline="", dir=output.parent, delete=False,
                                     prefix="." + output.name) as stream:
        temp = Path(stream.name); writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for item in ledger.get("intents", []):
            metadata = item.get("metadata") or {}
            writer.writerow({**{key: item.get(key, "") for key in fields[:10]},
                             "stop": metadata.get("stop", ""), "target": metadata.get("target", ""),
                             "exit_type": metadata.get("exit_type", ""),
                             "metadata_json": json.dumps(metadata, sort_keys=True, separators=(",", ":"))})
        stream.flush(); os.fsync(stream.fileno())
    temp.replace(output)
    return output
