import hashlib
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, BigInteger, String, Float, Text, DateTime, Boolean, Index, select, insert, update, delete, func, and_, or_, inspect, text, case
)
from .fingerprint import hamming, bands, BANDS

meta = MetaData()

items = Table(
    "items", meta,
    Column("id", String(36), primary_key=True),
    Column("kind", String(12), nullable=False),
    Column("phash", String(16)),
    Column("dhash", String(16)),
    Column("b0", Integer), Column("b1", Integer), Column("b2", Integer), Column("b3", Integer),
    Column("frames", Text),
    Column("first_seen", DateTime, nullable=False),
    Column("last_seen", DateTime, nullable=False),
    Column("sightings", Integer, default=1),
    Column("p_mean", Float, default=0.5),
    Column("p_n", Integer, default=0),
    Column("tier", String(24)),
    Column("generator", String(40)),
    Column("apps", Text, default="{}"),
    Column("feedback_ai", Integer, default=0),
    Column("feedback_human", Integer, default=0),
)
Index("ix_items_b0", items.c.b0)
Index("ix_items_b1", items.c.b1)
Index("ix_items_b2", items.c.b2)
Index("ix_items_b3", items.c.b3)

marks = Table(
    "audio_marks", meta,
    Column("hash", Integer, nullable=False),
    Column("item_id", String(36), nullable=False),
    Column("t", Integer, nullable=False),
)
Index("ix_marks_hash", marks.c.hash)

checks = Table(
    "checks", meta,
    Column("id", String(36), primary_key=True),
    Column("item_id", String(36)),
    Column("device", String(64)),
    Column("source_app", String(80)),
    Column("trigger", String(32)),
    Column("kind", String(12)),
    Column("tier", String(24)),
    Column("p", Float),
    Column("signals", Text),
    Column("ms", Integer),
    Column("payload", Text),
    Column("counted", Boolean),
    Column("created", DateTime, nullable=False),
)
Index("ix_checks_created", checks.c.created)
Index("ix_checks_item_device", checks.c.item_id, checks.c.device)

feedback = Table(
    "feedback", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("check_id", String(36), nullable=False),
    Column("label", String(12), nullable=False),
    Column("created", DateTime, nullable=False),
)

push_tokens = Table(
    "push_tokens", meta,
    Column("device", String(64), primary_key=True),
    Column("platform", String(12)),
    Column("token", String(256), nullable=False),
    Column("updated", DateTime, nullable=False),
)

webhooks = Table(
    "webhooks", meta,
    Column("id", String(36), primary_key=True),
    Column("owner", String(16), nullable=False),
    Column("url", Text, nullable=False),
    Column("threshold", Integer, default=25),
    Column("created", DateTime, nullable=False),
)

