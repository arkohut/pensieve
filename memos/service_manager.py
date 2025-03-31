import os
import sys
import time
import signal
import logging
import platform
import subprocess
import psutil
from pathlib import Path
from typing import Tuple, List, Dict, Optional

from .config import settings

# 1. PID文件管理
def get_pid_dir() -> Path:
    """返回PID文件目录"""
    pid_dir = settings.resolved_base_dir / "pids"
    pid_dir.mkdir(parents=True, exist_ok=True)
    return pid_dir

def get_pid_file(service_name: str) -> Path:
    """获取服务的PID文件路径"""
    return get_pid_dir() / f"{service_name}.pid"

def write_pid_file(service_name: str, pid: int = None) -> None:
    """写入PID文件"""
    pid = pid or os.getpid()
    with open(get_pid_file(service_name), "w") as f:
        f.write(str(pid))
    
def read_pid_file(service_name: str) -> Optional[int]:
    """读取PID文件，返回PID或None"""
    pid_file = get_pid_file(service_name)
    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None
    return None

def remove_pid_file(service_name: str) -> None:
    """删除PID文件"""
    pid_file = get_pid_file(service_name)
    if pid_file.exists():
        pid_file.unlink()

# 2. 进程管理和检测
def find_service_processes(service_name: str) -> List[psutil.Process]:
    """查找特定服务的所有进程"""
    return [
        p for p in psutil.process_iter(["pid", "name", "cmdline"])
        if p.info["cmdline"] is not None  # 确保cmdline不为None
        and "python" in p.info["name"].lower()
        and "memos.commands" in " ".join(p.info["cmdline"])
        and service_name in " ".join(p.info["cmdline"])
    ]

def is_service_running(service_name: str) -> Tuple[bool, Optional[int]]:
    """检查服务是否正在运行，返回(运行状态, PID)"""
    # 先通过psutil直接检查
    processes = find_service_processes(service_name)
    if processes:
        return True, processes[0].info["pid"]
    
    # 如果没找到进程，检查PID文件
    pid = read_pid_file(service_name)
    if pid:
        # 检查PID对应的进程是否存在，且是否是目标服务
        try:
            process = psutil.Process(pid)
            cmdline = " ".join(process.cmdline())
            if "python" in process.name().lower() and "memos.commands" in cmdline and service_name in cmdline:
                return True, pid
            else:
                # PID存在但不是目标服务，清理PID文件
                remove_pid_file(service_name)
        except psutil.NoSuchProcess:
            # 进程不存在，清理PID文件
            remove_pid_file(service_name)
    
    return False, None

def ensure_single_instance(service_name: str) -> Tuple[bool, Optional[str]]:
    """确保服务只有一个实例运行，返回(是否可以继续, 错误消息)"""
    running, pid = is_service_running(service_name)
    if running:
        return False, f"{service_name}服务已在运行 (PID: {pid})"
    
    # 写入PID文件（作为锁）
    write_pid_file(service_name)
    return True, None

