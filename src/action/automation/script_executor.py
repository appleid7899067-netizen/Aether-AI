import subprocess
import os
import sys
import tempfile
import time
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import threading
import queue

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ScriptExecutionResult:
    def __init__(
        self,
        success: bool,
        output: str = "",
        error: str = "",
        exit_code: int = 0,
        execution_time: float = 0.0,
        timeout: bool = False
    ):
        self.success = success
        self.output = output
        self.error = error
        self.exit_code = exit_code
        self.execution_time = execution_time
        self.timeout = timeout

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "timeout": self.timeout
        }

    def __repr__(self):
        return f"ScriptExecutionResult(success={self.success}, exit_code={self.exit_code}, time={self.execution_time:.2f}s)"


class ScriptExecutor:
    ALLOWED_EXTENSIONS = {'.py', '.bat', '.cmd', '.ps1', '.sh'}
    MAX_OUTPUT_SIZE = 10 * 1024 * 1024  # 10 MB
    
    def __init__(
        self,
        timeout: int = 30,
        max_output_size: int = MAX_OUTPUT_SIZE,
        working_directory: Optional[str] = None,
        allowed_commands: Optional[List[str]] = None
    ):
        self.timeout = timeout
        self.max_output_size = max_output_size
        self.working_directory = working_directory or os.getcwd()
        self.allowed_commands = allowed_commands or []
        
    def execute_script(
        self,
        script_path: str,
        args: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        output_callback: Optional[Callable[[str], None]] = None
    ) -> ScriptExecutionResult:
        timeout = timeout or self.timeout
        args = args or []
        
        script_path = Path(script_path).resolve()
        
        if not script_path.exists():
            return ScriptExecutionResult(
                success=False,
                error=f"Script not found: {script_path}"
            )
        
        if script_path.suffix not in self.ALLOWED_EXTENSIONS:
            return ScriptExecutionResult(
                success=False,
                error=f"Unsupported script type: {script_path.suffix}"
            )
        
        try:
            return self._execute_subprocess(
                self._build_command(script_path, args), [], env_vars, timeout, output_callback
            )
        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            return ScriptExecutionResult(
                success=False,
                error=str(e)
            )

    @staticmethod
    def _build_command(script_path: Path, args: List[str]):
        """Return the argv that runs ``script_path``.

        Scripts are launched through their interpreter instead of being executed
        directly - a plain ``.py``/``.sh`` file has no execute bit and no shebang
        when Aether writes it, which used to fail with "Permission denied".
        """
        suffix = script_path.suffix.lower()
        if suffix == ".py":
            return [sys.executable or "python", str(script_path), *args]
        if suffix == ".sh":
            if os.name == "nt":
                raise ValueError("Shell scripts (.sh) are not supported on Windows")
            return ["bash", str(script_path), *args]
        if suffix == ".ps1":
            shell = "powershell" if os.name == "nt" else "pwsh"
            return [shell, "-NoProfile", "-File", str(script_path), *args]
        if suffix in (".bat", ".cmd"):
            if os.name != "nt":
                raise ValueError(f"{suffix} scripts are only supported on Windows")
            return ["cmd.exe", "/c", str(script_path), *args]
        return [str(script_path), *args]
    
    def execute_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        output_callback: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ScriptExecutionResult:
        timeout = timeout or self.timeout
        args = args or []
        
        if self.allowed_commands and command not in self.allowed_commands:
            return ScriptExecutionResult(
                success=False,
                error=f"Command not allowed: {command}"
            )
        
        cmd_list = [command] + args
        
        try:
            return self._execute_subprocess(cmd_list, [], {}, timeout, output_callback, **kwargs)
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return ScriptExecutionResult(
                success=False,
                error=str(e)
            )
    
    def execute_python_code(
        self,
        code: str,
        timeout: Optional[int] = None,
        globals_dict: Optional[Dict[str, Any]] = None
    ) -> ScriptExecutionResult:
        timeout = timeout or self.timeout
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            result = self.execute_script(temp_file, timeout=timeout)
            return result
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def _execute_subprocess(
        self,
        command,
        args: List[str],
        env_vars: Optional[Dict[str, str]],
        timeout: int,
        output_callback: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> ScriptExecutionResult:
        start_time = time.time()
        
        shell = kwargs.get('shell', False)
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        if not shell:
            if isinstance(command, (str, Path)):
                cmd_name = str(command).lower()
                cmd_list = [str(command)] + args
            elif isinstance(command, list) and len(command) > 0:
                cmd_name = str(command[0]).lower()
                cmd_list = command
            else:
                cmd_name = ""
                cmd_list = command

            if os.name == 'nt' and cmd_name in ['echo', 'dir', 'type', 'copy', 'move', 'del', 'mkdir', 'rmdir']:
                cmd_list = ["cmd.exe", "/c"] + cmd_list
        else:
            cmd_list = command if isinstance(command, str) else " ".join(map(str, command))
        
        try:
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.working_directory,
                env=env,
                shell=shell,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output_lines = []
            
            def read_output():
                for line in iter(process.stdout.readline, ""):
                    output_lines.append(line)
                    if output_callback:
                        output_callback(line)
                process.stdout.close()
            
            reader_thread = threading.Thread(target=read_output)
            reader_thread.start()
            
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                reader_thread.join()
                
                return ScriptExecutionResult(
                    success=False,
                    output="".join(output_lines),
                    error=f"Command timed out after {timeout} seconds",
                    timeout=True,
                    execution_time=timeout
                )
            
            reader_thread.join()
            execution_time = time.time() - start_time
            
            stdout = "".join(output_lines)
            if len(stdout) > self.max_output_size:
                stdout = stdout[:self.max_output_size] + "\n... (output truncated)"
            
            success = process.returncode == 0
            
            return ScriptExecutionResult(
                success=success,
                output=stdout,
                error="" if success else "Command failed",
                exit_code=process.returncode,
                execution_time=execution_time,
                timeout=False
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Subprocess execution failed: {e}")
            return ScriptExecutionResult(
                success=False,
                error=str(e),
                exit_code=1,
                execution_time=execution_time
            )


class SafeScriptExecutor(ScriptExecutor):
    DANGEROUS_COMMANDS = {
        'rm', 'del', 'format', 'fdisk', 'mkfs', 'dd',
        'shutdown', 'reboot', 'init', 'halt',
        'chmod', 'chown', 'sudo', 'su'
    }
    
    SAFE_COMMANDS = {
        'echo', 'dir', 'ls', 'pwd', 'cd', 'type', 'cat',
        'whoami', 'hostname', 'date', 'time', 'systeminfo',
        'git', 'python', 'pip', 'npm', 'node'
    }
    
    def __init__(self, **kwargs):
        allowed_commands = kwargs.pop('allowed_commands', list(self.SAFE_COMMANDS))
        super().__init__(allowed_commands=allowed_commands, **kwargs)
    
    def execute_command(self, command: str, **kwargs) -> ScriptExecutionResult:
        base_command = command.split()[0].lower()
        
        if base_command in self.DANGEROUS_COMMANDS:
            logger.warning(f"Blocked dangerous command: {command}")
            return ScriptExecutionResult(
                success=False,
                error=f"Command '{base_command}' is not allowed for safety reasons"
            )
        
        return super().execute_command(command, **kwargs)
