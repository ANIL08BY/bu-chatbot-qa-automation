"""
Qdrant Local -> Cloud Migration
================================
Tum veriyi qdrant_local'den Qdrant Cloud'a tasir.

CALISTIRMADAN ONCE:
  1. Backend'i durdur (uvicorn kapali olmali)
  2. .env icinde QDRANT_URL ve QDRANT_API_KEY satirlarinin basi acik olmali

Kullanim:
  python migrate_to_cloud.py
"""
from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

load_dotenv()

# ---------------------------------------------------------------------------
# Baglanti parametreleri
# ---------------------------------------------------------------------------
LOCAL_PATH    = os.getenv("QDRANT_PATH", "./qdrant_local")
CLOUD_URL     = os.getenv("QDRANT_URL", "")
CLOUD_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION    = "belek_v2"
BATCH_SIZE    = 100


def hr(char="=", width=60):
    print(char * width)


# ---------------------------------------------------------------------------
# On kontrol
# ---------------------------------------------------------------------------
if not CLOUD_URL or not CLOUD_API_KEY:
    print("HATA: .env dosyasinda QDRANT_URL ve QDRANT_API_KEY tanimli degil.")
    print("  Satirlarin basindaki # karakterini kaldirin ve tekrar deneyin.")
    sys.exit(1)


def connect_local():
    print("  Local Qdrant baglaniliyor: " + LOCAL_PATH)
    try:
        return QdrantClient(path=LOCAL_PATH)
    except RuntimeError as exc:
        if "already accessed" in str(exc):
            print()
            print("HATA: qdrant_local baska bir surec tarafindan kilitli.")
            print("  Backend (uvicorn) calisiyorsa kapatin ve tekrar deneyin.")
            sys.exit(1)
        raise


def connect_cloud():
    print("  Cloud Qdrant baglaniliyor: " + CLOUD_URL[:55] + "...")
    return QdrantClient(url=CLOUD_URL, api_key=CLOUD_API_KEY, timeout=60)


# ---------------------------------------------------------------------------
# Ana migration
# ---------------------------------------------------------------------------
def migrate():
    hr()
    print("  Qdrant Local -> Cloud Migration")
    hr()

    # 1. Baglantilar
    print("\n[1/5] Baglantilar kuruluyor...")
    local = connect_local()
    cloud = connect_cloud()
    print("  [OK] Her iki baglanti kuruldu.")

    # 2. Local koleksiyon kontrolu
    print("\n[2/5] Local koleksiyon kontrol ediliyor: '" + COLLECTION + "'")
    local_cols = {c.name for c in local.get_collections().collections}
    if COLLECTION not in local_cols:
        print("HATA: '" + COLLECTION + "' koleksiyonu local'de bulunamadi.")
        print("  Mevcut koleksiyonlar: " + str(local_cols or "(bos)"))
        sys.exit(1)

    local_info   = local.get_collection(COLLECTION)
    total_points = local_info.points_count or 0
    print("  [OK] Nokta sayisi : " + str(total_points))

    if total_points == 0:
        print("  Local koleksiyon bos, tasinacak veri yok.")
        sys.exit(0)

    # 3. Cloud koleksiyonunu sifirla
    print("\n[3/5] Cloud koleksiyonu sifirlanıyor: '" + COLLECTION + "'")
    cloud_cols = {c.name for c in cloud.get_collections().collections}
    if COLLECTION in cloud_cols:
        cloud.delete_collection(COLLECTION)
        print("  [OK] Eski cloud koleksiyonu silindi.")
    else:
        print("  [OK] Cloud'da mevcut koleksiyon yok (temiz baslangic).")

    from backend.pipeline_v2.schemas.qdrant_schema import create_collection_if_not_exists
    create_collection_if_not_exists(cloud, COLLECTION)
    print("  [OK] Cloud koleksiyonu olusturuldu (schema + payload indexler).")

    # 4. Veri transferi
    print("\n[4/5] Veri tasinıyor... (" + str(total_points) + " nokta, batch=" + str(BATCH_SIZE) + ")")
    offset      = None
    transferred = 0
    errors      = 0
    start_time  = time.time()

    while True:
        records, next_offset = local.scroll(
            collection_name=COLLECTION,
            offset=offset,
            limit=BATCH_SIZE,
            with_vectors=True,
            with_payload=True,
        )

        if not records:
            break

        points = [
            PointStruct(id=rec.id, vector=rec.vector, payload=rec.payload)
            for rec in records
        ]

        try:
            cloud.upsert(collection_name=COLLECTION, points=points)
            transferred += len(points)
        except Exception as exc:
            errors += len(points)
            print("\n  UYARI: Batch upsert hatasi (" + str(len(points)) + " nokta atlandi): " + str(exc))

        # Ilerleme
        elapsed = time.time() - start_time
        pct     = transferred / total_points * 100 if total_points else 0
        rate    = transferred / elapsed if elapsed > 0 else 0
        width   = len(str(total_points))
        line    = ("  %*d/%d  (%5.1f%%)  %5.0f nokta/s" %
                   (width, transferred, total_points, pct, rate))
        print(line, end="\r")

        if next_offset is None:
            break
        offset = next_offset

    elapsed_total = time.time() - start_time
    print()

    # 5. Dogrulama
    print("\n[5/5] Dogrulama yapiliyor...")
    cloud_points = (cloud.get_collection(COLLECTION).points_count or 0)

    hr("-")
    print("  Local nokta sayisi : " + str(total_points))
    print("  Cloud nokta sayisi : " + str(cloud_points))
    print("  Transfer edilen    : " + str(transferred))
    if errors:
        print("  Hatali             : " + str(errors) + "  (!)")
    print("  Sure               : %.1fs" % elapsed_total)
    hr("-")

    if cloud_points == total_points:
        print("  [BASARILI] Tum noktalar cloud'a tasindi.")
    else:
        diff = total_points - cloud_points
        print("  [UYARI] " + str(diff) + " nokta eksik. Tekrar calistirmayi deneyin.")

    print()
    print("  SONRAKI ADIM: .env dosyasinda")
    print("    QDRANT_PATH satirini # ile yorum satiri yapin")
    print("    QDRANT_URL ve QDRANT_API_KEY satirlari acik kalmali")
    print("  Ardindan backend'i yeniden baslatin.")
    hr()


if __name__ == "__main__":
    migrate()
