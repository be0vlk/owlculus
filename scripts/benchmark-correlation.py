"""Bounded, repeatable correlation timing/memory and legacy-result comparison.

Run from backend with uv run --locked python ../scripts/benchmark-correlation.py
[--baseline /tmp/entity_correlation_before.py] [--dense]. No production DB is used.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import resource
import sys
import tracemalloc
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
for key, value in {
    "SECRET_KEY": "isolated-correlation-benchmark",
    "POSTGRES_USER": "unused",
    "POSTGRES_PASSWORD": "unused",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "unused",
    "FRONTEND_URL": "http://localhost:3000",
}.items():
    os.environ.setdefault(key, value)

from sqlmodel import Session, SQLModel, create_engine

from app.database.models import Case, Entity, User
from app.schemas.entity_schema import EntityCreate
from app.services import entity_correlation

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--baseline", type=Path)
parser.add_argument("--dense", action="store_true")
args = parser.parse_args()
module = entity_correlation
if args.baseline:
    spec = importlib.util.spec_from_file_location("correlation_baseline", args.baseline)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

with TemporaryDirectory(prefix="correlation-benchmark-") as directory:
    engine = create_engine(f"sqlite:///{directory}/benchmark.db")
    SQLModel.metadata.create_all(engine)
    source_count, candidate_count = (40, 1000) if args.dense else (300, 4000)
    with Session(engine) as db:
        user = User(
            username="benchmark",
            email="benchmark@example.com",
            password_hash="unused",
            role="Admin",
            is_superadmin=True,
        )
        source, related = Case(case_number="A", title="A"), Case(
            case_number="B", title="B"
        )
        db.add_all([user, source, related])
        db.flush()
        for case, count in ((source, source_count), (related, candidate_count)):
            rows = []
            for index in range(count):
                employer = (
                    "Dense"
                    if args.dense
                    else (
                        f"Employer {index}"
                        if case is source or index < 60
                        else f"Nonmatch {index}"
                    )
                )
                data = EntityCreate(
                    entity_type="person",
                    data={
                        "first_name": f"{case.case_number} {index}",
                        "employer": employer,
                        "usernames": [
                            f"https://{case.case_number.lower()}{index}.example.com/@profile"
                        ],
                    },
                ).data
                rows.append(
                    Entity(
                        case_id=case.id,
                        created_by_id=user.id,
                        entity_type="person",
                        data=data,
                    )
                )
            db.add_all(rows)
            db.flush()
        db.commit()
        source_id, user_id = source.id, user.id
    with Session(engine) as db:
        source, user = db.get(Case, source_id), db.get(User, user_id)
        query = module.EntityCorrelation(db)
        tracemalloc.start()
        started = perf_counter()
        iterator = (
            query.iter_correlations(source, user)
            if hasattr(query, "iter_correlations")
            else query.correlate(source, user)
        )
        count, fingerprint, first_match = 0, 0, None
        for match in iterator:
            if not hasattr(match, "kind") or match.kind.value in {"email", "phone"}:
                continue
            if first_match is None:
                first_match = perf_counter() - started
            record = [
                match.source_entity.id,
                match.other_entity.id,
                match.other_case.id,
                match.kind.value,
                match.normalized_value,
                [(field.field, field.value) for field in match.source_fields],
                [(field.field, field.value) for field in match.other_fields],
                match.signal,
            ]
            fingerprint = (
                fingerprint
                + int.from_bytes(
                    hashlib.sha256(json.dumps(record, sort_keys=True).encode()).digest()
                )
            ) % (1 << 256)
            count += 1
        elapsed = perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(
            json.dumps(
                {
                    "version": "before" if args.baseline else "after",
                    "workload": "dense" if args.dense else "sparse",
                    "sources": source_count,
                    "candidates": candidate_count,
                    "matches": count,
                    "fingerprint": f"{fingerprint:064x}",
                    "elapsed_seconds": round(elapsed, 3),
                    "first_match_seconds": round(first_match or 0, 3),
                    "peak_traced_mib": round(peak / 1024**2, 2),
                    "process_peak_rss_mib": round(
                        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
                    ),
                }
            )
        )
    engine.dispose()
