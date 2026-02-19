"""
IRDAI Compliance GPT - Crawler Layer
Crawls IRDAI website, downloads PDFs with deduplication via SQLite
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
PDF_DIR = _DATA_ROOT / "pdfs"
DB_PATH = _DATA_ROOT / "irdai_tracker.db"

# Ensure writable dirs exist at import time
_DATA_ROOT.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

DOCUMENT_CATEGORIES = {
    "regulations":   "/web/guest/regulations",
    "circulars":     "/web/guest/circulars",
    "notifications": "/web/guest/notifications",
    "guidelines":    "/web/guest/guidelines",
}

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
def extract_pdf_links(html: str, base_url: str) -> list[str]:
    """Extract PDF links from an IRDAI page.
    Handles both direct .pdf links and /documents/.../*.pdf/UUID patterns.
    """
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith("javascript"):
            continue
        # Match /documents/ URLs that contain .pdf in the path
        if "/documents/" in href and ".pdf" in href.lower():
            full = urljoin(base_url, href)
            links.append(full)
        # Match plain .pdf links
        elif href.lower().endswith(".pdf"):
            full = urljoin(base_url, href)
            links.append(full)
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


def _extract_pdf_filename(url: str) -> str:
    """Extract a clean .pdf filename from IRDAI URL patterns.
    Handles: /documents/37343/365525/filename.pdf/UUID?t=...
    Sanitizes non-ASCII characters for cross-platform compatibility.
    """
    import re
    from urllib.parse import unquote
    parsed = urlparse(url)
    path_parts = parsed.path.split("/")
    for part in path_parts:
        if part.lower().endswith(".pdf"):
            name = unquote(part).replace('+', ' ').strip()
            # Replace non-ASCII chars with underscore for safe filenames
            name = re.sub(r'[^\x20-\x7E]', '_', name)
            # Collapse multiple underscores
            name = re.sub(r'_+', '_', name).strip('_')
            if not name or name == '.pdf':
                break  # fall through to hash-based name
            return name
    return f"doc_{hashlib.md5(url.encode()).hexdigest()[:8]}.pdf"


def download_pdf(url: str, category: str) -> bool:
    """Download a single PDF; returns True if new file saved."""
    if is_already_downloaded(url):
        logger.debug("Already downloaded: %s", url)
        return False

    resp = fetch_with_retry(url, stream=True)
    if not resp:
        return False

    # Check content type
    content_type = resp.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
        logger.warning("Skipping non-PDF content (%s): %s", content_type, url[:100])
        return False

    # Determine filename
    filename = _extract_pdf_filename(url)
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'
    dest = PDF_DIR / category / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Stream write + hash
    sha256 = hashlib.sha256()
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            fh.write(chunk)
            sha256.update(chunk)

    record_download(url, filename, category, sha256.hexdigest())
    logger.info("Downloaded [%s] %s", category, filename)
    return True


def crawl_category(category: str, path: str, max_pages: int = 5) -> int:
    """Crawl a single IRDAI category with pagination. Returns count of new PDFs."""
    url = BASE_URL + path
    count = 0

    for page_num in range(1, max_pages + 1):
        logger.info("Crawling %s – page %d: %s", category, page_num, url)
        resp = fetch_with_retry(url)
        if not resp:
            break

        # 1. Direct PDF links on the page
        pdf_links = extract_pdf_links(resp.text, url)
        logger.info("Found %d direct PDF links on page %d", len(pdf_links), page_num)

        for pdf_url in pdf_links:
            if download_pdf(pdf_url, category):
                count += 1
            time.sleep(0.5)

        # 2. Follow document-detail pages to find PDFs inside
        detail_links = extract_document_detail_links(resp.text, url)
        logger.info("Found %d document-detail links on page %d", len(detail_links), page_num)

        for detail_url in detail_links:
            try:
                detail_resp = fetch_with_retry(detail_url)
                if detail_resp:
                    inner_pdfs = extract_pdf_links(detail_resp.text, detail_url)
                    for pdf_url in inner_pdfs:
                        if download_pdf(pdf_url, category):
                            count += 1
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

    return count


def run_crawl(categories: list[str] | None = None) -> dict:
    """Run crawler for all (or selected) categories. Returns summary dict."""
    init_db()
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    cats = categories or list(DOCUMENT_CATEGORIES.keys())
    summary = {}
    for cat in cats:
        path = DOCUMENT_CATEGORIES.get(cat)
        if not path:
            logger.warning("Unknown category: %s", cat)
            continue
        new_count = crawl_category(cat, path)
        summary[cat] = new_count
        logger.info("Category '%s' – %d new PDFs downloaded", cat, new_count)

    logger.info("Crawl complete. Summary: %s", summary)
    return summary


if __name__ == "__main__":
    result = run_crawl()
    print("Crawl summary:", result)