factchecks = Table(
    "factchecks", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("item_id", String(36), nullable=False),
    Column("publisher", String(120)),
    Column("rating", String(120)),
    Column("url", Text),
    Column("created", DateTime, nullable=False),
)
Index("ix_fact_item", factchecks.c.item_id)


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Index_:
    def __init__(self, url, salt="dev-salt"):
        kwargs = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(url, **kwargs)
        meta.create_all(self.engine)
        self._migrate()
        self.salt = salt

    def _migrate(self):
        insp = inspect(self.engine)
        quote = self.engine.dialect.identifier_preparer.quote
        missing = []
        for table in meta.sorted_tables:
            existing = {col["name"] for col in insp.get_columns(table.name)}
            missing.extend((table.name, col.name, col.type.compile(self.engine.dialect)) for col in table.columns if col.name not in existing)
        for tname, cname, ctype in missing:
            try:
                with self.engine.begin() as c:
                    c.execute(text(f"ALTER TABLE {quote(tname)} ADD COLUMN {quote(cname)} {ctype}"))
            except Exception as e:
                if "duplicate" not in str(e).lower() and "already exists" not in str(e).lower():
                    raise
        for table in meta.sorted_tables:
            for idx in table.indexes:
                try:
                    idx.create(self.engine, checkfirst=True)
                except Exception as e:
                    if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                        raise

    def device_hash(self, device_id):
        if not device_id:
            return None
        return hashlib.sha256((self.salt + ":" + device_id).encode()).hexdigest()[:40]

    def near(self, phash, threshold=10, kind=None):
        bs = bands(phash)
        cond = or_(items.c.b0 == bs[0], items.c.b1 == bs[1], items.c.b2 == bs[2], items.c.b3 == bs[3])
        if kind:
            cond = and_(cond, items.c.kind == kind)
        with self.engine.connect() as c:
            rows = c.execute(select(items).where(cond).limit(400)).mappings().all()
        best = None
        for r in rows:
            if not r["phash"]:
                continue
            d = hamming(r["phash"], phash)
            if d <= threshold and (best is None or d < best[1]):
                best = (dict(r), d)
        return best

    def near_video(self, frames, threshold=8):
        seen = {}
        for f in frames:
            hit = self.near(f, threshold=threshold, kind="video")
            if hit:
                row = hit[0]
                parent = json.loads(row["frames"] or "[]")[0] if row["tier"] == "frame" else row["id"]
                seen[parent] = seen.get(parent, 0) + 1
        if not seen:
            return None
        item_id, n = max(seen.items(), key=lambda kv: kv[1])
        if n / max(1, len(frames)) < 0.4:
            return None
        return self.get(item_id), n

    def audio_candidates(self, query_marks):
        hashes = list({h for h, _ in query_marks})
        if not hashes:
            return []
        out = []
        with self.engine.connect() as c:
            for i in range(0, len(hashes), 500):
                chunk = hashes[i:i + 500]
                rows = c.execute(select(marks.c.item_id, marks.c.hash, marks.c.t).where(marks.c.hash.in_(chunk))).all()
                out.extend((r[0], r[1], r[2]) for r in rows)
        return out

    def get(self, item_id):
        with self.engine.connect() as c:
            r = c.execute(select(items).where(items.c.id == item_id)).mappings().first()
        return dict(r) if r else None

    def seen_from(self, item_id, device, hours=24):
        if not device:
            return False
        since = now() - timedelta(hours=hours)
        with self.engine.connect() as c:
            row = c.execute(select(checks.c.id).where(and_(checks.c.item_id == item_id, checks.c.device == self.device_hash(device), checks.c.counted.is_(True), checks.c.created >= since)).limit(1)).first()
        return row is not None

    def record(self, kind, prints=None, frames=None, audio=None, p=0.5, tier="unclear", generator="", source_app="", match=None, device=None):
        t = now()
        if match:
            item = match
            apps = json.loads(item.get("apps") or "{}")
            repeat = self.seen_from(item["id"], device)
            source_app = (source_app or "")[:80]
            if source_app and not repeat:
                apps[source_app] = apps.get(source_app, 0) + 1
            n = item["p_n"] + (0 if repeat else 1)
            p_mean = item["p_mean"] if repeat else (item["p_mean"] * item["p_n"] + p) / n
            with self.engine.begin() as c:
                c.execute(update(items).where(items.c.id == item["id"]).values(
                    last_seen=t, sightings=item["sightings"] + (0 if repeat else 1), p_mean=p_mean, p_n=n,
                    tier=tier, apps=json.dumps(apps), generator=item.get("generator") or generator,
                ))
            item = self.get(item["id"])
            return item, not repeat
        source_app = (source_app or "")[:80]
        item_id = str(uuid.uuid4())
        ph = (prints or {}).get("phash")
        row = {
            "id": item_id, "kind": kind, "phash": ph, "dhash": (prints or {}).get("dhash"),
            "frames": json.dumps(frames or []), "first_seen": t, "last_seen": t, "sightings": 1,
            "p_mean": p, "p_n": 1, "tier": tier, "generator": generator,
            "apps": json.dumps({source_app: 1} if source_app else {}),
            "feedback_ai": 0, "feedback_human": 0,
        }
        if ph:
            for i, b in enumerate(bands(ph)):
                row[f"b{i}"] = b
        with self.engine.begin() as c:
            c.execute(insert(items).values(**row))
            if frames and not ph:
                pass
            if audio:
                seen = set()
                rows = []
                for h, tt in audio:
                    if (h, tt) in seen:
                        continue
                    seen.add((h, tt))
                    rows.append({"hash": h, "item_id": item_id, "t": int(tt)})
                for i in range(0, len(rows), 1000):
                    c.execute(insert(marks), rows[i:i + 1000])
        return self.get(item_id), True

    def record_frames(self, frames, item_id):
        with self.engine.begin() as c:
            for f in frames[:8]:
                fid = str(uuid.uuid4())
                row = {"id": fid, "kind": "video", "phash": f, "frames": json.dumps([item_id]), "first_seen": now(), "last_seen": now(), "sightings": 1, "p_mean": 0.5, "p_n": 0, "tier": "frame", "apps": "{}", "feedback_ai": 0, "feedback_human": 0}
                for i, b in enumerate(bands(f)):
                    row[f"b{i}"] = b
                c.execute(insert(items).values(**row))

    def log_check(self, item_id, device, source_app, trigger, kind, tier, p, signals, ms, cid=None, payload=None, counted=False):
        cid = cid or str(uuid.uuid4())
        with self.engine.begin() as c:
            c.execute(insert(checks).values(
                id=cid, item_id=item_id, device=self.device_hash(device), source_app=(source_app or "")[:80],
                trigger=(trigger or "")[:32], kind=kind, tier=tier, p=p, signals=json.dumps(signals)[:4000], ms=ms,
                payload=payload or None, counted=bool(counted), created=now(),
            ))
        return cid

    def get_check(self, cid):
        with self.engine.connect() as c:
            row = c.execute(select(checks.c.payload).where(checks.c.id == cid)).first()
        if not row or not row[0]:
            return None
        try:
            return json.loads(row[0])
        except ValueError:
            return None

    @staticmethod
    def _vote(label, tier):
        if label in ("ai", "human"):
            return label
        if tier in ("likely_synthetic", "leaning_synthetic"):
            return "human"
        if tier in ("leaning_human", "no_ai_signals", "verified_capture"):
            return "ai"
        return None

    def add_feedback(self, check_id, label):
        with self.engine.begin() as c:
            row = c.execute(select(checks.c.item_id, checks.c.tier, checks.c.device).where(checks.c.id == check_id)).first()
            if not row:
                return False
            item_id, tier, dev = row
            joined = select(feedback.c.id, feedback.c.label, checks.c.tier).select_from(feedback.join(checks, feedback.c.check_id == checks.c.id))
            if item_id and dev:
                prev = c.execute(joined.where(and_(checks.c.item_id == item_id, checks.c.device == dev)).order_by(feedback.c.created)).first()
            else:
                prev = c.execute(joined.where(feedback.c.check_id == check_id)).first()
            vote = self._vote(label, tier)
            if prev and self._vote(prev[1], prev[2]) == vote:
                return True
            if prev:
                c.execute(update(feedback).where(feedback.c.id == prev[0]).values(check_id=check_id, label=label, created=now()))
                undo = self._vote(prev[1], prev[2])
                if item_id and undo:
                    col = items.c.feedback_ai if undo == "ai" else items.c.feedback_human
                    c.execute(update(items).where(items.c.id == item_id).values({col: case((col > 0, col - 1), else_=0)}))
            else:
                c.execute(insert(feedback).values(check_id=check_id, label=label, created=now()))
            if item_id and vote:
                col = items.c.feedback_ai if vote == "ai" else items.c.feedback_human
                c.execute(update(items).where(items.c.id == item_id).values({col: col + 1}))
        return True

    def add_webhook(self, owner, url, threshold):
        wid = str(uuid.uuid4())
        with self.engine.begin() as c:
            c.execute(insert(webhooks).values(id=wid, owner=owner[:16], url=url[:2000], threshold=max(2, int(threshold)), created=now()))
        return wid

    def list_webhooks(self, owner=None):
        with self.engine.connect() as c:
            q = select(webhooks)
            if owner:
                q = q.where(webhooks.c.owner == owner[:16])
            rows = c.execute(q).mappings().all()
        return [{"id": r["id"], "url": r["url"], "threshold": r["threshold"], "created": r["created"].isoformat()} for r in rows]

    def remove_webhook(self, owner, wid):
        with self.engine.begin() as c:
            n = c.execute(delete(webhooks).where(and_(webhooks.c.id == wid, webhooks.c.owner == owner[:16]))).rowcount
        return n > 0

    def save_push_token(self, device, platform, token):
        dh = self.device_hash(device)
        if not dh or not token:
            return False
        with self.engine.begin() as c:
            c.execute(delete(push_tokens).where(push_tokens.c.device == dh))
            c.execute(insert(push_tokens).values(device=dh, platform=(platform or "")[:12], token=token[:256], updated=now()))
        return True

    def push_token(self, device):
        dh = self.device_hash(device)
        if not dh:
            return None
        with self.engine.connect() as c:
            row = c.execute(select(push_tokens.c.token).where(push_tokens.c.device == dh)).first()
        return row[0] if row else None

    def add_factchecks(self, item_id, claims):
        if not claims:
            return
        with self.engine.begin() as c:
            c.execute(delete(factchecks).where(factchecks.c.item_id == item_id))
            for cl in claims[:5]:
                c.execute(insert(factchecks).values(item_id=item_id, publisher=cl.get("publisher", "")[:120], rating=cl.get("rating", "")[:120], url=cl.get("url", ""), created=now()))

    def factchecks_for(self, item_id):
        with self.engine.connect() as c:
            rows = c.execute(select(factchecks).where(factchecks.c.item_id == item_id)).mappings().all()
        return [dict(r) for r in rows]

    def stats(self):
        with self.engine.connect() as c:
            total = c.execute(select(func.count()).select_from(items).where(items.c.p_n > 0)).scalar() or 0
            n_checks = c.execute(select(func.count()).select_from(checks)).scalar() or 0
            day = now() - timedelta(days=1)
            today = c.execute(select(func.count()).select_from(checks).where(checks.c.created >= day)).scalar() or 0
            tiers = c.execute(select(checks.c.tier, func.count()).group_by(checks.c.tier)).all()
            kinds = c.execute(select(checks.c.kind, func.count()).group_by(checks.c.kind)).all()
            apps = c.execute(select(checks.c.source_app, func.count()).group_by(checks.c.source_app).order_by(func.count().desc()).limit(10)).all()
            repeat = c.execute(select(func.count()).select_from(items).where(items.c.sightings > 1)).scalar() or 0
            fb = c.execute(select(feedback.c.label, func.count()).group_by(feedback.c.label)).all()
        return {
            "items": int(total),
            "checks": int(n_checks),
            "checks_24h": int(today),
            "repeat_items": int(repeat),
            "tiers": {t or "none": int(n) for t, n in tiers},
            "kinds": {k or "none": int(n) for k, n in kinds},
            "apps": {a or "unknown": int(n) for a, n in apps},
            "feedback": {l: int(n) for l, n in fb},
        }

    def trending(self, hours=24, limit=10):
        since = now() - timedelta(hours=hours)
        with self.engine.connect() as c:
            devices = func.count(func.distinct(checks.c.device))
            rows = c.execute(
                select(checks.c.item_id, devices.label("n"))
                .where(and_(checks.c.created >= since, checks.c.item_id.isnot(None)))
                .group_by(checks.c.item_id).order_by(devices.desc()).limit(limit)
            ).all()
            out = []
            for item_id, n in rows:
                it = c.execute(select(items).where(items.c.id == item_id)).mappings().first()
                if not it or n < 2:
                    continue
                out.append({
                    "item": item_id[:8], "kind": it["kind"], "recent": int(n), "sightings": it["sightings"],
                    "tier": it["tier"], "p_mean": round(it["p_mean"], 2), "first_seen": it["first_seen"].isoformat(),
                    "apps": json.loads(it["apps"] or "{}"), "generator": it["generator"] or "",
                })
        return out

    def timeline(self, hours=48):
        since = now() - timedelta(hours=hours)
        with self.engine.connect() as c:
            rows = c.execute(select(checks.c.created, checks.c.tier).where(checks.c.created >= since)).all()
        buckets = {}
        for created, tier in rows:
            key = created.replace(minute=0, second=0, microsecond=0)
            b = buckets.setdefault(key, {"total": 0, "synthetic": 0})
            b["total"] += 1
            if tier in ("likely_synthetic", "leaning_synthetic"):
                b["synthetic"] += 1
        start = now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours - 1)
        out = []
        for i in range(hours):
            key = start + timedelta(hours=i)
            b = buckets.get(key, {"total": 0, "synthetic": 0})
            out.append({"hour": key.isoformat(), "total": b["total"], "synthetic": b["synthetic"]})
        return out

    def recent(self, limit=50):
        with self.engine.connect() as c:
            rows = c.execute(select(checks.c.created, checks.c.kind, checks.c.tier, checks.c.p, checks.c.source_app, checks.c.ms).order_by(checks.c.created.desc()).limit(limit)).all()
        return [{"created": r[0].isoformat(), "kind": r[1], "tier": r[2], "p": r[3], "app": r[4], "ms": r[5]} for r in rows]

    def purge(self, days):
        cutoff = now() - timedelta(days=days)
        with self.engine.begin() as c:
            n = c.execute(delete(checks).where(checks.c.created < cutoff)).rowcount
        return n
