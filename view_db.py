#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查看传输状态数据库
"""
import sqlite3
import json
from datetime import datetime

DB_PATH = "transfer_state.db"

def view_tasks():
    """查看所有任务"""
    print("=" * 80)
    print("任务列表 (task_progress)")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT task_id, target_dir, status, started_at FROM task_progress ORDER BY started_at DESC")
    rows = cursor.fetchall()
    
    if not rows:
        print("没有找到任务")
    else:
        for row in rows:
            task_id, target_dir, status, started_at = row
            print(f"\n任务ID: {task_id}")
            print(f"目标目录: {target_dir}")
            print(f"状态: {status}")
            print(f"开始时间: {started_at}")
    
    conn.close()

def view_file_progress():
    """查看文件进度"""
    print("\n" + "=" * 80)
    print("文件进度 (file_progress)")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 先获取所有任务
    cursor.execute("SELECT DISTINCT task_id FROM file_progress")
    task_ids = [row[0] for row in cursor.fetchall()]
    
    if not task_ids:
        print("没有找到文件进度记录")
    else:
        for task_id in task_ids:
            print(f"\n任务ID: {task_id}")
            print("-" * 80)
            
            cursor.execute("""
                SELECT file_path, status, size, checksum, completed_at
                FROM file_progress
                WHERE task_id = ?
                ORDER BY completed_at DESC
            """, (task_id,))
            
            rows = cursor.fetchall()
            
            success_count = 0
            failed_count = 0
            pending_count = 0
            
            for row in rows:
                file_path, status, size, checksum, completed_at = row
                status_text = {
                    "pending": "待传输",
                    "in_progress": "传输中",
                    "completed": "已完成",
                    "failed": "失败"
                }.get(status, status)
                
                print(f"  {status_text} | {file_path}")
                if size:
                    print(f"        大小: {size} 字节")
                if completed_at:
                    print(f"        完成时间: {completed_at}")
                print()
                
                if status == "completed":
                    success_count += 1
                elif status == "failed":
                    failed_count += 1
                else:
                    pending_count += 1
            
            print(f"  统计: 已完成 {success_count}, 失败 {failed_count}, 待传输 {pending_count}")
    
    conn.close()

def view_chunk_progress():
    """查看块进度"""
    print("\n" + "=" * 80)
    print("块进度 (transfer_state) - 显示每个任务的前10个文件")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT task_id FROM transfer_state")
    task_ids = [row[0] for row in cursor.fetchall()]
    
    if not task_ids:
        print("没有找到块进度记录")
    else:
        for task_id in task_ids:
            print(f"\n任务ID: {task_id}")
            print("-" * 80)
            
            cursor.execute("""
                SELECT file_path, COUNT(*) as total_chunks, 
                       SUM(CASE WHEN received = 1 THEN 1 ELSE 0 END) as received_chunks
                FROM transfer_state
                WHERE task_id = ?
                GROUP BY file_path
                LIMIT 10
            """, (task_id,))
            
            rows = cursor.fetchall()
            
            for row in rows:
                file_path, total_chunks, received_chunks = row
                progress = (received_chunks / total_chunks * 100) if total_chunks > 0 else 0
                print(f"  {file_path}")
                print(f"        进度: {received_chunks}/{total_chunks} 块 ({progress:.1f}%)")
    
    conn.close()

if __name__ == "__main__":
    try:
        view_tasks()
        view_file_progress()
        view_chunk_progress()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
