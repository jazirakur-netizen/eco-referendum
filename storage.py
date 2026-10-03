"""Shared durable ballot storage. No names, IP addresses or token-to-ballot links."""
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey,
                        MetaData, String, Table, Text, create_engine, func, select, update)

metadata = MetaData()
polls = Table("eco_polls", metadata,
    Column("id", String(36), primary_key=True),
    Column("title", Text, nullable=False),
    Column("document", String(120), nullable=False),
    Column("context", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("closed_at", DateTime(timezone=True)),
    Column("is_open", Boolean, nullable=False))
tokens = Table("eco_tokens", metadata,
    Column("digest", String(64), primary_key=True),
    Column("poll_id", String(36), ForeignKey("eco_polls.id"), nullable=False),
    Column("used", Boolean, nullable=False))
ballots = Table("eco_ballots", metadata,
    Column("id", String(36), primary_key=True),
    Column("poll_id", String(36), ForeignKey("eco_polls.id"), nullable=False),
    Column("choice", String(8), nullable=False),
    Column("reason", Text, nullable=False),
    CheckConstraint("choice IN ('pro', 'con')", name="eco_choice_valid"))


class VoteError(ValueError):
    pass


def open_engine(url, *, local_test=False):
    # SQLite is only an explicitly requested local test backend, never a cloud fallback.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+psycopg://") and not (local_test and url.startswith("sqlite://")):
        raise ValueError("PostgreSQL connection required")
    options = {"pool_pre_ping": True, "hide_parameters": True}
    if url.startswith("postgresql"):
        options["connect_args"] = {"connect_timeout": 10, "prepare_threshold": None}
    return create_engine(url, **options)


def initialize(engine):
    metadata.create_all(engine)


def create_poll(engine, title, document, context=""):
    title, document, context = title.strip(), document.strip(), context.strip()
    if not 5 <= len(title) <= 2000 or not 1 <= len(document) <= 120 or len(context) > 5000:
        raise ValueError("Сұрақты (5–2000 таңба) және нөмірін (1–120 таңба) толтырыңыз.")
    poll_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(polls.insert().values(id=poll_id, title=title, document=document,
            context=context, created_at=datetime.now(timezone.utc), is_open=True))
    return poll_id


def list_polls(engine, only_open=False):
    query = select(polls).order_by(polls.c.created_at.desc(), polls.c.id)
    if only_open:
        query = query.where(polls.c.is_open.is_(True))
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(query).mappings()]


def close_poll(engine, poll_id):
    with engine.begin() as conn:
        conn.execute(update(polls).where(polls.c.id == poll_id, polls.c.is_open.is_(True))
            .values(is_open=False, closed_at=datetime.now(timezone.utc)))


def token_digest(code):
    normalized = "".join(code.split()).replace("-", "").upper()
    return hashlib.sha256(normalized.encode()).hexdigest()


def issue_codes(engine, poll_id, count):
    if not isinstance(count, int) or not 1 <= count <= 500:
        raise ValueError("Код саны 1–500 аралығында болуы керек.")
    codes = [secrets.token_hex(8).upper() for _ in range(count)]
    codes = ["-".join(code[i:i+4] for i in range(0, 16, 4)) for code in codes]
    with engine.begin() as conn:
        active = conn.execute(select(polls.c.is_open).where(polls.c.id == poll_id)
                              .with_for_update()).scalar_one_or_none()
        if not active:
            raise VoteError("Сауалнама жабық немесе табылмады.")
        conn.execute(tokens.insert(), [{"digest": token_digest(code), "poll_id": poll_id,
                                       "used": False} for code in codes])
    return codes


def cast_vote(engine, poll_id, code, choice, reason=""):
    reason = reason.strip()
    if choice not in ("pro", "con") or len(reason) > 1500 or not code.strip():
        raise VoteError("Код пен жауапты тексеріңіз. Пікір 1500 таңбадан аспасын.")
    with engine.begin() as conn:
        # Serialize with close_poll so no ballots can be accepted after closure.
        active = conn.execute(select(polls.c.is_open).where(polls.c.id == poll_id)
                              .with_for_update()).scalar_one_or_none()
        if not active:
            raise VoteError("Бұл сауалнама аяқталды. Дауыс қабылданбады.")
        redeemed = conn.execute(update(tokens).where(tokens.c.digest == token_digest(code),
            tokens.c.poll_id == poll_id, tokens.c.used.is_(False)).values(used=True))
        if redeemed.rowcount != 1:
            raise VoteError("Код жарамсыз, басқа сауалнамаға тиесілі немесе бұрын қолданылған.")
        # Ballot and redemption commit together. No token or precise time in ballot table.
        conn.execute(ballots.insert().values(id=str(uuid.uuid4()), poll_id=poll_id,
                                            choice=choice, reason=reason))


def results(engine, poll_id):
    with engine.connect() as conn:
        counts = dict(conn.execute(select(ballots.c.choice, func.count()).where(
            ballots.c.poll_id == poll_id).group_by(ballots.c.choice)).all())
    return {"pro": counts.get("pro", 0), "con": counts.get("con", 0)}


def code_counts(engine, poll_id):
    with engine.connect() as conn:
        issued = conn.execute(select(func.count()).select_from(tokens).where(
            tokens.c.poll_id == poll_id)).scalar_one()
        used = conn.execute(select(func.count()).select_from(tokens).where(
            tokens.c.poll_id == poll_id, tokens.c.used.is_(True))).scalar_one()
    return issued, used


def comments(engine, poll_id, choice=None):
    # Group identical comments; do not export row identifiers or chronological order.
    query = select(ballots.c.choice, ballots.c.reason, func.count().label("count")).where(
        ballots.c.poll_id == poll_id, ballots.c.reason != "")
    if choice:
        query = query.where(ballots.c.choice == choice)
    query = query.group_by(ballots.c.choice, ballots.c.reason).order_by(ballots.c.choice, ballots.c.reason)
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(query).mappings()]
