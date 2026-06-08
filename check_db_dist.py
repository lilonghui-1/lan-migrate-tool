#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查编译目录下的数据库
"""
import sqlite3
import os

DB_PATH = r"D:\trea-TMS\lan-migrate-tool\dist_new\transfer_state.db"

if not os.path.exists(DB_PATH):
    print(f"数据库文件不存在: {DB_PATH}")
    exit(0)

print(f"查看数据库: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = cursor.fetchall()
print(f"\n表列表: {[t[0] for t in tables]}")

for table_name in [t[0] for t in tables]:
    print(f"\n{'='*80}")
    print(f"表: {table_name}")
    print(f"{'='*80}")
    
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    print("\n列:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    print(f"\n记录 (前30条):")
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 30;")
        rows = cursor.fetchall()
        
        if rows:
            col_names = [col[1] for col in columns]
            print(f"  {' | '.join(col_names)}")
            print(f"  {'-' * (len(' | '.join(col_names)))}")
            
            for row in rows:
                row_str = []
                for val in row:
                    if isinstance(val, str) and len(val) > 60:
                        val = val[:60] + "..."
                    row_str.append(str(val))
                print(f"  {' | '.join(row_str)}")
        else:
            print("  (无数据)")
    except Exception as e:
        print(f"  读取失败: {e}")

conn.close()
