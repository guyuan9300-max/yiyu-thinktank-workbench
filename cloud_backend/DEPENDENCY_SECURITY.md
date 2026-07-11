# Cloud backend dependency security boundary

## Temporary ChromaDB exception

As of 2026-07-11, ChromaDB 1.5.9 is the latest published release and remains
affected by `PYSEC-2026-311` (`CVE-2026-45829`, `GHSA-f4j7-r4q5-qw2c`). The
advisory concerns unauthenticated code injection through ChromaDB's HTTP
collection endpoint when an attacker supplies a remote model repository with
`trust_remote_code=true`. Upstream does not currently publish a fixed version.

The Yiyu cloud backend does not run or mount the Chroma HTTP server. Its sole
Chroma import is a lazy import in `app/knowledge_store.py`, and its sole client
construction is an embedded `chromadb.PersistentClient` backed by
`YIYU_CLOUD_DATA_DIR`. It does not use `HttpClient`, `AsyncHttpClient`,
`CloudClient`, Chroma server modules, Chroma `/api/v2` routes, or
`trust_remote_code`.

This is an exploit-path isolation, not an upstream vulnerability fix. Do not
expose a Chroma port from this service or add a Chroma HTTP client/server path.
The executable `scripts/audit_chromadb_isolation.py` fails closed if this
boundary changes.

## Audit gate

Run from the repository root:

```bash
bash scripts/audit-python-dependencies.sh
```

The backend lock permits no advisory exceptions. The cloud lock and a fresh
Python 3.11 resolution of `requirements.deploy.txt` each permit only the exact
ID `PYSEC-2026-311`, after the embedded-only boundary audit passes. The gate
does not use a package-wide or severity-wide ignore. Any additional finding
fails the command.

Remove the exception as soon as ChromaDB publishes a fixed release: raise the
version constraint, regenerate `cloud_backend/uv.lock`, remove the exact
`--ignore-vuln` argument, and rerun the full cloud test suite. Downgrading an
existing Chroma 1.x persistent store to 0.x is not approved without a backup
and a restore/query compatibility test against a copy of real data.
