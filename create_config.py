#!/usr/bin/env python3
import json

config = {
    "db_config": {
        "host": "localhost",
        "port": 5432,
        "database": "encar",
        "user": "postgres",
        "password": "password"
    },
    "update_config": {
        "max_workers": 5,
        "update_type": "daily"
    },
    "notification_config": {
        "enabled": False,
        "smtp": {
            "server": "smtp.gmail.com",
            "port": 587,
            "username": "your-email@gmail.com",
            "password": "your-app-password",
            "to_email": "admin@yourcompany.com"
        },
        "send_on_success": True,
        "send_on_error": True
    },
    "backup_config": {
        "enabled": True,
        "backup_dir": "./backups",
        "keep_days": 7
    }
}

with open('config.json', 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2)

print("✅ Конфигурация создана")