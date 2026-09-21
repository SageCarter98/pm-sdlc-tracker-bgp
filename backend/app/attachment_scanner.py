"""WP15 Phase 2: malware scanning for uploaded evidence attachments, via
Cloudmersive's Virus Scan API (POST /virus/scan/file, `Apikey` header,
multipart field "inputFile", JSON {"CleanResult": bool, "FoundViruses": [...]}).
Chosen over VirusTotal specifically because VirusTotal's standard API
shares submitted files with a multi-vendor corpus -- a poor fit for a
platform built around not letting tenant data cross boundaries it
shouldn't; Cloudmersive's scan result stays between this app and them.

`Scanner` is the seam a different vendor would replace without touching
app/routers/attachments.py. `scan()` never invents "clean" on ambiguity --
a call that fails, times out, or comes back in an unexpected shape returns
"error", which app/routers/attachments.py treats exactly like "unavailable"
(blocks download, does not quarantine as a version-lineage rejection). Only
a real, parsed "not clean" result returns "infected"."""

from __future__ import annotations

import httpx

from app.core.config import settings

SCAN_URL = "https://api.cloudmersive.com/virus/scan/file"
SCAN_TIMEOUT_SECONDS = 30


class Scanner:
    def scan(self, filename: str, data: bytes) -> str:
        """Returns "clean", "infected", "error", or "unavailable" (not configured)."""
        raise NotImplementedError


class CloudmersiveScanner(Scanner):
    def scan(self, filename: str, data: bytes) -> str:
        if not settings.cloudmersive_api_key:
            return "unavailable"
        try:
            resp = httpx.post(
                SCAN_URL,
                headers={"Apikey": settings.cloudmersive_api_key},
                files={"inputFile": (filename, data)},
                timeout=SCAN_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            result = resp.json()
        except (httpx.HTTPError, ValueError):
            return "error"
        if "CleanResult" not in result:
            return "error"
        return "clean" if result["CleanResult"] else "infected"


scanner: Scanner = CloudmersiveScanner()
