"""
SHA-256 Hash Kaydı — Incremental Ingestion.

doc_hashes.json şeması:
{
  "https://example.com/page": {
    "hash": "abc123...",
    "last_seen": "2026-03-16T10:00:00+00:00"
  }
}

Kullanım:
    registry = load_registry(path)
    changed = filter_changed(docs, registry)
    save_registry(registry, path)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def load_registry(path: str) -> dict[str, dict[str, str]]:
    """Hash kaydını JSON dosyasından yükle. Dosya yoksa boş dict döner."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_registry(registry: dict[str, dict[str, str]], path: str) -> None:
    """Kaydı atomik olarak yaz (.tmp → rename)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as exc:
        # tmp dosyasını temizle; hata fırlat
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise RuntimeError(f"Hash kaydı yazılamadı: {exc}") from exc


def filter_changed(
    docs: list[dict[str, Any]],
    registry: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    """
    Her belge için hash karşılaştırması yapar.

    - Yeni veya değişmiş belgeler: is_changed = True
    - Değişmemiş belgeler: is_changed = False

    Registry güncellenmiş haliyle döner (kaydetmek çağrıcının sorumluluğu).

    Returns:
        (annotated_docs, updated_registry)
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    annotated: list[dict[str, Any]] = []

    for doc in docs:
        url = doc.get("url", "")
        new_hash = doc.get("content_hash", "")
        old_entry = registry.get(url, {})
        old_hash = old_entry.get("hash", "")

        is_new = url not in registry          # hash kaydında hiç yok
        is_changed = old_hash != new_hash     # yeni veya içerik değişmiş
        doc = {**doc, "is_changed": is_changed, "is_new": is_new}

        # Kaydı güncelle (değişsin ya da değişmesin, last_seen güncellenir)
        registry[url] = {"hash": new_hash, "last_seen": now_iso}
        annotated.append(doc)

    return annotated, registry


def compute_stats(
    docs: list[dict[str, Any]],
) -> dict[str, int]:
    """Değişen/değişmeyen belge istatistiklerini döndür."""
    changed = sum(1 for d in docs if d.get("is_changed", True))
    return {
        "total": len(docs),
        "changed": changed,
        "unchanged": len(docs) - changed,
    }
