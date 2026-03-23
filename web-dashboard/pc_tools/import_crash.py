#!/usr/bin/env python3
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import CrashDatabase

json_path = "/tmp/crash_dump.json"
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'crash_dumps.db')

if not os.path.exists(json_path):
    print(f"❌ Fichier non trouvé: {json_path}")
    sys.exit(1)

with open(json_path, 'r') as f:#Open the file in read mode
    crash_data = json.load(f) #Reads all the content and parses the JSON into a Python dictionary

print(f"📄 Crash chargé depuis: {json_path}")
print(f"📁 Base de données: {db_path}")

db = CrashDatabase(db_path)  #call constractor of class
crash_id = db.add_crash(crash_data)

print(f"✅ Crash importé avec succès ! ID: {crash_id}")
print(f"📊 Type: {crash_data.get('type', 'N/A')}")
print(f"📁 Fichier: {crash_data.get('file', 'N/A')}")
print(f"🔢 Ligne: {crash_data.get('line', 'N/A')}")
print(f"🚨 Sévérité: {crash_data.get('analysis', {}).get('severity', 'N/A')}")
EOF