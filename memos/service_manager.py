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

# 1. PID File Management
def get_pid_dir() -> Path:
    """Returns the PID file directory"""
    pid_dir = settings.resolved_base_dir / "pids"
    pid_dir.mkdir(parents=True, exist_ok=True)
    return pid_dir

def get_pid_file(service_name: str) -> Path:
    """Gets the PID file path for a service"""
    return get_pid_dir() / f"{service_name}.pid"

def write_pid_file(service_name: str, pid: int = None) -> None:
    """Writes PID file"""
    pid = pid or os.getpid()
    with open(get_pid_file(service_name), "w") as f:
        f.write(str(pid))
    
def read_pid_file(service_name: str) -> Optional[int]:
    """Reads PID file, returns PID or None"""
    pid_file = get_pid_file(service_name)
    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None
    return None

def remove_pid_file(service_name: str) -> None:
    """Deletes PID file"""
    pid_file = get_pid_file(service_name)
    if pid_file.exists():
        pid_file.unlink()

# 2. Process Management and Detection
def find_service_processes(service_name: str) -> List[psutil.Process]:
    """Finds all processes for a specific service"""
    return [
        p for p in psutil.process_iter(["pid", "name", "cmdline"])
        if p.info["cmdline"] is not None  # Ensure cmdline is not None
        and "python" in p.info["name"].lower()
        and "memos.commands" in " ".join(p.info["cmdline"])
        and service_name in " ".join(p.info["cmdline"])
    ]

def is_service_running(service_name: str) -> Tuple[bool, Optional[int]]:
    """Checks if service is running, returns (running_status, PID)"""
    # First check PID file
    pid = read_pid_file(service_name)
    if pid:
        try:
            process = psutil.Process(pid)
            cmdline = " ".join(process.cmdline())
            if "python" in process.name().lower() and "memos.commands" in cmdline and service_name in cmdline:
                return True, pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Process doesn't exist or can't be accessed, clean up PID file
            remove_pid_file(service_name)
    
    # If PID file doesn't exist or is invalid, try finding through process list
    processes = find_service_processes(service_name)
    if processes:
        pid = processes[0].info["pid"]
        # After finding process, update PID file
        write_pid_file(service_name, pid)
        return True, pid
    
    return False, None

# 3. Service Start Function
def start_service(service_name: str, log_dir: Optional[Path] = None) -> bool:
    """Starts specified service"""
    if service_name not in ["serve", "record", "watch"]:
        logging.error(f"Unknown service: {service_name}")
        return False
    
    # Check if service is already running
    running, pid = is_service_running(service_name)
    if running:
        logging.info(f"Service {service_name} is already running (PID: {pid})")
        return False
    
    # Prepare log directory
    if log_dir is None:
        log_dir = settings.resolved_base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{service_name}.log"
    
    # Get Python path
    python_path = sys.executable
    
    try:
        # Choose startup method based on OS
        if platform.system() == "Windows":
            # On Windows, use pythonw for windowless execution
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
        
        # Write PID file after successful start
        write_pid_file(service_name, process.pid)
        logging.info(f"Started service {service_name} (PID: {process.pid})")
        return True
    except Exception as e:
        logging.error(f"Failed to start service {service_name}: {e}")
        return False

# 4. Service Stop Function
def stop_service(service_name: str, timeout: int = 5) -> bool:
    """Stops specified service, waits up to timeout seconds"""
    running, pid = is_service_running(service_name)
    if not running:
        logging.info(f"Service {service_name} is not running")
        # Clean up any existing PID file
        remove_pid_file(service_name)
        return True
    
    try:
        # Send SIGTERM signal
        os.kill(pid, signal.SIGTERM)
        logging.info(f"Sent SIGTERM to service {service_name} (PID: {pid})")
        
        # Wait for process termination
        wait_time = 0
        while is_service_running(service_name)[0] and wait_time < timeout:
            time.sleep(0.5)
            wait_time += 0.5
        
        # If process is still running, send SIGKILL
        if is_service_running(service_name)[0]:
            os.kill(pid, signal.SIGKILL)
            logging.info(f"Sent SIGKILL to service {service_name} (PID: {pid})")
            time.sleep(0.5)
        
        # Clean up PID file
        remove_pid_file(service_name)
        return True
    except Exception as e:
        logging.error(f"Failed to stop service {service_name}: {e}")
        return False

# 5. Restart Single Service
def restart_service(service_name: str) -> bool:
    """Restarts a single service"""
    if service_name == "serve":
        # Service bootstrap restart needs special handling
        return restart_serve_service()
    else:
        # Regular services can be stopped and started directly
        stop_service(service_name)
        time.sleep(1)  # Ensure complete stop
        return start_service(service_name)

