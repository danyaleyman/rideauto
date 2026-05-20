#!/usr/bin/env python3
import sys
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("62.76.31.51", username="root", password=sys.argv[1], timeout=30)
cmds = [
    "ps aux | grep postgres_catalog_sync | grep -v grep",
    "ps aux | grep rideauto | grep python | grep -v grep | head -5",
    "curl -sS 'http://127.0.0.1:8000/api/search?region=china&source=che168&sort=price_high&limit=3'",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd)
    print("===", cmd[:60])
    print(o.read().decode()[:2000])
c.close()
