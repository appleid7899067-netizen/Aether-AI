"""Task execution API.

All endpoints here execute *real* actions through the safe command registry,
script executor and file-operation helpers. Nothing is mocked.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional
import uuid
import json
import asyncio
from datetime import datetime

from src.api.schemas.tasks import (
    CreateTaskRequest,
    TaskResponse,
    TaskListResponse,
    TaskStatus,
    TaskType,
    TaskCancelRequest,
)
from src.utils.logger import get_logger
from src.action.automation.command_registry import get_command_registry
from src.action.automation.script_executor import SafeScriptExecutor
from src.action.automation.file_operations import SafeFileOperations

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

tasks_store: Dict[str, dict] = {}

# Global executors (module level so background tasks can reuse them)
registry = get_command_registry()
script_executor = SafeScriptExecutor()
file_ops = SafeFileOperations()

FILE_OPERATION_MAP = {
    "read": "read_file",
    "write": "create_file",
    "delete": "delete_file",
    "list": "list_files",
    "search": "search",
}

GUI_COMMAND_MAP = {
    "type": "type_text",
    "press": "press_key",
    "click_at": "click",
    "screenshot": "screenshot",
}


class TaskExecutor:
    """REAL task executor - actually executes commands instead of mocking."""

    @staticmethod
    def _start(task_id: str, kind: str, command: str):
        tasks_store[task_id]["status"] = TaskStatus.running
        tasks_store[task_id]["started_at"] = datetime.now()
        tasks_store[task_id].setdefault("logs", [])
        logger.info(f"[REAL EXECUTION] {kind} task {task_id}: {command}")

    @staticmethod
    def _log_callback(task_id: str):
        def log_callback(message: str):
            tasks_store[task_id].setdefault("logs", []).append(message)
        return log_callback

    @staticmethod
    def _finish(task_id: str, success: bool, result):
        tasks_store[task_id]["status"] = (
            TaskStatus.completed if success else TaskStatus.failed
        )
        tasks_store[task_id]["completed_at"] = datetime.now()
        tasks_store[task_id]["result"] = result

    @staticmethod
    def _fail(task_id: str, error: Exception):
        logger.error(f"[FAILED] Task {task_id} error: {error}")
        tasks_store[task_id]["status"] = TaskStatus.failed
        tasks_store[task_id]["completed_at"] = datetime.now()
        tasks_store[task_id]["error"] = str(error)

    @staticmethod
    async def execute_automation(task_id: str, command: str, parameters: dict):
        """Execute a desktop automation command through the command registry."""
        try:
            TaskExecutor._start(task_id, "Automation", command)
            log_callback = TaskExecutor._log_callback(task_id)

            if command.lower() == "open_app" and not parameters.get("app_name"):
                app_name = parameters.pop("app", None) or parameters.pop("name", None)
                if app_name:
                    parameters["app_name"] = app_name

            result = registry.execute_command(command, **parameters)
            log_callback(f"{command} -> {'ok' if result.success else 'failed'}")
            TaskExecutor._finish(task_id, result.success, result.to_dict())
            tasks_store[task_id]["error"] = result.error
        except Exception as e:  # noqa: BLE001
            TaskExecutor._fail(task_id, e)

    @staticmethod
    async def execute_script(task_id: str, command: str, parameters: dict):
        """Execute a real system script/command."""
        try:
            TaskExecutor._start(task_id, "Script", command)
            args = parameters.get("args", [])
            timeout = parameters.get("timeout", 30)
            log_callback = TaskExecutor._log_callback(task_id)

            execution_result = script_executor.execute_script(
                command, args=args, timeout=timeout, output_callback=log_callback
            )
            result = execution_result.to_dict()
            result["command"] = command
            TaskExecutor._finish(task_id, execution_result.success, result)
            tasks_store[task_id]["error"] = execution_result.error
        except Exception as e:  # noqa: BLE001
            TaskExecutor._fail(task_id, e)

    @staticmethod
    async def execute_gui_control(task_id: str, command: str, parameters: dict):
        """Execute a real GUI control action."""
        try:
            TaskExecutor._start(task_id, "GUI control", command)
            mapped_cmd = GUI_COMMAND_MAP.get(command.lower(), command)
            result = registry.execute_command(mapped_cmd, **parameters)
            TaskExecutor._finish(task_id, result.success, result.to_dict())
            tasks_store[task_id]["error"] = result.error
        except Exception as e:  # noqa: BLE001
            TaskExecutor._fail(task_id, e)

    @staticmethod
    async def execute_file_operation(task_id: str, command: str, parameters: dict):
        """Execute a real file operation."""
        try:
            TaskExecutor._start(task_id, "File operation", command)
            operation = FILE_OPERATION_MAP.get(command.lower(), command)

            if operation == "read_file":
                result = file_ops.read_file(parameters.get("path", ""))
            elif operation == "create_file":
                result = file_ops.write_file(
                    parameters.get("path", ""),
                    parameters.get("content", ""),
                    overwrite=parameters.get("overwrite", False),
                )
            elif operation == "delete_file":
                result = file_ops.delete_file(parameters.get("path", ""))
            elif operation == "list_files":
                result = file_ops.list_directory(
                    parameters.get("directory", "."), parameters.get("pattern", "*")
                )
            elif operation == "search":
                result = file_ops.search_files(
                    parameters.get("directory", "."),
                    parameters.get("pattern", "*"),
                    recursive=parameters.get("recursive", True),
                )
            else:
                raise ValueError(f"Unsupported file operation: {command}")

            TaskExecutor._finish(task_id, result.success, result.to_dict())
            tasks_store[task_id]["error"] = result.error
        except Exception as e:  # noqa: BLE001
            TaskExecutor._fail(task_id, e)

    @staticmethod
    async def execute_system_command(task_id: str, command: str, parameters: dict):
        """Execute a real system command."""
        try:
            TaskExecutor._start(task_id, "System command", command)
            args = parameters.get("args", [])
            timeout = parameters.get("timeout", 30)
            log_callback = TaskExecutor._log_callback(task_id)

            execution_result = script_executor.execute_command(
                command, args=args, timeout=timeout, output_callback=log_callback
            )
            result = execution_result.to_dict()
            result["command"] = command
            TaskExecutor._finish(task_id, execution_result.success, result)
            tasks_store[task_id]["error"] = execution_result.error
        except Exception as e:  # noqa: BLE001
            TaskExecutor._fail(task_id, e)


executor = TaskExecutor()

BACKGROUND_HANDLERS = {
    TaskType.automation: executor.execute_automation,
    TaskType.script: executor.execute_script,
    TaskType.gui_control: executor.execute_gui_control,
    TaskType.file_operation: executor.execute_file_operation,
    TaskType.system_command: executor.execute_system_command,
}


@router.post("/", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest, background_tasks: BackgroundTasks):
    try:
        task_id = str(uuid.uuid4())

        task_data = {
            "task_id": task_id,
            "task_type": request.task_type,
            "command": request.command,
            "status": TaskStatus.pending,
            "created_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "logs": [],
            "metadata": {
                "parameters": request.parameters or {},
                "timeout": request.timeout,
                "auto_approve": request.auto_approve,
            },
        }

        tasks_store[task_id] = task_data
        logger.info(f"Task {task_id} created ({request.task_type.value}): {request.command}")

        if request.auto_approve:
            await execute_task(task_id, background_tasks)

        return TaskResponse(**tasks_store[task_id])

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    page: int = 1,
    page_size: int = 20,
):
    try:
        filtered_tasks = list(tasks_store.values())

        if status:
            filtered_tasks = [t for t in filtered_tasks if t["status"] == status]

        if task_type:
            filtered_tasks = [t for t in filtered_tasks if t["task_type"] == task_type]

        filtered_tasks.sort(key=lambda x: x["created_at"], reverse=True)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_tasks = filtered_tasks[start_idx:end_idx]

        return TaskListResponse(
            tasks=[TaskResponse(**t) for t in paginated_tasks],
            total=len(filtered_tasks),
            page=page,
            page_size=page_size,
        )

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_task_stats():
    try:
        stats_by_status = {status: 0 for status in TaskStatus}
        stats_by_type = {task_type: 0 for task_type in TaskType}

        for task in tasks_store.values():
            stats_by_status[task["status"]] += 1
            stats_by_type[task["task_type"]] += 1

        return {
            "total_tasks": len(tasks_store),
            "by_status": {k.value: v for k, v in stats_by_status.items()},
            "by_type": {k.value: v for k, v in stats_by_type.items()},
        }

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting task stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskResponse(**tasks_store[task_id])


@router.post("/{task_id}/execute", response_model=TaskResponse)
async def execute_task(task_id: str, background_tasks: BackgroundTasks):
    try:
        if task_id not in tasks_store:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        task = tasks_store[task_id]

        if task["status"] != TaskStatus.pending:
            raise HTTPException(
                status_code=400,
                detail=f"Task is in {task['status']} state, cannot execute",
            )

        task_type = task["task_type"]
        command = task["command"]
        parameters = task["metadata"].get("parameters", {})
        if task["metadata"].get("timeout"):
            parameters.setdefault("timeout", task["metadata"]["timeout"])

        handler = BACKGROUND_HANDLERS.get(task_type)
        if handler is None:
            raise HTTPException(
                status_code=400, detail=f"Unsupported task type: {task_type}"
            )

        background_tasks.add_task(handler, task_id, command, parameters)

        return TaskResponse(**tasks_store[task_id])

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error executing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str, request: TaskCancelRequest):
    try:
        if task_id not in tasks_store:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        task = tasks_store[task_id]

        if task["status"] in [
            TaskStatus.completed,
            TaskStatus.failed,
            TaskStatus.cancelled,
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"Task is already in {task['status']} state",
            )

        tasks_store[task_id]["status"] = TaskStatus.cancelled
        tasks_store[task_id]["completed_at"] = datetime.now()
        tasks_store[task_id]["metadata"]["cancel_reason"] = request.reason

        logger.info(f"Task {task_id} cancelled: {request.reason}")

        return TaskResponse(**tasks_store[task_id])

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}/stream")
async def stream_task_events(task_id: str):
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        task = tasks_store[task_id]
        last_status = None
        last_log_idx = 0

        while True:
            current_status = task["status"]

            # Yield any new logs
            logs = task.get("logs", [])
            if len(logs) > last_log_idx:
                new_logs = logs[last_log_idx:]
                last_log_idx = len(logs)
                for log_line in new_logs:
                    yield f"data: {json.dumps({'type': 'log', 'content': log_line.strip()})}\n\n"

            # Yield status change
            if current_status != last_status:
                payload = {"type": "status", "status": current_status.value}

                # Only include result/error once done to avoid huge payloads
                if current_status in [
                    TaskStatus.completed,
                    TaskStatus.failed,
                    TaskStatus.cancelled,
                ]:
                    payload["result"] = task.get("result")
                    payload["error"] = task.get("error")

                yield f"data: {json.dumps(payload)}\n\n"
                last_status = current_status

            if current_status in [
                TaskStatus.completed,
                TaskStatus.failed,
                TaskStatus.cancelled,
            ]:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
