#!/usr/bin/env python3
import sys
import paramiko

pw = sys.argv[1]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("62.76.31.51", username="root", password=pw, timeout=30)
cmd = r"""
cd /opt/rideauto
docker compose exec -T postgres psql -U wra -d wra -c "SELECT pid, state, left(query,100) AS q, now()-query_start AS elapsed FROM pg_stat_activity WHERE datname='wra' AND state <> 'idle';"
ls -lh /tmp/rideauto-db-export-20260527-190410/ 2>/dev/null || true
du -sh /tmp/rideauto-db-export-20260527-190410/ 2>/dev/null || true
docker compose exec -T postgres psql -U wra -d wra -c "SELECT relname, pg_size_pretty(pg_total_relation_size(oid)) FROM pg_class WHERE relnamespace = 'wra_export'::regnamespace;" 2>/dev/null || true
"""
_, o, e = c.exec_command(cmd, timeout=120)
print(o.read().decode("utf-8", errors="replace"))
if e.read().decode().strip():
    print("err:", e.read())
c.close()
