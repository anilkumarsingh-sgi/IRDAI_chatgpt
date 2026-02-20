"""
IRDAI Compliance GPT - Crawler Layer
Crawls IRDAI website, downloads PDFs, Excel and Word docs with deduplication via SQLite
"""

import os
import time
import sqlite3
import hashlib
import logging
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("irdai.crawler")

# ─── Config ────────────────────────────────────────────────────────────────────
_ON_CLOUD = Path("/mount/src").exists()
_DATA_ROOT = Path("/tmp/irdai_data") if _ON_CLOUD else Path("data")

BASE_URL = "https://irdai.gov.in"
PDF_DIR   = _DATA_ROOT / "pdfs"
EXCEL_DIR = _DATA_ROOT / "excel"
WORD_DIR  = _DATA_ROOT / "word"
DB_PATH   = _DATA_ROOT / "irdai_tracker.db"

# Ensure writable dirs exist at import time
for _d in [_DATA_ROOT, PDF_DIR, EXCEL_DIR, WORD_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# Supported file extensions mapped to their target directory
DOC_TYPES = {
    ".pdf":  PDF_DIR,
    ".xlsx": EXCEL_DIR,
    ".xls":  EXCEL_DIR,
    ".csv":  EXCEL_DIR,
    ".docx": WORD_DIR,
    ".doc":  WORD_DIR,
}

DOCUMENT_CATEGORIES = {
    "regulations":   "/web/guest/regulations",
    "circulars":     "/web/guest/circulars",
    "notifications": "/web/guest/notifications",
    "guidelines":    "/web/guest/guidelines",
}

# Additional pages to scrape for documents
EXTRA_PAGES = [
    "/home",
    "/web/guest/acts",
    "/web/guest/annual-reports",
    "/web/guest/forms",
    "/web/guest/reports-and-manuals",
    "/web/guest/orders",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


# ─── Database Setup ────────────────────────────────────────────────────────────
def init_db():
    """Initialize SQLite database for download tracking."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT UNIQUE NOT NULL,
            filename    TEXT NOT NULL,
            category    TEXT,
            file_hash   TEXT,
            downloaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            status      TEXT DEFAULT 'success'
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized at %s", DB_PATH)


def is_already_downloaded(url: str) -> bool:
    """Check if a URL has already been downloaded."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id FROM downloads WHERE url = ?", (url,)
    ).fetchone()
    conn.close()
    return row is not None


def record_download(url: str, filename: str, category: str, file_hash: str):
    """Record a successful download in SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO downloads (url, filename, category, file_hash) "
        "VALUES (?, ?, ?, ?)",
        (url, filename, category, file_hash),
    )
    conn.commit()
    conn.close()


def get_download_stats() -> dict:
    """Return download stats per category."""
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT category, COUNT(*) FROM downloads GROUP BY category"
        ).fetchall()
        return {r[0]: r[1] for r in rows}
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()


# ─── HTTP Helpers ──────────────────────────────────────────────────────────────
def fetch_with_retry(url: str, stream: bool = False) -> requests.Response | None:
    """GET request with exponential backoff retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url, headers=HEADERS, stream=stream,
                timeout=30, allow_redirects=True
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            wait = BACKOFF_BASE ** attempt
            logger.warning(
                "Attempt %d/%d failed for %s: %s. Retrying in %ds…",
                attempt, MAX_RETRIES, url, exc, wait
            )
            if attempt < MAX_RETRIES:
                time.sleep(wait)
    logger.error("All retries exhausted for %s", url)
    return None


# ─── PDF Crawler ───────────────────────────────────────────────────────────────
def extract_doc_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Extract all document links (PDF, Excel, Word) from a page.
    Returns list of (full_url, extension) tuples.
    """
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith("javascript"):
            continue
        hl = href.lower()
        for ext in DOC_TYPES:
            if ext in hl:
                full = urljoin(base_url, href)
                links.append((full, ext))
                break
    return list(set(links))


def extract_document_detail_links(html: str, base_url: str) -> list[str]:
    """Extract document-detail page links that may contain PDFs."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if "document-detail" in href and "documentId" in href:
            full = urljoin(base_url, href)
            links.append(full)
    return list(set(links))


def get_next_page_url(html: str, current_url: str) -> str | None:
    """Find pagination 'Next' link if present."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith("javascript"):
            continue
        text = tag.get_text(strip=True).lower()
        if text in ("next", "next page", "›", "»"):
            return urljoin(current_url, href)
    return None


def _extract_doc_filename(url: str, ext: str) -> str:
    """Extract a clean filename from IRDAI URL patterns.
    Sanitizes non-ASCII characters for cross-platform compatibility.
    """
    import re
    from urllib.parse import unquote
    parsed = urlparse(url)
    path_parts = parsed.path.split("/")
    for part in path_parts:
        if ext in part.lower():
            name = unquote(part).replace('+', ' ').strip()
            name = re.sub(r'[^\x20-\x7E]', '_', name)
            name = re.sub(r'_+', '_', name).strip('_')
            if name and name != ext:
                return name
    return f"doc_{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}"


def download_document(url: str, ext: str, category: str) -> bool:
    """Download a single document (PDF/Excel/Word); returns True if new file saved."""
    if is_already_downloaded(url):
        logger.debug("Already downloaded: %s", url)
        return False

    resp = fetch_with_retry(url, stream=True)
    if not resp:
        return False

    # Determine target directory and filename
    target_dir = DOC_TYPES.get(ext, PDF_DIR)
    filename = _extract_doc_filename(url, ext)
    if not filename.lower().endswith(ext):
        filename += ext
    dest = target_dir / category / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Stream write + hash
    sha256 = hashlib.sha256()
    try:
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)
                sha256.update(chunk)
    except OSError as exc:
        logger.error("Failed to write %s: %s", dest, exc)
        return False

    file_type = "pdf" if ext == ".pdf" else ("excel" if ext in (".xlsx", ".xls", ".csv") else "word")
    record_download(url, filename, f"{category}_{file_type}", sha256.hexdigest())
    logger.info("Downloaded [%s/%s] %s", category, file_type, filename)
    return True


def crawl_category(category: str, path: str, max_pages: int = 5) -> dict:
    """Crawl a single IRDAI category. Returns counts by doc type."""
    url = BASE_URL + path
    counts = {"pdf": 0, "excel": 0, "word": 0}

    for page_num in range(1, max_pages + 1):
        logger.info("Crawling %s – page %d: %s", category, page_num, url)
        resp = fetch_with_retry(url)
        if not resp:
            break

        # 1. Direct document links on the page
        doc_links = extract_doc_links(resp.text, url)
        logger.info("Found %d document links on page %d", len(doc_links), page_num)

        for doc_url, ext in doc_links:
            if download_document(doc_url, ext, category):
                dtype = "pdf" if ext == ".pdf" else ("excel" if ext in (".xlsx",".xls",".csv") else "word")
                counts[dtype] += 1
            time.sleep(0.5)

        # 2. Follow document-detail pages
        detail_links = extract_document_detail_links(resp.text, url)
        logger.info("Found %d document-detail links on page %d", len(detail_links), page_num)

        for detail_url in detail_links:
            try:
                detail_resp = fetch_with_retry(detail_url)
                if detail_resp:
                    inner_docs = extract_doc_links(detail_resp.text, detail_url)
                    for doc_url, ext in inner_docs:
                        if download_document(doc_url, ext, category):
                            dtype = "pdf" if ext == ".pdf" else ("excel" if ext in (".xlsx",".xls",".csv") else "word")
                            counts[dtype] += 1
                        time.sleep(0.5)
            except Exception as exc:
                logger.warning("Error following detail page %s: %s", detail_url[:80], exc)
            time.sleep(0.5)

        next_url = get_next_page_url(resp.text, url)
        if not next_url or next_url == url:
            logger.info("No more pages for %s", category)
            break
        url = next_url
        time.sleep(1)

    return counts


def crawl_extra_pages() -> dict:
    """Crawl additional IRDAI pages (home, forms, reports, etc.)."""
    counts = {"pdf": 0, "excel": 0, "word": 0}
    for path in EXTRA_PAGES:
        url = BASE_URL + path
        category = path.split("/")[-1] or "home"
        logger.info("Crawling extra page: %s", url)
        resp = fetch_with_retry(url)
        if not resp:
            continue

        doc_links = extract_doc_links(resp.text, url)
        logger.info("Found %d document links on %s", len(doc_links), category)

        for doc_url, ext in doc_links:
            if download_document(doc_url, ext, category):
                dtype = "pdf" if ext == ".pdf" else ("excel" if ext in (".xlsx",".xls",".csv") else "word")
                counts[dtype] += 1
            time.sleep(0.5)

        # Follow detail pages
        detail_links = extract_document_detail_links(resp.text, url)
        for detail_url in detail_links:
            try:
                detail_resp = fetch_with_retry(detail_url)
                if detail_resp:
                    inner_docs = extract_doc_links(detail_resp.text, detail_url)
                    for doc_url, ext in inner_docs:
                        if download_document(doc_url, ext, category):
                            dtype = "pdf" if ext == ".pdf" else ("excel" if ext in (".xlsx",".xls",".csv") else "word")
                            counts[dtype] += 1
                        time.sleep(0.5)
            except Exception as exc:
                logger.warning("Error: %s", exc)
            time.sleep(0.5)
    return counts


def run_crawl(categories: list[str] | None = None) -> dict:
    """Run crawler for all (or selected) categories + extra pages. Returns summary."""
    init_db()
    for _d in [PDF_DIR, EXCEL_DIR, WORD_DIR]:
        _d.mkdir(parents=True, exist_ok=True)

    cats = categories or list(DOCUMENT_CATEGORIES.keys())
    summary = {"pdf": 0, "excel": 0, "word": 0}

    for cat in cats:
        path = DOCUMENT_CATEGORIES.get(cat)
        if not path:
            logger.warning("Unknown category: %s", cat)
            continue
        counts = crawl_category(cat, path)
        for k in summary:
            summary[k] += counts.get(k, 0)
        logger.info("Category '%s' – %s", cat, counts)

    # Crawl extra pages
    extra_counts = crawl_extra_pages()
    for k in summary:
        summary[k] += extra_counts.get(k, 0)
    logger.info("Extra pages – %s", extra_counts)

    logger.info("Crawl complete. Summary: %s", summary)
    return summary


if __name__ == "__main__":
    result = run_crawl()
    print("Crawl summary:", result)
