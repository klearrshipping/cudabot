#!/usr/bin/env python3
"""
Extract every PDF link from the WCO HS-2022 table-of-contents page
and optionally download the files.

Requirements:
  pip install beautifulsoup4 requests tqdm
"""

import os, sys, requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from tqdm import tqdm       # Progress bar for downloads

PAGE_URL  = (
    "https://www.wcoomd.org/en/topics/nomenclature/"
    "instrument-and-tools/hs-nomenclature-2022-edition/hs-nomenclature-2022-edition.aspx"
)
DOWNLOAD  = True            # set False if you only want the list
OUT_FILE  = "pdf_links.txt"
OUT_DIR   = "pdfs"

def fetch_html(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text

def parse_pdfs(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    pdfs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf") or ".pdf?" in href.lower():
            pdfs.append(urljoin(base, href))
    return pdfs

def save_list(urls: list[str], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(urls))
    print(f"[+] Saved {len(urls)} links to {path}")

def download_all(urls: list[str], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for url in tqdm(urls, desc="Downloading PDFs"):
        fname = os.path.join(out_dir, url.split("/")[-1].split("?")[0])
        if os.path.exists(fname):
            continue
        try:
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            with open(fname, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            print(f"[!] Failed {url}: {e}")

def main():
    html  = fetch_html(PAGE_URL)
    pdfs  = parse_pdfs(html, "https://www.wcoomd.org")
    save_list(pdfs, OUT_FILE)
    if DOWNLOAD:
        download_all(pdfs, OUT_DIR)

if __name__ == "__main__":
    main()
