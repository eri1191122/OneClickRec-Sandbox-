"""
汎用プロセス実行エンジン (Process Engine)
録画に限らず、あらゆる外部プロセスの実行・監視・制御を担当

設計原則:
- プラットフォーム非依存（TwitCasting等の単語は一切使用しない）
- 完全非同期対応
- 高い再利用性とテスタビリティ
"""
import asyncio
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
import signal
import os


class ProcessState(Enum):
    """プロセス状態"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class MonitorEventType(Enum):
    """監視イベントタイプ"""
    STARTED = "started"
    STDOUT_LINE = "stdout_line"
    STDERR_LINE = "stderr_line"
    PROGRESS = "progress"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class MonitorEvent:
    """監視イベント"""
    event_type: MonitorEventType
    timestamp: datetime
    session_id: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessRequest:
    """プロセス実行リクエスト"""
    command: List[str]
    working_directory: Optional[Path] = None
    environment: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None


@dataclass
class ProcessResult:
    """プロセス実行結果"""
    session_id: str
    state: ProcessState
    return_code: Optional[int]
    stdout: str
    stderr: str
    start_time: datetime
    end_time: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """実行時間（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def is_success(self) -> bool:
        """成功判定"""
        return self.state == ProcessState.COMPLETED and self.return_code == 0


class ProcessMonitor:
    """
    プロセス監視クラス
    stdout/stderr/プロセス状態をリアルタイム監視
    """
    
    def __init__(self):
        self.observers: List[Callable[[MonitorEvent], None]] = []
        self.is_monitoring = False
        self._monitor_tasks: List[asyncio.Task] = []
    
    def add_observer(self, observer: Callable[[MonitorEvent], None]):
        """監視者を追加"""
        self.observers.append(observer)
    
    def remove_observer(self, observer: Callable[[MonitorEvent], None]):
        """監視者を削除"""
        if observer in self.observers:
            self.observers.remove(observer)
    
    async def start_monitoring(self, 
                              session_id: str,
                              process: asyncio.subprocess.Process,
                              custom_parsers: List[Callable[[str], Optional[Dict[str, Any]]]] = None):
        """
        プロセス監視開始
        
        Args:
            session_id: セッションID
            process: 監視対象プロセス
            custom_parsers: カスタムログパーサー（プラットフォーム固有）
        """
        self.is_monitoring = True
        custom_parsers = custom_parsers or []
        
        # 開始イベント通知
        await self._notify_observers(MonitorEvent(
            event_type=MonitorEventType.STARTED,
            timestamp=datetime.now(),
            session_id=session_id,
            data={"pid": process.pid}
        ))
        
        # 並行監視タスク開始
        self._monitor_tasks = [
            asyncio.create_task(self._monitor_stdout(session_id, process, custom_parsers)),
            asyncio.create_task(self._monitor_stderr(session_id, process, custom_parsers)),
            asyncio.create_task(self._monitor_process_state(session_id, process))
        ]
    
    async def stop_monitoring(self):
        """監視停止"""
        self.is_monitoring = False
        
        # 全監視タスクをキャンセル
        for task in self._monitor_tasks:
            if not task.done():
                task.cancel()
        
        # タスク完了を待機
        if self._monitor_tasks:
            await asyncio.gather(*self._monitor_tasks, return_exceptions=True)
        
        self._monitor_tasks.clear()
    
    async def _monitor_stdout(self, 
                             session_id: str, 
                             process: asyncio.subprocess.Process,
                             custom_parsers: List[Callable]):
        """stdout監視"""
        if not process.stdout:
            return
        
        try:
            while self.is_monitoring and process.returncode is None:
                line = await process.stdout.readline()
                if not line:
                    break
                
                line_text = line.decode().strip()
                if not line_text:
                    continue
                
                # 基本イベント通知
                await self._notify_observers(MonitorEvent(
                    event_type=MonitorEventType.STDOUT_LINE,
                    timestamp=datetime.now(),
                    session_id=session_id,
                    data={"line": line_text}
                ))
                
                # カスタムパーサー実行（プラットフォーム固有処理）
                for parser in custom_parsers:
                    try:
                        parsed_data = parser(line_text)
                        if parsed_data:
                            await self._notify_observers(MonitorEvent(
                                event_type=MonitorEventType.PROGRESS,
                                timestamp=datetime.now(),
                                session_id=session_id,
                                data=parsed_data
                            ))
                    except Exception as e:
                        await self._notify_observers(MonitorEvent(
                            event_type=MonitorEventType.ERROR,
                            timestamp=datetime.now(),
                            session_id=session_id,
                            data={"parser_error": str(e)}
                        ))
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._notify_observers(MonitorEvent(
                event_type=MonitorEventType.ERROR,
                timestamp=datetime.now(),
                session_id=session_id,
                data={"stdout_monitor_error": str(e)}
            ))
    
    async def _monitor_stderr(self, 
                             session_id: str, 
                             process: asyncio.subprocess.Process,
                             custom_parsers: List[Callable]):
        """stderr監視"""
        if not process.stderr:
            return
        
        try:
            while self.is_monitoring and process.returncode is None:
                line = await process.stderr.readline()
                if not line:
                    break
                
                line_text = line.decode().strip()
                if not line_text:
                    continue
                
                await self._notify_observers(MonitorEvent(
                    event_type=MonitorEventType.STDERR_LINE,
                    timestamp=datetime.now(),
                    session_id=session_id,
                    data={"line": line_text}
                ))
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._notify_observers(MonitorEvent(
                event_type=MonitorEventType.ERROR,
                timestamp=datetime.now(),
                session_id=session_id,
                data={"stderr_monitor_error": str(e)}
            ))
    
    async def _monitor_process_state(self, session_id: str, process: asyncio.subprocess.Process):
        """プロセス状態監視"""
        try:
            while self.is_monitoring and process.returncode is None:
                await asyncio.sleep(0.5)
            
            # プロセス完了通知
            if process.returncode is not None:
                await self._notify_observers(MonitorEvent(
                    event_type=MonitorEventType.COMPLETED,
                    timestamp=datetime.now(),
                    session_id=session_id,
                    data={"return_code": process.returncode}
                ))
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._notify_observers(MonitorEvent(
                event_type=MonitorEventType.ERROR,
                timestamp=datetime.now(),
                session_id=session_id,
                data={"state_monitor_error": str(e)}
            ))
    
    async def _notify_observers(self, event: MonitorEvent):
        """監視者に通知"""
        for observer in self.observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event)
                else:
                    observer(event)
            except Exception as e:
                # Observer例外は無視（監視を継続）
                pass


