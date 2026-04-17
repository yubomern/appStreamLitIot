#!/usr/bin/env python3
"""
Manage SQLite database for crash dumps
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

class CrashDatabase:
    def __init__(self, db_path: str = "crash_dumps.db"):
        # Save database path and create tables if not exist
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        # Create tables for crashes and call stack
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for crash info
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crashes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                unix_timestamp INTEGER NOT NULL,
                type INTEGER NOT NULL,
                file TEXT,
                line INTEGER,
                function TEXT,
                process_id INTEGER,
                thread_id INTEGER,
                stack_depth INTEGER,
                cpu_usage REAL,
                memory_used_kb INTEGER,
                memory_total_kb INTEGER,
                probable_cause TEXT,
                severity TEXT,
                confidence_score INTEGER,
                raw_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table for call stack frames
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_stack (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crash_id INTEGER NOT NULL,
                frame_index INTEGER NOT NULL,
                address TEXT NOT NULL,
                decoded_function TEXT,
                decoded_file TEXT,
                decoded_line INTEGER,
                FOREIGN KEY (crash_id) REFERENCES crashes(id)
            )
        ''')
        
        # Indexes for faster search
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON crashes(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_severity ON crashes(severity)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_type ON crashes(type)')
        
        conn.commit()
        conn.close()
    
    def add_crash(self, crash_data: Dict) -> int:
        # Insert new crash into database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO crashes (
                timestamp, unix_timestamp, type, file, line, function,
                process_id, thread_id, stack_depth, cpu_usage,
                memory_used_kb, memory_total_kb, probable_cause,
                severity, confidence_score, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            crash_data.get('timestamp', ''),
            crash_data.get('unix_timestamp', 0),
            crash_data.get('type', 0),
            crash_data.get('file', ''),
            crash_data.get('line', 0),
            crash_data.get('function', ''),
            crash_data.get('process_id', 0),
            crash_data.get('thread_id', 0),
            crash_data.get('stack_depth', 0),
            crash_data.get('system_metrics', {}).get('cpu_usage_percent', 0),
            crash_data.get('system_metrics', {}).get('memory_used_kb', 0),
            crash_data.get('system_metrics', {}).get('memory_total_kb', 0),
            crash_data.get('analysis', {}).get('probable_cause', ''),
            crash_data.get('analysis', {}).get('severity', ''),
            crash_data.get('analysis', {}).get('confidence_score', 0),
            json.dumps(crash_data)
        ))
        
        crash_id = cursor.lastrowid
        
        # Insert call stack frames
        call_stack = crash_data.get('call_stack', [])
        for idx, addr in enumerate(call_stack):
            cursor.execute('''
                INSERT INTO call_stack (crash_id, frame_index, address)
                VALUES (?, ?, ?)
            ''', (crash_id, idx, addr))
        
        conn.commit()
        conn.close()
        
        return crash_id
    
    def get_all_crashes(self, limit: int = 100) -> List[Dict]:
        # Get list of crashes (latest first)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM crashes ORDER BY unix_timestamp DESC LIMIT ?
        ''', (limit,))
        
        crashes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return crashes
    
    def get_crash_by_id(self, crash_id: int) -> Optional[Dict]:
        # Get one crash and its call stack
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM crashes WHERE id = ?', (crash_id,))
        crash = cursor.fetchone()
        
        if crash:
            crash_dict = dict(crash)
            
            cursor.execute('''
                SELECT * FROM call_stack WHERE crash_id = ? ORDER BY frame_index
            ''', (crash_id,))
            
            crash_dict['call_stack'] = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return crash_dict
        
        conn.close()
        return None
    
    def get_statistics(self) -> Dict:
        # Get global stats about crashes
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        stats = {}
        
        # Total crashes
        cursor.execute('SELECT COUNT(*) as total FROM crashes')
        stats['total_crashes'] = cursor.fetchone()['total']
        
        # Crashes by severity
        cursor.execute('''
            SELECT severity, COUNT(*) as count 
            FROM crashes 
            GROUP BY severity
        ''')
        stats['by_severity'] = {row['severity']: row['count'] 
                               for row in cursor.fetchall()}
        
        # Crashes by type
        cursor.execute('''
            SELECT type, COUNT(*) as count 
            FROM crashes 
            GROUP BY type
        ''')
        stats['by_type'] = {row['type']: row['count'] 
                           for row in cursor.fetchall()}
        
        # Crashes per day (last 7 days)
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as count 
            FROM crashes 
            WHERE unix_timestamp > (strftime('%s', 'now') - 604800)
            GROUP BY DATE(timestamp)
        ''')
        stats['daily_crashes'] = {row['date']: row['count'] 
                                 for row in cursor.fetchall()}
        
        conn.close()
        return stats
    
    def delete_old_crashes(self, days: int = 30):
        # Delete crashes older than given days
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM crashes 
            WHERE unix_timestamp < (strftime('%s', 'now') - ?)
        ''', (days * 86400,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
