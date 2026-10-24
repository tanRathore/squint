import asyncio
import ipaddress
import json
import logging
import socket
from urllib.parse import urlsplit

log = logging.getLogger("squint.hooks")


def _bad_ip(ip):
    a = ipaddress.ip_address(ip)
    return a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified


async def vet(url):
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError:
        return "that url doesn't parse", None
    if u.scheme not in ("http", "https"):
        return "url should be http(s)", None
    host = (u.hostname or "").strip("[]").lower()
    if not host or u.username or u.password:
        return "url needs a plain host, no credentials", None
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".arpa")):
        return "url points inside the network", None
    port = port or (443 if u.scheme == "https" else 80)
    try:
        if _bad_ip(host):
            return "url points inside the network", None
        return None, (u, host, port, host)
    except ValueError:
        pass
    addrs = await _resolve(host, port)
    if not addrs:
        return "that host doesn't resolve", None
    if any(_bad_ip(a) for a in addrs):
        return "url points inside the network", None
    return None, (u, host, port, addrs[0])


async def unsafe(url):
    problem, _ = await vet(url)
    return problem


def pinned(target):
    u, host, port, ip = target
    lit = f"[{ip}]" if ":" in ip else ip
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    return f"{u.scheme}://{lit}:{port}{path}", host


async def _resolve(host, port):
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError, UnicodeError):
        return []
    return [info[4][0] for info in infos]


def payload(item, verdict):
    return {
        "event": "item.spreading",
        "item": item["id"][:12],
        "kind": item["kind"],
        "sightings": item["sightings"],
        "tier": verdict.tier,
        "p_mean": round(item.get("p_mean", 0.5), 3),
        "first_seen": item["first_seen"].isoformat() if hasattr(item["first_seen"], "isoformat") else str(item["first_seen"]),
        "apps": json.loads(item.get("apps") or "{}"),
        "generator": item.get("generator") or "",
        "factchecks": verdict.factchecks,
    }


async def fire(client, hooks, body):
    async def one(h):
        try:
            problem, target = await vet(h["url"])
            if problem:
                log.info("webhook %s skipped: %s", h["url"][:60], problem)
                return
            url, host = pinned(target)
            r = await client.post(url, json=body, timeout=6, follow_redirects=False, headers={"Host": host}, extensions={"sni_hostname": host})
            if r.status_code >= 300:
                log.info("webhook %s answered %s", h["url"][:60], r.status_code)
        except Exception as e:
            log.info("webhook %s failed: %s", h["url"][:60], e)

    await asyncio.gather(*(one(h) for h in hooks))


def crossed(hooks, sightings):
    return [h for h in hooks if h["threshold"] == sightings]