class ProcessTerminator:
    """
    プロセス終了制御クラス
    段階的な安全終了を実現
    """
    
    @staticmethod
    async def terminate_gracefully(process: asyncio.subprocess.Process, 
                                  timeout_term: float = 5.0,
                                  timeout_kill: float = 3.0) -> bool:
        """
        段階的プロセス終了
        
        Args:
            process: 終了対象プロセス
            timeout_term: SIGTERM待機時間
            timeout_kill: SIGKILL待機時間
            
        Returns:
            bool: 終了成功かどうか
        """
        if process.returncode is not None:
            return True
        
        try:
            # ステップ1: 通常終了 (SIGTERM)
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout_term)
                return True
            except asyncio.TimeoutError:
                pass
            
            # ステップ2: 強制終了 (SIGKILL)
            process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout_kill)
                return True
            except asyncio.TimeoutError:
                pass
            
            # ステップ3: OS レベル強制終了
            try:
                if os.name == 'nt':  # Windows
                    subprocess.run(f"taskkill /F /PID {process.pid}", 
                                 shell=True, capture_output=True)
                else:  # Unix-like
                    os.kill(process.pid, signal.SIGKILL)
                return True
            except:
                return False
            
        except Exception:
            return False


class AsyncProcessEngine:
    """
    非同期プロセス実行エンジン
    汎用的なプロセス実行・監視・制御を提供
    """
    
    def __init__(self, max_concurrent: int = 5):
        """
        初期化
        
        Args:
            max_concurrent: 最大同時実行数
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.process_lock = asyncio.Lock()
        
        # 統計情報
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "active_count": 0
        }
    
    async def execute_process(self, 
                             request: ProcessRequest,
                             monitors: Optional[List[ProcessMonitor]] = None,
                             custom_parsers: Optional[List[Callable]] = None) -> ProcessResult:
        """
        プロセス実行（非同期）
        
        Args:
            request: プロセス実行リクエスト
            monitors: プロセス監視者リスト
            custom_parsers: カスタムログパーサー
            
        Returns:
            ProcessResult: 実行結果
        """
        session_id = self._generate_session_id()
        start_time = datetime.now()
        
        # 統計更新
        self.stats["total_executions"] += 1
        
        # 同時実行数制限
        async with self.semaphore:
            try:
                # プロセス開始
                process = await self._start_process(request)
                
                # プロセス登録
                async with self.process_lock:
                    self.active_processes[session_id] = process
                    self.stats["active_count"] += 1
                
                # 監視開始
                monitors = monitors or []
                for monitor in monitors:
                    await monitor.start_monitoring(session_id, process, custom_parsers)
                
                # プロセス完了待機（真の非ブロッキング）
                try:
                    if request.timeout:
                        await asyncio.wait_for(process.wait(), timeout=request.timeout)
                    else:
                        await process.wait()
                except asyncio.TimeoutError:
                    # タイムアウト時は強制終了
                    await ProcessTerminator.terminate_gracefully(process)
                
                # stdout/stderr取得
                stdout, stderr = "", ""
                try:
                    if process.stdout:
                        stdout_data = await process.stdout.read()
                        stdout = stdout_data.decode()
                    if process.stderr:
                        stderr_data = await process.stderr.read()
                        stderr = stderr_data.decode()
                except:
                    pass
                
                # 監視停止
                for monitor in monitors:
                    await monitor.stop_monitoring()
                
                # 結果作成
                end_time = datetime.now()
                state = ProcessState.COMPLETED if process.returncode == 0 else ProcessState.FAILED
                
                if state == ProcessState.COMPLETED:
                    self.stats["successful_executions"] += 1
                else:
                    self.stats["failed_executions"] += 1
                
                return ProcessResult(
                    session_id=session_id,
                    state=state,
                    return_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    start_time=start_time,
                    end_time=end_time,
                    metadata={
                        "command": " ".join(request.command),
                        "working_directory": str(request.working_directory) if request.working_directory else None
                    }
                )
                
            except Exception as e:
                self.stats["failed_executions"] += 1
                
                # 監視停止
                for monitor in monitors or []:
                    await monitor.stop_monitoring()
                
                return ProcessResult(
                    session_id=session_id,
                    state=ProcessState.FAILED,
                    return_code=None,
                    stdout="",
                    stderr=str(e),
                    start_time=start_time,
                    end_time=datetime.now(),
                    metadata={"exception": str(e)}
                )
            
            finally:
                # プロセス登録解除
                async with self.process_lock:
                    if session_id in self.active_processes:
                        del self.active_processes[session_id]
                        self.stats["active_count"] -= 1
    
    async def terminate_process(self, session_id: str) -> bool:
        """プロセス強制終了"""
        async with self.process_lock:
            if session_id in self.active_processes:
                process = self.active_processes[session_id]
                return await ProcessTerminator.terminate_gracefully(process)
            return False
    
    async def get_active_sessions(self) -> List[str]:
        """アクティブセッション一覧"""
        async with self.process_lock:
            return list(self.active_processes.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """統計情報取得"""
        return self.stats.copy()
    
    async def _start_process(self, request: ProcessRequest) -> asyncio.subprocess.Process:
        """プロセス開始"""
        return await asyncio.create_subprocess_exec(
            *request.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=request.working_directory,
            env=request.environment
        )
    
    def _generate_session_id(self) -> str:
        """セッションID生成"""
        return f"proc_{int(time.time() * 1000000)}"


# エクスポート
__all__ = [
    'ProcessState',
    'MonitorEventType', 
    'MonitorEvent',
    'ProcessRequest',
    'ProcessResult',
    'ProcessMonitor',
    'ProcessTerminator',
    'AsyncProcessEngine'
]