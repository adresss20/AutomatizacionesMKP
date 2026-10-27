import json
import os
import shutil
from pathlib import Path


def save_checkpoint(path, data):
    """Escritura atomica: .tmp → os.replace() para evitar corrupcion."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, str(p))

    # Backup cada 500 productos
    products = data.get("products", [])
    if len(products) % 500 == 0 and len(products) > 0:
        backup_dir = p.parent / "checkpoints_backup"
        backup_dir.mkdir(exist_ok=True)
        backup_path = backup_dir / f"checkpoint_{len(products)}.json"
        shutil.copy2(str(p), str(backup_path))


def load_checkpoint(path):
    """Carga checkpoint; devuelve None si no existe o esta corrupto."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_pids(path, entries):
    """Guarda lista de (pid, url) a disco."""
    p = Path(path)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False)


def load_pids(path):
    """Carga lista de [pid, url] desde disco."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Convertir a lista de tuplas
        return [(int(item[0]), item[1]) for item in data]
    except Exception:
        return None
