# AegisAI Data Retention and Evidence Handling

What AegisAI stores, how sensitive it is, and how long it is kept.

## Why this document exists

A security assessment stores the prompts it sent and the responses it got back.
For a data-leakage test, that response *is* the sensitive payload: it is the
moment a model disclosed something it should not have.

Storing those responses verbatim, unlabelled, means the tool accumulates the
very secrets it discovered, with no way to apply a different policy to them.
AegisAI therefore classifies evidence when it is written, and redacts detected
credential values before they reach the database.

## Evidence sensitivity levels

| Level | Meaning |
|---|---|
| `0` PUBLIC | Nothing sensitive detected. Safe to show anywhere. |
| `1` INTERNAL | Default. Assessment content with no detected credentials or personal data. |
| `2` CONFIDENTIAL | Contains personal data (email, phone, national id). |
| `3` RESTRICTED | Contains a credential: API key, password, private key, or payment card. |

Classification is derived at write time from what the scanner found, and stored
on the record alongside the kinds detected. It is not a guess applied later, so
a policy change does not require re-scanning historical rows.

## What is redacted

Detected credentials are replaced with a keyed placeholder:

```
[REDACTED:api_key:9f2c1a7b4e6d8035]
```

The suffix is an HMAC-SHA256 of the value, keyed with `SECRET_KEY` and truncated
to 16 hex characters. That gives two properties:

- **Proof survives.** Two disclosures of the same secret produce the same
  fingerprint, so an assessment can show that the same credential leaked twice,
  or that a fix actually worked.
- **The secret does not.** The value is not recoverable from the database. The
  keying prevents an attacker holding the database from confirming a guessed
  secret by recomputing the hash; the truncation prevents brute-forcing a short
  one.

Personal data is redacted the same way, and can be disabled per project.

### Detection is deliberately high-precision

A red-team tool that flagged ordinary prose would be unusable, so patterns are
anchored on structure — a known vendor prefix, a PEM header, a
`password = value` assignment — rather than a bare keyword. "The password field
is required" is not a finding. Detection runs against model output that
frequently contains security language by nature, so a loose rule would mark most
evidence `RESTRICTED` and make the classification useless.

Redaction can be disabled per project for cases where the exact bytes matter to
an investigation. **Classification still happens when redaction is off**, so
turning redaction off does not silently unlabel the evidence.

## Where this applies

| Data | Redacted | Classified | Notes |
|---|---|---|---|
| Evidence content (model request/response) | Yes | Yes | At write time |
| Report artifacts (JSON/Markdown) | Yes, by inheritance | Labelled | Generated from stored evidence |
| Findings | No | Via their evidence | A finding title is not itself sensitive |
| Audit log entries | N/A | N/A | Counts and IDs only; never evidence content |
| Target credentials | Encrypted (Fernet) | N/A | Never stored in plaintext anywhere |

Report downloads are served with `Cache-Control: no-store` so evidence does not
linger in shared or browser caches.

Viewing evidence emits an `evidence.viewed` audit event carrying the record
count and how many were restricted. The event never contains evidence content.

## Retention

**Not yet implemented.** There is no automated retention or deletion job, and
no configurable retention period. Evidence persists until its finding is
deleted.

This is a known gap, recorded in the roadmap rather than implied to exist. When
added, it needs:

- a per-project retention period, defaulting to something finite;
- a deletion job that removes evidence and generated artifacts past the period;
- a secure-deletion path, since report artifacts live on a filesystem volume;
- an audit record of what was deleted.

Until then, an operator who needs to bound retention must delete the project.

## Operational note: encrypted volumes

Report artifacts are written to `AEGIS_REPORT_DIR`, which should be an
**encrypted volume** in production. AegisAI does not encrypt the volume itself —
that is the platform's responsibility, and the production Compose file mounts it
as a named volume so it can be backed by encrypted storage.

The same applies to database backups. See `docs/secrets-management.md` for the
`SECRET_KEY` rotation procedure, which invalidates stored credentials and must
be coordinated with a backup that still holds the old key.

## Verifying

```powershell
pytest tests/services/test_redaction.py tests/services/test_evidence_redaction.py tests/api/test_evidence_handling.py
```

Covers detection precision, redaction of secrets and PII, fingerprint
stability, classification at each level, that the secret is absent from both the
returned object and the stored row, that redaction can be disabled without
unlabelling, and that viewing evidence is audited.
