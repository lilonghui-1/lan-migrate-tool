#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试日志工具
"""
import os
import time
import traceback
from datetime import datetime
from typing import Any

import config

def debug_log(message: str, level: str = "INFO", module: str = "unknown"):
    """
    记录调试日志
    
    Args:
        message: 日志消息
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        module: 模块名称
    """
    if not config.DEBUG:
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_line = f"[{timestamp}] [{level}] [{module}] {message}"
    
    # 打印到控制台
    print(log_line)
    
    # 写入日志文件
    try:
        with open(config.DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception as e:
        print(f"写入日志文件失败: {e}")

def debug_log_exception(exc: Exception, module: str = "unknown"):
    """
    记录异常日志
    
    Args:
        exc: 异常对象
        module: 模块名称
    """
    if not config.DEBUG:
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    exc_type = type(exc).__name__
    exc_msg = str(exc)
    
    log_line = f"[{timestamp}] [ERROR] [{module}] 异常: {exc_type}: {exc_msg}"
    print(log_line)
    
    # 获取堆栈信息
    stack_trace = traceback.format_exc()
    print(stack_trace)
    
    try:
        with open(config.DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
            f.write(stack_trace + "\n")
    except Exception as e:
        print(f"写入日志文件失败: {e}")

def debug_log_function(func):
    """
    装饰器：记录函数调用和返回
    """
    def wrapper(*args, **kwargs):
        if not config.DEBUG:
            return func(*args, **kwargs)
        
        module = func.__module__
        func_name = func.__name__
        
        # 记录函数调用
        args_str = str(args)[:100]
        kwargs_str = str(kwargs)[:100]
        debug_log(f"调用函数: {func_name}(args={args_str}, kwargs={kwargs_str})", 
                  level="DEBUG", module=module)
        
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            
            # 记录函数返回
            elapsed = time.time() - start_time
            result_str = str(result)[:100]
            debug_log(f"函数 {func_name} 完成，耗时: {elapsed:.3f}s, 返回: {result_str}", 
                      level="DEBUG", module=module)
            
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            debug_log(f"函数 {func_name} 异常，耗时: {elapsed:.3f}s", 
                      level="ERROR", module=module)
            debug_log_exception(e, module)
            raise
    
    return wrapper
