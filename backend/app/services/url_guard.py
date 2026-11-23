"""Safe remote video download: HTTP/HTTPS only, public IPs only (SSRF guard re-applied on
every redirect hop), size cap, timeout, content-type/extension allow-list, no shell."""
import asyncio
import ipaddress
import socket
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from ..config import get_settings
from .storage import VIDEO_EXT

MAX_REDIRECTS = 3
CT_TO_EXT = {
    "video/mp4": ".mp4", "video/quicktime": ".mov", "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv", "video/webm": ".webm", "video/mpeg": ".mpg",
    "video/x-m4v": ".m4v",
}
GENERIC_CT = {"application/octet-stream", "binary/octet-stream"}


class UrlError(Exception):
    """Invalid or disallowed URL (client error)."""


class DownloadError(Exception):
    """Remote fetch failed after the URL was accepted."""


def _ip_blocked(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not ip.is_global


def resolve_public(host: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlError("The URL host could not be resolved.") from exc
    ips = sorted({i[4][0] for i in infos})
    if not ips:
        raise UrlError("The URL host could not be resolved.")
    for raw in ips:
        if _ip_blocked(ipaddress.ip_address(raw.split("%")[0])):
            raise UrlError("URLs pointing to local or internal network addresses are not allowed.")
    return ips


def validate_url(url: str, resolver=None) -> str:
    """Syntactic + SSRF validation. Returns the normalised URL."""
    url = (url or "").strip()
    if not url or len(url) > 2048:
        raise UrlError("Enter a valid video URL.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise UrlError("Enter a valid video URL.") from exc
    if parts.scheme not in ("http", "https"):
        raise UrlError("Only http and https video URLs are supported.")
    if not parts.hostname:
        raise UrlError("Enter a valid video URL.")
    if parts.username or parts.password:
        raise UrlError("URLs containing credentials are not allowed.")
    try:
        literal = ipaddress.ip_address(parts.hostname)
        if _ip_blocked(literal):
            raise UrlError("URLs pointing to local or internal network addresses are not allowed.")
    except ValueError:
        pass
    (resolver or resolve_public)(parts.hostname, port or (443 if parts.scheme == "https" else 80))
    return url


def _ext_for(url: str, content_type: str) -> str | None:
    ext = Path(unquote(urlsplit(url).path)).suffix.lower()
    if content_type in CT_TO_EXT:
        return ext if ext in VIDEO_EXT else CT_TO_EXT[content_type]
    if content_type in GENERIC_CT and ext in VIDEO_EXT:
        return ext
    return None


async def download_video(url: str, dest_dir: Path, max_bytes: int, timeout_s: int,
                         resolver=None) -> tuple[Path, str]:
    """Download into dest_dir (a private temp directory). Returns (path, display filename)."""
    settings = get_settings()
    deadline = time.monotonic() + timeout_s
    current = await asyncio.to_thread(validate_url, url, resolver)
    timeout = httpx.Timeout(connect=10, read=20, write=20, pool=10)
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout,
                                 trust_env=settings.url_use_env_proxy) as client:
        for _hop in range(MAX_REDIRECTS + 1):
            try:
                async with client.stream("GET", current, headers={"Accept": "video/*,*/*;q=0.5",
                                                                   "User-Agent": "VisualFind/1.0"}) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        loc = resp.headers.get("location")
                        if not loc:
                            raise DownloadError("The server sent an invalid redirect.")
                        current = await asyncio.to_thread(validate_url, urljoin(current, loc), resolver)
                        continue
                    if resp.status_code != 200:
                        raise DownloadError(f"The video server responded with HTTP {resp.status_code}.")
                    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                    ext = _ext_for(current, ctype)
                    if ext is None:
                        raise DownloadError("The URL does not point to a supported video file "
                                            f"(content type: {ctype or 'unknown'}).")
                    declared = resp.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > max_bytes:
                        raise DownloadError(f"The video exceeds the {max_bytes // (1024 * 1024)} MB limit.")
                    dest = dest_dir / f"{uuid.uuid4().hex}{ext}"
                    size = 0
                    with open(dest, "wb") as out:
                        async for chunk in resp.aiter_bytes(256 * 1024):
                            size += len(chunk)
                            if size > max_bytes:
                                raise DownloadError(f"The video exceeds the {max_bytes // (1024 * 1024)} MB limit.")
                            if time.monotonic() > deadline:
                                raise DownloadError("The video download timed out.")
                            out.write(chunk)
                    if size == 0:
                        raise DownloadError("The downloaded file is empty.")
                    name = Path(unquote(urlsplit(current).path)).name or f"video{ext}"
                    return dest, name[:120]
            except httpx.TimeoutException as exc:
                raise DownloadError("The video download timed out.") from exc
            except httpx.HTTPError as exc:
                raise DownloadError("The video could not be downloaded from that URL.") from exc
        raise DownloadError("Too many redirects.")


async def async_validate(url: str, resolver=None) -> str:
    return await asyncio.to_thread(validate_url, url, resolver)
