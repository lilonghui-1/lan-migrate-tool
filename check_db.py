#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查和查看数据库
"""
import sqlite3
import os

# 可能的数据库位置
possible_paths = [
    "transfer_state.db",
    os.path.join(os.path.expanduser("~"), "transfer_state.db"),
    os.path.join(os.getcwd(), "transfer_state.db"),
]

print("查找数据库...")
db_path = None
for path in possible_paths:
    if os.path.exists(path):
        db_path = path
        print(f"找到数据库: {db_path}")
        break

if not db_path:
    print("未找到数据库文件")
    print("可能的位置:")
    for path in possible_paths:
        print(f"  {path}")
    exit(0)

print("\n查看数据库表结构...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = cursor.fetchall()
print(f"\n表列表: {[t[0] for t in tables]}")

for table_name in [t[0] for t in tables]:
    print(f"\n{'='*80}")
    print(f"表: {table_name}")
    print(f"{'='*80}")
    
    # 查看表结构
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    print("\n列:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # 查看前20条记录
    print(f"\n记录 (前20条):")
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 20;")
        rows = cursor.fetchall()
        
        if rows:
            # 打印列名
            col_names = [col[1] for col in columns]
            print(f"  {' | '.join(col_names)}")
            print(f"  {'-' * (len(' | '.join(col_names)))}")
            
            for row in rows:
                # 格式化显示
                row_str = []
                for val in row:
                    if isinstance(val, str) and len(val) > 50:
                        val = val[:50] + "..."
                    row_str.append(str(val))
                print(f"  {' | '.join(row_str)}")
        else:
            print("  (无数据)")
    except Exception as e:
        print(f"  读取失败: {e}")

conn.close()
