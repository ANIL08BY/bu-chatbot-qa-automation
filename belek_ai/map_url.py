"""
map_url.py — Firecrawl Map + Akıllı Filtre + ingestion_list.json güncelleme.

Derinlik 1: sadece verilen URL'deki linkleri keşfeder, alt sayfalara inmez.

Kullanım:
    python map_url.py https://belek.edu.tr/programlar
    python map_url.py https://belek.edu.tr/programlar --exclude haber,duyuru,etkinlik
    python map_url.py https://belek.edu.tr/programlar --include lisans,yukseklisans
    python map_url.py --from-ingestion
    python map_url.py https://belek.edu.tr/programlar --dry-run

Seçenekler:
    URL                          Keşfedilecek URL (derinlik=1)
    --exclude PAT1,PAT2,...      URL'de bu kelimeler geçenleri hariç tut (regex)
    --include PAT1,PAT2,...      Sadece bu kelimeler geçen URL'leri göster (regex)
    --limit N                    Maksimum link sayısı (varsayılan: 200)
    --include-subdomains         Alt alan adlarını dahil et
    --ignore-sitemap             sitemap.xml'i yoksay
    --category KATEGORİ          Seçilen linklere atanacak kategori
    --priority N                 Öncelik (varsayılan: 1)
    --output PATH                ingestion_list.json yolu
    --from-ingestion             Mevcut ingestion_list.json'daki HTML URL'lerden seç
    --dry-run                    Yazmadan göster
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.WARNING,       # Sadece hataları göster; bilgi mesajları _print ile
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger("map_url")

# ─────────────────────────────────────────────────────────────────────────────
# Renk sabitleri (Windows CMD de çalışır)
# ─────────────────────────────────────────────────────────────────────────────
try:
    import colorama
    colorama.init()
    _GREEN  = "\033[32m"
    _YELLOW = "\033[33m"
    _CYAN   = "\033[36m"
    _GRAY   = "\033[90m"
    _BOLD   = "\033[1m"
    _RESET  = "\033[0m"
except ImportError:
    _GREEN = _YELLOW = _CYAN = _GRAY = _BOLD = _RESET = ""


def _c(color: str, text: str) -> str:
    return f"{color}{text}{_RESET}"


# ─────────────────────────────────────────────────────────────────────────────
# Filtre motoru
# ─────────────────────────────────────────────────────────────────────────────

def _compile_patterns(raw: str) -> list[re.Pattern]:
    """Virgülle ayrılmış pattern string → derlenmiş regex listesi."""
    patterns = []
    for p in raw.split(","):
        p = p.strip()
        if p:
            try:
                patterns.append(re.compile(p, re.IGNORECASE))
            except re.error:
                # Geçersiz regex ise literal string olarak dene
                patterns.append(re.compile(re.escape(p), re.IGNORECASE))
    return patterns


def apply_filters(
    links: list[str],
    exclude_patterns: list[re.Pattern],
    include_patterns: list[re.Pattern],
) -> tuple[list[str], int]:
    """
    Linklere exclude/include filtresi uygula.

    Returns:
        (filtreli_liste, filtrelenen_sayı)
    """
    original_count = len(links)
    result = links[:]

    if exclude_patterns:
        result = [
            u for u in result
            if not any(p.search(u) for p in exclude_patterns)
        ]

    if include_patterns:
        result = [
            u for u in result
            if any(p.search(u) for p in include_patterns)
        ]

    return result, original_count - len(result)


# ─────────────────────────────────────────────────────────────────────────────
# ingestion_list.json I/O
# ─────────────────────────────────────────────────────────────────────────────

def _load_ingestion_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("ingestion_list.json okunamadı: %s", exc)
        return []


def _save_ingestion_list(path: Path, items: list[dict]) -> None:
    path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _existing_urls(items: list[dict]) -> set[str]:
    return {item["url"] for item in items if item.get("url")}


# ─────────────────────────────────────────────────────────────────────────────
# Görüntüleme
# ─────────────────────────────────────────────────────────────────────────────

def _print_links(links: list[str], existing: set[str]) -> None:
    if not links:
        print("  (link yok)\n")
        return

    num_w = len(str(len(links)))
    new_count    = sum(1 for u in links if u not in existing)
    exist_count  = len(links) - new_count

    print()
    print(f"  {_c(_BOLD, f'{len(links)} link')}  "
          f"({_c(_GREEN, f'{new_count} yeni')}, "
          f"{_c(_GRAY, f'{exist_count} mevcut')})")
    print()
    print(f"  {'#':<{num_w+2}}  {'':8}  URL")
    print(f"  {'-'*(num_w+2)}  {'-'*8}  {'-'*60}")

    for i, url in enumerate(links, 1):
        if url in existing:
            tag  = _c(_GRAY,  "✓ mevcut")
            ustr = _c(_GRAY,  url)
        else:
            tag  = _c(_GREEN, "· yeni  ")
            ustr = url
        print(f"  {i:<{num_w+2}}  {tag}  {ustr}")
    print()


def _print_separator(title: str = "") -> None:
    line = "─" * 70
    if title:
        pad = max(0, (70 - len(title) - 2) // 2)
        print(f"\n  {'─'*pad} {_c(_BOLD, title)} {'─'*pad}\n")
    else:
        print(f"\n  {line}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Seçim ayrıştırıcı
# ─────────────────────────────────────────────────────────────────────────────

def _parse_selection(raw: str, max_idx: int) -> list[int]:
    """
    "1,3,5-8"  → [0,2,4,5,6,7]
    "all"       → [0..max_idx-1]
    ""          → []
    """
    raw = raw.strip().lower()
    if raw in ("all", "hepsi", "tümü", "hepsini", "tümünü"):
        return list(range(max_idx))
    if not raw:
        return []

    indices: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                s, e = part.split("-", 1)
                indices.extend(range(int(s) - 1, int(e)))
            except ValueError:
                print(f"  ⚠  Geçersiz aralık atlandı: {part}")
        else:
            try:
                indices.append(int(part) - 1)
            except ValueError:
                print(f"  ⚠  Geçersiz numara atlandı: {part}")

    return sorted(set(i for i in indices if 0 <= i < max_idx))


# ─────────────────────────────────────────────────────────────────────────────
# İnteraktif filtre döngüsü
# ─────────────────────────────────────────────────────────────────────────────

def interactive_filter(
    links: list[str],
    existing: set[str],
    init_exclude: list[re.Pattern],
    init_include: list[re.Pattern],
) -> list[str]:
    """
    Kullanıcıya filtre uygulama imkânı verir.
    Sonuçta seçime hazır link listesi döner.
    """
    current = links[:]

    # Başlangıç CLI filtreleri
    if init_exclude or init_include:
        current, filtered_n = apply_filters(current, init_exclude, init_include)
        print(f"  CLI filtresi uygulandı: {filtered_n} link hariç tutuldu, "
              f"{len(current)} link kaldı.")

    _print_links(current, existing)

    # İnteraktif filtre döngüsü
    while True:
        _print_separator("FİLTRE")
        print("  Hariç tut  → haber,duyuru,etkinlik   (URL içinde arar, regex geçerli)")
        print("  Sadece göster → +lisans,yukseklisans  (başına + koy)")
        print("  Filtreyi sıfırla → sifirla")
        print("  Devam et  → Enter\n")

        raw = input("  Filtre: ").strip()

        if not raw:
            break  # filtre yok, devam

        if raw.lower() in ("sifirla", "reset", "sıfırla"):
            current = links[:]
            print(f"  ↩  Sıfırlandı, {len(current)} link.")
            _print_links(current, existing)
            continue

        # + ile başlıyorsa include, değilse exclude
        if raw.startswith("+"):
            inc_pats = _compile_patterns(raw[1:])
            new_list, _ = apply_filters(current, [], inc_pats)
        else:
            exc_pats = _compile_patterns(raw)
            new_list, filtered_n = apply_filters(current, exc_pats, [])
            print(f"  ✂  {filtered_n} link filtrelendi.")

        if not new_list:
            print("  ⚠  Filtre sonrası hiç link kalmadı! Filtre uygulanmadı.")
            continue

        current = new_list
        _print_links(current, existing)

    return current


# ─────────────────────────────────────────────────────────────────────────────
# Ana akış
# ─────────────────────────────────────────────────────────────────────────────

def _guess_category(url: str) -> str:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if parts:
        return parts[-1].replace("-", " ").replace("_", " ")
    return parsed.netloc.split(".")[0]


def run_map(url: str, args: argparse.Namespace, ingestion_path: Path) -> None:
    from backend.pipeline_v2.resources.firecrawl_resource import FirecrawlResource

    fc = FirecrawlResource(api_key=os.environ.get("FIRECRAWL_API_KEY", ""))

    _print_separator("KEŞİF")
    print(f"  URL   : {_c(_CYAN, url)}")
    print(f"  Limit : {args.limit}  |  Derinlik: 1  |  Subdomains: {args.include_subdomains}")
    if args.exclude:
        print(f"  Hariç : {_c(_YELLOW, args.exclude)}")
    if args.include:
        print(f"  Sadece: {_c(_YELLOW, args.include)}")
    print()
    print("  Firecrawl map çalışıyor...")

    links = fc.map(
        url,
        limit=args.limit,
        include_subdomains=args.include_subdomains,
        ignore_sitemap=args.ignore_sitemap,
    )

    if not links:
        print("  ✗  Hiç link bulunamadı veya API hatası.\n")
        return

    print(f"  {len(links)} link keşfedildi.")

    # Mevcut ingestion_list
    current_items = _load_ingestion_list(ingestion_path)
    existing = _existing_urls(current_items)

    # CLI filtrelerini derle
    init_exclude = _compile_patterns(args.exclude) if args.exclude else []
    init_include = _compile_patterns(args.include) if args.include else []

    # ── İnteraktif filtre ──────────────────────────────────────────────────
    _print_separator("LİNKLER")
    active_links = interactive_filter(links, existing, init_exclude, init_include)

    # Yeni olanları filtrele (mevcut olanları listeye eklemek istemeyiz)
    new_links = [u for u in active_links if u not in existing]
    already_n = len(active_links) - len(new_links)

    if already_n:
        print(f"  ℹ  {already_n} link zaten ingestion_list.json'da — bunlar atlanacak.")

    if not new_links:
        print("  ✓  Eklenecek yeni link yok.\n")
        return

    # ── Seçim ─────────────────────────────────────────────────────────────
    _print_separator("SEÇİM")
    print(f"  {len(new_links)} yeni link mevcut.\n")
    print(f"  {_c(_BOLD, 'all')}        → tüm yeni linkleri ekle")
    print(f"  {_c(_BOLD, '1,3,5-8')}   → numara/aralık ile seç")
    print(f"  {_c(_BOLD, 'Enter')}      → atla / çık\n")

    raw_sel = input("  Seçim: ").strip()

    if not raw_sel:
        print("  Atlandı.\n")
        return

    selected_indices = _parse_selection(raw_sel, len(new_links))
    selected_urls = [new_links[i] for i in selected_indices]

    if not selected_urls:
        print("  Geçerli seçim yapılmadı.\n")
        return

    print(f"\n  {_c(_GREEN, f'{len(selected_urls)} URL seçildi:')}")
    for u in selected_urls:
        print(f"    {_c(_GREEN, '+')} {u}")

    # ── Kategori & Öncelik ─────────────────────────────────────────────────
    _print_separator("METADATA")
    default_cat = args.category or _guess_category(url)
    default_pri = args.priority

    cat_in = input(f"  Kategori [{default_cat}]: ").strip()
    category = cat_in if cat_in else default_cat

    pri_in = input(f"  Öncelik  [{default_pri}]: ").strip()
    try:
        priority = int(pri_in) if pri_in else default_pri
    except ValueError:
        priority = default_pri

    # ── Dry-run ────────────────────────────────────────────────────────────
    if args.dry_run:
        print(f"\n  {_c(_YELLOW, '--dry-run:')} ingestion_list.json'a YAZILMADı.")
        print(f"  Yazılacaktı: {len(selected_urls)} giriş  "
              f"kategori='{category}'  öncelik={priority}\n")
        return

    # ── Yazma ──────────────────────────────────────────────────────────────
    existing_now = _existing_urls(current_items)  # güncel set
    added = 0
    for u in selected_urls:
        if u in existing_now:
            print(f"  ⚠  Zaten mevcut, atlandı: {u}")
            continue
        current_items.append({
            "url": u,
            "category": category,
            "priority": priority,
            "crawl_linked_docs": False,
        })
        existing_now.add(u)
        added += 1

    _save_ingestion_list(ingestion_path, current_items)

    _print_separator()
    print(f"  {_c(_GREEN, f'✅  {added} URL ingestion_list.json a eklendi')}")
    print(f"     kategori='{category}'  öncelik={priority}")
    print(f"     Dosya: {ingestion_path}\n")


# ─────────────────────────────────────────────────────────────────────────────
# --from-ingestion modu
# ─────────────────────────────────────────────────────────────────────────────

def run_from_ingestion(args: argparse.Namespace, ingestion_path: Path) -> None:
    from backend.pipeline_v2.config_v2 import load_ingestion_list_v2

    sources = load_ingestion_list_v2(str(ingestion_path))
    html_sources = [s for s in sources if s.is_html]

    if not html_sources:
        print("  ingestion_list.json'da HTML kaynak bulunamadı.")
        sys.exit(1)

    _print_separator("MEVCUT HTML KAYNAKLAR")
    num_w = len(str(len(html_sources)))
    for i, s in enumerate(html_sources, 1):
        print(f"  [{i:>{num_w}}]  {s.url}  {_c(_GRAY, f'({s.category})')}")

    print()
    raw = input("  Hangi URL için map çalıştırılsın? (numara): ").strip()
    try:
        idx = int(raw) - 1
        assert 0 <= idx < len(html_sources)
    except (ValueError, AssertionError):
        print("  Geçersiz seçim.")
        sys.exit(1)

    chosen = html_sources[idx]
    if not args.category:
        args.category = chosen.category

    run_map(chosen.url, args, ingestion_path)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Firecrawl Map → Filtre → ingestion_list.json  (derinlik=1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("url", nargs="?", default="",
                   help="Keşfedilecek URL")
    p.add_argument("--exclude", default="",
                   help="Hariç tutulacak pattern'lar, virgülle (örn: haber,duyuru)")
    p.add_argument("--include", default="",
                   help="Sadece gösterilecek pattern'lar, virgülle (örn: lisans,burs)")
    p.add_argument("--limit", type=int, default=200,
                   help="Maksimum link sayısı (varsayılan: 200)")
    p.add_argument("--include-subdomains", action="store_true",
                   help="Alt alan adlarını dahil et")
    p.add_argument("--ignore-sitemap", action="store_true",
                   help="sitemap.xml'i yoksay")
    p.add_argument("--category", default="",
                   help="Seçilen linklere atanacak kategori")
    p.add_argument("--priority", type=int, default=1,
                   help="Öncelik (varsayılan: 1)")
    p.add_argument("--output", default="ingestion_list.json",
                   help="ingestion_list.json yolu")
    p.add_argument("--env", default=".env",
                   help=".env dosyası")
    p.add_argument("--from-ingestion", action="store_true",
                   help="Mevcut ingestion_list.json'daki HTML URL'lerden seç")
    p.add_argument("--dry-run", action="store_true",
                   help="Yazmadan göster")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv(args.env, override=False)
    except ImportError:
        pass

    ingestion_path = Path(args.output)

    if args.from_ingestion:
        run_from_ingestion(args, ingestion_path)
        return

    if not args.url:
        print("Hata: URL veya --from-ingestion gerekli.\n")
        print("Örnekler:")
        print("  python map_url.py https://belek.edu.tr/programlar")
        print("  python map_url.py https://belek.edu.tr/programlar --exclude haber,duyuru")
        print("  python map_url.py --from-ingestion")
        sys.exit(1)

    run_map(args.url, args, ingestion_path)


if __name__ == "__main__":
    main()