# 6. Special Handling for Serve Service Bootstrap Restart
def restart_serve_service() -> bool:
    """Special handling for serve service bootstrap restart"""
    logging.info("Entering restart_serve_service")
    
    # Check if serve is running
    running, pid = is_service_running("serve")
    logging.info(f"Current serve service status - running: {running}, pid: {pid}")
    
    if not running:
        logging.info("No existing serve service found, starting new one")
        return start_service("serve")
    
    # Create restart script
    script_path = sys.executable
    log_dir = settings.resolved_base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    restart_script = f"""
import time
import subprocess
import sys
import os
import logging
import signal
from pathlib import Path

# Configure logging
logging.basicConfig(
    filename="{log_dir}/restart_serve.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def wait_for_process_exit(pid, timeout=5):
    import psutil
    start_time = time.time()
    try:
        while time.time() - start_time < timeout:
            if not psutil.pid_exists(pid):
                return True
            time.sleep(0.1)
        return False
    except Exception as e:
        logging.error(f"Error waiting for process exit: {{e}}")
        return False

try:
    logging.info(f"Restart script started with PID: {{os.getpid()}}")
    
    # Wait for original service to terminate
    logging.info(f"Waiting for serve service (PID: {pid}) to terminate...")
    if not wait_for_process_exit({pid}, timeout=5):
        logging.warning("Old service did not terminate in time")
    
    # Start new service
    logging.info("Starting serve service...")
    python_path = "{sys.executable}"
    cmd = [python_path, "-m", "memos.commands", "serve"]
    
    if sys.platform == "win32":
        pythonw_path = python_path.replace("python.exe", "pythonw.exe")
        with open("{log_dir}/serve.log", "a") as log_file:
            process = subprocess.Popen(
                [pythonw_path, "-m", "memos.commands", "serve"],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
    else:
        with open("{log_dir}/serve.log", "a") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
    
    logging.info(f"Serve service started, PID: {{process.pid}}")
    
    # Verify the new process
    time.sleep(1)
    if process.poll() is not None:
        logging.error("New serve process terminated immediately")
        raise Exception("Failed to start new serve process")
        
except Exception as e:
    logging.error(f"Failed to restart serve service: {{str(e)}}", exc_info=True)
    raise
"""
    
    # Save restart script
    script_file = log_dir / "restart_serve.py"
    with open(script_file, "w") as f:
        f.write(restart_script)
    
    # Start independent process to execute restart script
    try:
        if platform.system() == "Windows":
            pythonw_path = script_path.replace("python.exe", "pythonw.exe")
            process = subprocess.Popen(
                [pythonw_path, str(script_file)],
                stdout=open(log_dir / "restart_serve_launcher.log", "a"),
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            process = subprocess.Popen(
                [script_path, str(script_file)],
                stdout=open(log_dir / "restart_serve_launcher.log", "a"),
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
        
        logging.info(f"Started restart script process with PID: {process.pid}")
        
        # Stop current serve process
        logging.info(f"Preparing to stop current serve service (PID: {pid})")
        stop_result = stop_service("serve")
        logging.info(f"Stop service result: {stop_result}")
        
        return True
    except Exception as e:
        logging.error(f"Failed to create restart process: {e}", exc_info=True)
        return False

# 7. Batch Service Restart
def restart_processes(components: Dict[str, bool]) -> Dict[str, bool]:
    """Restarts multiple services, returns restart results for each service"""
    results = {}
    
    # Handle non-serve services
    for service, should_restart in components.items():
        if service != "serve" and should_restart:
            results[service] = restart_service(service)
    
    # Handle serve service last
    if components.get("serve", False):
        results["serve"] = restart_serve_service()
    
    return results

# 8. Register Signal Handlers for Service Entry Points
def register_service_signals(service_name: str) -> None:
    """Registers signal handlers for service"""
    def signal_handler(signum, frame):
        if signum in (signal.SIGTERM, signal.SIGINT):
            logging.info(f"Received signal {signum}, service {service_name} is gracefully shutting down...")
            # Clean up PID file
            remove_pid_file(service_name)
            sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

# 9. API Safe Restart Function
def api_restart_services(components: Dict[str, bool]) -> Dict[str, bool]:
    """Provides safe restart function for API calls"""
    results = {}
    logging.info(f"API restart requested for components: {components}")
    
    # 1. Handle non-serve components first (immediate restart)
    for service, should_restart in components.items():
        if service != "serve" and should_restart:
            logging.info(f"Restarting {service} service")
            results[service] = restart_service(service)
            logging.info(f"{service} restart result: {results[service]}")
    
    # 2. Special handling for serve component (delayed restart)
    if components.get("serve", False):
        # Create delayed restart script
        script_path = sys.executable
        log_dir = settings.resolved_base_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        restart_script = f"""
import time
import sys
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    filename="{log_dir}/restart_api.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

try:
    logging.info(f"Restart API script started with PID: {{os.getpid()}}")
    
    # Delay to ensure API response completes
    logging.info("Waiting for API response to complete...")
    time.sleep(2)
    
    # Import and call restart function
    memos_path = "{Path(__file__).parent.parent.absolute()}"
    logging.info(f"Adding to Python path: {{memos_path}}")
    sys.path.insert(0, memos_path)
    
    from memos.service_manager import restart_serve_service, is_service_running
    
    # Check old service status
    running, pid = is_service_running("serve")
    logging.info(f"Current serve service status - running: {{running}}, pid: {{pid}}")
    
    # Attempt restart
    logging.info("Starting serve service restart")
    result = restart_serve_service()
    logging.info(f"Restart result: {{result}}")
    
    # Verify new service status
    time.sleep(2)
    running, new_pid = is_service_running("serve")
    logging.info(f"New serve service status - running: {{running}}, pid: {{new_pid}}")
    
except Exception as e:
    logging.error(f"Failed to restart serve service: {{str(e)}}", exc_info=True)
    raise
"""
        
        # Save restart script
        script_file = log_dir / "restart_api.py"
        with open(script_file, "w") as f:
            f.write(restart_script)
        
        try:
            if platform.system() == "Windows":
                pythonw_path = script_path.replace("python.exe", "pythonw.exe")
                process = subprocess.Popen(
                    [pythonw_path, str(script_file)],
                    stdout=open(log_dir / "restart_api_launcher.log", "a"),
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                process = subprocess.Popen(
                    [script_path, str(script_file)],
                    stdout=open(log_dir / "restart_api_launcher.log", "a"),
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
            
            logging.info(f"Started API restart script with PID: {process.pid}")
            results["serve"] = True
        except Exception as e:
            logging.error(f"Failed to create restart process: {e}", exc_info=True)
            results["serve"] = False
    
    return results
