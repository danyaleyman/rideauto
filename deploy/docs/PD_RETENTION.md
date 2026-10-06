# PD retention (leads / auth)

Aligned with privacy page (`legal.privacy.s4p3`) and `backend/scripts/pd_retention_purge.py`.

| Data | Default TTL | Env |
|------|-------------|-----|
| `lead_requests` | 365 days | `WRA_PD_LEAD_RETENTION_DAYS` |
| `auth_magic_tokens` | 7 days (used/expired) | `WRA_PD_MAGIC_TOKEN_RETENTION_DAYS` |
| `auth_sessions` | 90 days / expired / revoked | `WRA_PD_SESSION_RETENTION_DAYS` |

```bash
# dry-run
python backend/scripts/pd_retention_purge.py --dsn "$DATABASE_URL"
# apply
python backend/scripts/pd_retention_purge.py --dsn "$DATABASE_URL" --apply
sudo systemctl enable --now rideauto-pd-retention.timer
```

PII tables in backups: see [`docs/BACKUP_RESTORE.md`](../../docs/BACKUP_RESTORE.md) §PII.
