"""
BU Chatbot — Modern Data Preparation Pipeline v1.0

Kullanım:
    python -m backend.pipeline.run                # Tam pipeline
    python -m backend.pipeline.run --resume       # Checkpoint'ten devam
    python -m backend.pipeline.run --fresh        # Sıfırdan başla
    python -m backend.pipeline.run --ingest-only  # Crawl atla, cache'den ingest
    python -m backend.pipeline.run --local-only   # Sadece backend/data/ klasörü
"""