# 3. 服务启动函数
def start_service(service_name: str, log_dir: Optional[Path] = None) -> bool:
    """启动指定的服务"""
    if service_name not in ["serve", "record", "watch"]:
        logging.error(f"未知服务: {service_name}")
        return False
    
    # 检查服务是否已运行
    running, pid = is_service_running(service_name)
    if running:
        logging.info(f"{service_name}服务已在运行 (PID: {pid})")
        return False
    
    # 准备日志目录
    if log_dir is None:
        log_dir = settings.resolved_base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{service_name}.log"
    
    # 获取Python路径
    python_path = sys.executable
    
    # 根据操作系统选择启动方式
    try:
        if platform.system() == "Windows":
            # Windows上使用pythonw以无窗口方式运行
            pythonw_path = python_path.replace("python.exe", "pythonw.exe")
            process = subprocess.Popen(
                [pythonw_path, "-m", "memos.commands", service_name],
                stdout=open(log_file, "a"),
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # macOS/Linux
            process = subprocess.Popen(
                [python_path, "-m", "memos.commands", service_name],
                stdout=open(log_file, "a"),
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
        
        logging.info(f"已启动{service_name}服务 (PID: {process.pid})")
        return True
    except Exception as e:
        logging.error(f"启动{service_name}服务失败: {e}")
        return False

# 4. 服务停止函数
def stop_service(service_name: str, timeout: int = 5) -> bool:
    """停止指定的服务，等待最多timeout秒"""
    running, pid = is_service_running(service_name)
    if not running:
        logging.info(f"{service_name}服务未运行")
        # 清理可能存在的PID文件
        remove_pid_file(service_name)
        return True
    
    try:
        # 发送SIGTERM信号
        os.kill(pid, signal.SIGTERM)
        logging.info(f"已发送SIGTERM到{service_name}服务 (PID: {pid})")
        
        # 等待进程终止
        wait_time = 0
        while is_service_running(service_name)[0] and wait_time < timeout:
            time.sleep(0.5)
            wait_time += 0.5
        
        # 如果进程仍在运行，发送SIGKILL
        if is_service_running(service_name)[0]:
            os.kill(pid, signal.SIGKILL)
            logging.info(f"已发送SIGKILL到{service_name}服务 (PID: {pid})")
            time.sleep(0.5)
        
        # 清理PID文件
        remove_pid_file(service_name)
        return True
    except Exception as e:
        logging.error(f"停止{service_name}服务失败: {e}")
        return False

# 5. 重启单个服务
def restart_service(service_name: str) -> bool:
    """重启单个服务"""
    if service_name == "serve":
        # 服务自举重启需要特殊处理
        return restart_serve_service()
    else:
        # 普通服务可以直接停止后启动
        stop_service(service_name)
        time.sleep(1)  # 确保完全停止
        return start_service(service_name)

# 6. 服务自举重启特殊处理
def restart_serve_service() -> bool:
    """特殊处理serve服务的自举重启"""
    # 检查serve是否在运行
    running, pid = is_service_running("serve")
    if not running:
        return start_service("serve")
    
    # 创建重启脚本
    script_path = sys.executable
    log_dir = settings.resolved_base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    restart_script = f"""
import time
import subprocess
import sys
import os
import logging

# 配置日志
logging.basicConfig(
    filename="{log_dir}/restart_serve.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

try:
    # 等待原服务终止
    logging.info("等待serve服务终止...")
    time.sleep(3)
    
    # 启动新服务
    logging.info("开始启动serve服务...")
    cmd = ["{script_path}", "-m", "memos.commands", "serve"]
    
    with open("{log_dir}/serve.log", "a") as log_file:
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            {"creationflags": subprocess.CREATE_NEW_CONSOLE} if sys.platform == "win32" else {{"start_new_session": True}}
        )
    
    logging.info(f"serve服务已启动，PID: {{process.pid}}")
except Exception as e:
    logging.error(f"重启serve服务失败: {{str(e)}}")
"""
    
    # 保存重启脚本
    script_file = log_dir / "restart_serve.py"
    with open(script_file, "w") as f:
        f.write(restart_script)
    
    # 启动独立进程执行重启脚本
    try:
        if platform.system() == "Windows":
            subprocess.Popen(
                [script_path, str(script_file)],
                creationflags=subprocess.DETACHED_PROCESS | 
                             subprocess.CREATE_NEW_PROCESS_GROUP |
                             subprocess.CREATE_NO_WINDOW
            )
        else:
            subprocess.Popen(
                [script_path, str(script_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        
        # 停止当前serve进程
        logging.info(f"准备停止当前serve服务 (PID: {pid})")
        stop_service("serve")
        return True
    except Exception as e:
        logging.error(f"创建重启进程失败: {e}")
        return False

# 7. 批量重启服务
def restart_processes(components: Dict[str, bool]) -> Dict[str, bool]:
    """重启多个服务，返回每个服务的重启结果"""
    results = {}
    
    # 处理非serve服务
    for service, should_restart in components.items():
        if service != "serve" and should_restart:
            results[service] = restart_service(service)
    
    # 最后处理serve服务
    if components.get("serve", False):
        results["serve"] = restart_serve_service()
    
    return results

# 8. 注册信号处理，用于服务入口函数
def register_service_signals(service_name: str) -> None:
    """为服务注册信号处理器"""
    def signal_handler(signum, frame):
        if signum in (signal.SIGTERM, signal.SIGINT):
            logging.info(f"收到信号{signum}，{service_name}服务正在优雅关闭...")
            # 清理PID文件
            remove_pid_file(service_name)
            sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

# 9. API安全重启函数
def api_restart_services(components: Dict[str, bool]) -> Dict[str, bool]:
    """用于API调用的安全重启函数"""
    results = {}
    
    # 检查是否需要重启serve服务
    restart_serve = components.get("serve", False)
    
    # 创建非serve组件的副本
    non_serve_components = {k: v for k, v in components.items() if k != "serve"}
    
    # 立即重启非serve组件
    if non_serve_components:
        for service, should_restart in non_serve_components.items():
            if should_restart:
                results[service] = restart_service(service)
    
    # 如果需要重启serve，创建延迟执行的后台任务
    if restart_serve:
        # 创建延迟重启脚本
        script_path = sys.executable
        log_dir = settings.resolved_base_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        restart_script = f"""
import time
import subprocess
import sys
import os
import logging

# 配置日志
logging.basicConfig(
    filename="{log_dir}/restart_api.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

try:
    # 短暂延迟确保API响应完成
    logging.info("等待API响应完成...")
    time.sleep(1)
    
    # 重启serve服务
    logging.info("开始重启serve服务...")
    # 导入服务管理模块
    sys.path.insert(0, "{Path(__file__).parent.parent}")
    from memos.service_manager import restart_serve_service
    restart_serve_service()
except Exception as e:
    logging.error(f"重启serve服务失败: {{str(e)}}")
"""
        
        # 保存重启脚本
        script_file = log_dir / "restart_api.py"
        with open(script_file, "w") as f:
            f.write(restart_script)
        
        # 启动独立进程执行重启
        try:
            if platform.system() == "Windows":
                subprocess.Popen(
                    [script_path, str(script_file)],
                    creationflags=subprocess.DETACHED_PROCESS | 
                                 subprocess.CREATE_NEW_PROCESS_GROUP |
                                 subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen(
                    [script_path, str(script_file)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            results["serve"] = True
        except Exception as e:
            logging.error(f"创建重启进程失败: {e}")
            results["serve"] = False
    
    return results
