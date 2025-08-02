# app/utils/logging.py
"""
Advanced Logging System for Kassia
Provides structured logging with WebUI integration, job tracking, and performance monitoring
"""

import logging
import json
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from collections import deque
import traceback
import uuid

class LogLevel(Enum):
    """Log levels for the system."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogCategory(Enum):
    """Categories for organizing logs."""
    SYSTEM = "SYSTEM"
    CONFIG = "CONFIG"
    ASSET = "ASSET"
    WIM = "WIM"
    DRIVER = "DRIVER"
    UPDATE = "UPDATE"
    WORKFLOW = "WORKFLOW"
    JOB = "JOB"
    API = "API"
    WEBUI = "WEBUI"
    ERROR = "ERROR"

class LogEntry:
    """Structured log entry."""
    
    def __init__(self, timestamp: str, level: str, category: str, component: str, 
                 message: str, details: Optional[Dict[str, Any]] = None, 
                 job_id: Optional[str] = None):
        self.timestamp = timestamp
        self.level = level
        self.category = category
        self.component = component
        self.message = message
        self.details = details or {}
        self.job_id = job_id
        self.id = str(uuid.uuid4())[:8]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            'id': self.id,
            'timestamp': self.timestamp,
            'level': self.level,
            'category': self.category,
            'component': self.component,
            'message': self.message
        }
        
        if self.details:
            result['details'] = self.details
        
        if self.job_id:
            result['job_id'] = self.job_id
        
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

class JobLogger:
    """Dedicated logger for individual jobs."""
    
    def __init__(self, job_id: str, log_dir: Path):
        self.job_id = job_id
        self.log_dir = log_dir
        self.log_file = log_dir / f"job_{job_id}.log"
        self.error_file = log_dir / f"job_{job_id}_errors.log"
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create dedicated loggers for this job
        self.logger = logging.getLogger(f"kassia.job.{job_id}")
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Main job log handler
        main_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(main_handler)
        
        # Error-only handler
        error_handler = logging.FileHandler(self.error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(error_handler)
        
        # Prevent propagation to root logger to avoid duplication
        self.logger.propagate = False
        
        # Write job start marker
        self.log_job_start()
    
    def log_job_start(self):
        """Log job initialization."""
        start_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO',
            'category': 'JOB',
            'component': f'job.{self.job_id}',
            'message': f'Job {self.job_id} logging started',
            'job_id': self.job_id,
            'details': {
                'log_file': str(self.log_file),
                'error_file': str(self.error_file),
                'session_start': datetime.now().isoformat()
            }
        }
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(start_entry, ensure_ascii=False, default=str) + '\n')
    
    def log_entry(self, level: str, category: str, component: str, message: str, details: Optional[Dict[str, Any]] = None):
        """Log entry to job-specific file."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'category': category,
            'component': component,
            'message': message,
            'job_id': self.job_id
        }
        
        if details:
            log_entry['details'] = details
        
        # Write to appropriate handler
        python_level = getattr(logging, level)
        record = self.logger.makeRecord(
            self.logger.name, python_level, "", 0, message, (), None
        )
        record.category = category
        record.details = details
        record.job_id = self.job_id
        
        self.logger.handle(record)
    
    def log_job_end(self, status: str = "completed", error_message: Optional[str] = None):
        """Log job completion."""
        end_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO' if status == 'completed' else 'ERROR',
            'category': 'JOB',
            'component': f'job.{self.job_id}',
            'message': f'Job {self.job_id} {status}',
            'job_id': self.job_id,
            'details': {
                'final_status': status,
                'session_end': datetime.now().isoformat()
            }
        }
        
        if error_message:
            end_entry['details']['error_message'] = error_message
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(end_entry, ensure_ascii=False, default=str) + '\n')
    
    def get_log_content(self) -> List[Dict[str, Any]]:
        """Get all log entries for this job."""
        entries = []
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return entries
    
    def get_error_content(self) -> List[Dict[str, Any]]:
        """Get error entries for this job."""
        entries = []
        try:
            with open(self.error_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return entries
    
    def cleanup(self, keep_logs: bool = True):
        """Cleanup job logger."""
        # Close handlers
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
        
        # Optionally remove log files
        if not keep_logs:
            try:
                if self.log_file.exists():
                    self.log_file.unlink()
                if self.error_file.exists():
                    self.error_file.unlink()
            except Exception:
                pass

class LogBuffer:
    """Thread-safe log buffer for WebUI integration."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.job_loggers: Dict[str, JobLogger] = {}
        self.log_dir = Path("runtime/logs")
    
    def add_entry(self, entry: LogEntry):
        """Add log entry to buffer."""
        with self.lock:
            self.buffer.append(entry)
            
            # Also log to job-specific file if job_id is present
            if entry.job_id:
                self._ensure_job_logger(entry.job_id)
                if entry.job_id in self.job_loggers:
                    self.job_loggers[entry.job_id].log_entry(
                        entry.level, entry.category, entry.component, 
                        entry.message, entry.details
                    )
    
    def _ensure_job_logger(self, job_id: str):
        """Ensure job logger exists for given job ID."""
        if job_id not in self.job_loggers:
            self.job_loggers[job_id] = JobLogger(job_id, self.log_dir)
    
    def create_job_logger(self, job_id: str) -> JobLogger:
        """Create and return a dedicated job logger."""
        with self.lock:
            if job_id not in self.job_loggers:
                self.job_loggers[job_id] = JobLogger(job_id, self.log_dir)
            return self.job_loggers[job_id]
    
    def get_job_logger(self, job_id: str) -> Optional[JobLogger]:
        """Get existing job logger."""
        with self.lock:
            return self.job_loggers.get(job_id)
    
    def finalize_job(self, job_id: str, status: str = "completed", error_message: Optional[str] = None):
        """Finalize job logging."""
        with self.lock:
            if job_id in self.job_loggers:
                self.job_loggers[job_id].log_job_end(status, error_message)
    
    def cleanup_job(self, job_id: str, keep_logs: bool = True):
        """Cleanup job logger."""
        with self.lock:
            if job_id in self.job_loggers:
                self.job_loggers[job_id].cleanup(keep_logs)
                del self.job_loggers[job_id]
    
    def get_job_log_file(self, job_id: str) -> Optional[Path]:
        """Get path to job log file."""
        if job_id in self.job_loggers:
            return self.job_loggers[job_id].log_file
        return self.log_dir / f"job_{job_id}.log"
    
    def get_job_error_file(self, job_id: str) -> Optional[Path]:
        """Get path to job error file."""
        if job_id in self.job_loggers:
            return self.job_loggers[job_id].error_file
        return self.log_dir / f"job_{job_id}_errors.log"
    
    def get_recent_logs(self, limit: Optional[int] = None) -> List[LogEntry]:
        """Get recent log entries."""
        with self.lock:
            if limit is None:
                return list(self.buffer)
            return list(self.buffer)[-limit:]
    
    def get_job_logs(self, job_id: str, limit: Optional[int] = None) -> List[LogEntry]:
        """Get logs for specific job."""
        with self.lock:
            job_logs = [entry for entry in self.buffer if entry.job_id == job_id]
            if limit is not None:
                job_logs = job_logs[-limit:]
            return job_logs
    
    def get_logs_by_level(self, level: str, limit: Optional[int] = None) -> List[LogEntry]:
        """Get logs by level."""
        with self.lock:
            level_logs = [entry for entry in self.buffer if entry.level == level]
            if limit is not None:
                level_logs = level_logs[-limit:]
            return level_logs
    
    def get_logs_by_category(self, category: str, limit: Optional[int] = None) -> List[LogEntry]:
        """Get logs by category."""
        with self.lock:
            category_logs = [entry for entry in self.buffer if entry.category == category]
            if limit is not None:
                category_logs = category_logs[-limit:]
            return category_logs
    
    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.buffer.clear()

class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def __init__(self):
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Get basic information
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'category': getattr(record, 'category', 'SYSTEM'),
            'component': record.name,
            'message': record.getMessage()
        }
        
        # Add details if present
        if hasattr(record, 'details') and record.details:
            log_entry['details'] = record.details
        
        # Add job ID if present
        if hasattr(record, 'job_id') and record.job_id:
            log_entry['job_id'] = record.job_id
        
        # Add exception information if present
        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            log_entry['details'] = log_entry.get('details', {})
            log_entry['details']['exception'] = {
                'type': exc_type.__name__ if exc_type else 'Exception',
                'message': str(exc_value),
                'traceback': traceback.format_exception(exc_type, exc_value, exc_traceback)
            }
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)

class ConsoleFormatter(logging.Formatter):
    """Custom formatter for console output with colors."""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def __init__(self):
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console."""
        # Get timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # Get color for level
        level_color = self.COLORS.get(record.levelname, '')
        reset_color = self.COLORS['RESET']
        
        # Format basic message
        category = getattr(record, 'category', 'SYSTEM')
        component = record.name.split('.')[-1]  # Get last part of component name
        
        # Build base message
        base_msg = f"{timestamp} {level_color}{record.levelname:8}{reset_color} {category:8} {component:15} {record.getMessage()}"
        
        # Add job ID if present
        if hasattr(record, 'job_id') and record.job_id:
            base_msg += f" [job:{record.job_id[:8]}]"
        
        # Add details if present
        if hasattr(record, 'details') and record.details:
            details_str = ", ".join([f"{k}={v}" for k, v in record.details.items() if k != 'exception'])
            if details_str:
                base_msg += f"\n                                                     📋 {details_str}"
        
        # Add exception if present
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            base_msg += f"\n                                                     💥 {exc_type.__name__}: {exc_value}"
        
        return base_msg

class KassiaLogger:
    """Enhanced logger with context and structured logging."""
    
    def __init__(self, name: str, python_logger: logging.Logger, log_buffer: Optional[LogBuffer] = None):
        self.name = name
        self.logger = python_logger
        self.log_buffer = log_buffer
        self.context = {}
    
    def set_context(self, **kwargs):
        """Set context for all subsequent log messages."""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear logging context."""
        self.context.clear()
    
    def _log(self, level: str, message: str, category: LogCategory, details: Optional[Dict[str, Any]] = None):
        """Internal logging method."""
        # Merge context with details
        final_details = {}
        final_details.update(self.context)
        if details:
            final_details.update(details)
        
        # Get job ID from context
        job_id = self.context.get('job_id')
        
        # Create log record
        python_level = getattr(logging, level)
        record = self.logger.makeRecord(
            self.logger.name, python_level, "", 0, message, (), None
        )
        
        # Add custom attributes
        record.category = category.value
        record.details = final_details if final_details else None
        record.job_id = job_id
        
        # Handle the log record
        self.logger.handle(record)
        
        # Add to buffer if available
        if self.log_buffer:
            log_entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created).isoformat(),
                level=level,
                category=category.value,
                component=self.name,
                message=message,
                details=final_details if final_details else None,
                job_id=job_id
            )
            self.log_buffer.add_entry(log_entry)
    
    def debug(self, message: str, category: LogCategory = LogCategory.SYSTEM, details: Optional[Dict[str, Any]] = None):
        """Log debug message."""
        self._log("DEBUG", message, category, details)
    
    def info(self, message: str, category: LogCategory = LogCategory.SYSTEM, details: Optional[Dict[str, Any]] = None):
        """Log info message."""
        self._log("INFO", message, category, details)
    
    def warning(self, message: str, category: LogCategory = LogCategory.SYSTEM, details: Optional[Dict[str, Any]] = None):
        """Log warning message."""
        self._log("WARNING", message, category, details)
    
    def error(self, message: str, category: LogCategory = LogCategory.ERROR, details: Optional[Dict[str, Any]] = None):
        """Log error message."""
        # Capture current exception if available
        import sys
        if sys.exc_info()[0] is not None:
            # Exception is active, include it
            record = self.logger.makeRecord(
                self.logger.name, logging.ERROR, "", 0, message, (), sys.exc_info()
            )
        else:
            record = self.logger.makeRecord(
                self.logger.name, logging.ERROR, "", 0, message, (), None
            )
        
        # Add custom attributes
        final_details = {}
        final_details.update(self.context)
        if details:
            final_details.update(details)
        
        record.category = category.value
        record.details = final_details if final_details else None
        record.job_id = self.context.get('job_id')
        
        # Handle the log record
        self.logger.handle(record)
        
        # Add to buffer if available
        if self.log_buffer:
            log_entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created).isoformat(),
                level="ERROR",
                category=category.value,
                component=self.name,
                message=message,
                details=final_details if final_details else None,
                job_id=self.context.get('job_id')
            )
            self.log_buffer.add_entry(log_entry)
    
    def critical(self, message: str, category: LogCategory = LogCategory.ERROR, details: Optional[Dict[str, Any]] = None):
        """Log critical message."""
        self._log("CRITICAL", message, category, details)
    
    def log_operation_start(self, operation: str):
        """Log the start of an operation."""
        self.info(f"Operation started: {operation}", LogCategory.WORKFLOW, {
            'operation': operation,
            'operation_status': 'started'
        })
    
    def log_operation_success(self, operation: str, duration: float, details: Optional[Dict[str, Any]] = None):
        """Log successful completion of an operation."""
        final_details = {
            'operation': operation,
            'operation_status': 'completed',
            'duration_seconds': round(duration, 3)
        }
        if details:
            final_details.update(details)
        
        self.info(f"Operation completed: {operation} ({duration:.3f}s)", LogCategory.WORKFLOW, final_details)
    
    def log_operation_failure(self, operation: str, error: str, duration: float, details: Optional[Dict[str, Any]] = None):
        """Log failed operation."""
        final_details = {
            'operation': operation,
            'operation_status': 'failed',
            'duration_seconds': round(duration, 3),
            'error_message': error
        }
        if details:
            final_details.update(details)
        
        self.error(f"Operation failed: {operation} ({duration:.3f}s) - {error}", LogCategory.ERROR, final_details)
    
    def create_job_context(self, job_id: str) -> 'JobContext':
        """Create a job context for enhanced logging."""
        return JobContext(self, job_id)

class JobContext:
    """Context manager for job-specific logging."""
    
    def __init__(self, logger: KassiaLogger, job_id: str):
        self.logger = logger
        self.job_id = job_id
        self.start_time = None
        self.original_context = {}
    
    def __enter__(self):
        """Enter job context."""
        # Save original context
        self.original_context = self.logger.context.copy()
        
        # Set job context
        self.logger.set_context(job_id=self.job_id)
        self.start_time = time.time()
        
        # Create job logger in buffer
        if self.logger.log_buffer:
            self.logger.log_buffer.create_job_logger(self.job_id)
        
        self.logger.info("Job context started", LogCategory.JOB, {
            'job_id': self.job_id,
            'context_start': datetime.now().isoformat()
        })
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit job context."""
        duration = time.time() - self.start_time if self.start_time else 0
        
        if exc_type:
            # Job failed
            self.logger.error(f"Job failed with {exc_type.__name__}", LogCategory.JOB, {
                'job_id': self.job_id,
                'duration_seconds': duration,
                'exception_type': exc_type.__name__,
                'exception_message': str(exc_val) if exc_val else None
            })
            
            # Finalize job with error
            if self.logger.log_buffer:
                self.logger.log_buffer.finalize_job(
                    self.job_id, "failed", 
                    f"{exc_type.__name__}: {exc_val}" if exc_val else str(exc_type)
                )
        else:
            # Job completed successfully
            self.logger.info("Job context completed", LogCategory.JOB, {
                'job_id': self.job_id,
                'duration_seconds': duration
            })
            
            # Finalize job successfully
            if self.logger.log_buffer:
                self.logger.log_buffer.finalize_job(self.job_id, "completed")
        
        # Restore original context
        self.logger.context = self.original_context

# Global state
_loggers: Dict[str, KassiaLogger] = {}
_log_buffer: Optional[LogBuffer] = None
_configured = False

def configure_logging(
    level: LogLevel = LogLevel.INFO,
    log_dir: Optional[Path] = None,
    enable_console: bool = True,
    enable_file: bool = True,
    enable_webui: bool = False
):
    """Configure the logging system."""
    global _log_buffer, _configured
    
    # Create log buffer if WebUI is enabled
    if enable_webui:
        _log_buffer = LogBuffer()
    
    # Convert custom level to Python logging level
    python_level = getattr(logging, level.value)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(python_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(python_level)
        console_handler.setFormatter(ConsoleFormatter())
        root_logger.addHandler(console_handler)
    
    # File handlers
    if enable_file and log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Main log file (all levels)
        main_log_file = log_dir / "kassia.log"
        main_handler = logging.FileHandler(main_log_file, encoding='utf-8')
        main_handler.setLevel(python_level)
        main_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(main_handler)
        
        # Error log file (errors only)
        error_log_file = log_dir / "kassia_errors.log"
        error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(error_handler)
    
    # Prevent duplicate logging
    root_logger.propagate = False
    
    _configured = True

def get_logger(name: str) -> KassiaLogger:
    """Get or create a logger instance."""
    if not _configured:
        # Auto-configure with basic settings
        configure_logging()
    
    if name not in _loggers:
        python_logger = logging.getLogger(name)
        _loggers[name] = KassiaLogger(name, python_logger, _log_buffer)
    
    return _loggers[name]

def get_log_buffer() -> Optional[LogBuffer]:
    """Get the log buffer for WebUI integration."""
    return _log_buffer

def get_job_logger(job_id: str) -> Optional[JobLogger]:
    """Get job-specific logger."""
    if _log_buffer:
        return _log_buffer.get_job_logger(job_id)
    return None

def create_job_logger(job_id: str) -> Optional[JobLogger]:
    """Create job-specific logger."""
    if _log_buffer:
        return _log_buffer.create_job_logger(job_id)
    return None

def finalize_job_logging(job_id: str, status: str = "completed", error_message: Optional[str] = None):
    """Finalize logging for a job."""
    if _log_buffer:
        _log_buffer.finalize_job(job_id, status, error_message)

def get_job_log_files(job_id: str) -> Dict[str, Optional[Path]]:
    """Get paths to job log files."""
    if _log_buffer:
        return {
            'main_log': _log_buffer.get_job_log_file(job_id),
            'error_log': _log_buffer.get_job_error_file(job_id)
        }
    return {'main_log': None, 'error_log': None}

def set_log_level(level: LogLevel):
    """Set the global log level."""
    python_level = getattr(logging, level.value)
    root_logger = logging.getLogger()
    root_logger.setLevel(python_level)
    
    # Update all handlers
    for handler in root_logger.handlers:
        handler.setLevel(python_level)

# Convenience functions
def debug(message: str, category: LogCategory = LogCategory.SYSTEM, details: Optional[Dict[str, Any]] = None):
    """Quick debug logging."""
    logger = get_logger("kassia.quick")
    logger.debug(message, category, details)

def info(message: str, category: LogCategory = LogCategory.SYSTEM, details: Optional[Dict[str, Any]] = None):
    """Quick info logging."""
    logger = get_logger("kassia.quick")
    logger.info(message, category, details)

def warning(message: str, category: LogCategory = LogCategory.SYSTEM, details: Optional[Dict[str, Any]] = None):
    """Quick warning logging."""
    logger = get_logger("kassia.quick")
    logger.warning(message, category, details)

def error(message: str, category: LogCategory = LogCategory.ERROR, details: Optional[Dict[str, Any]] = None):
    """Quick error logging."""
    logger = get_logger("kassia.quick")
    logger.error(message, category, details)

def critical(message: str, category: LogCategory = LogCategory.ERROR, details: Optional[Dict[str, Any]] = None):
    """Quick critical logging."""
    logger = get_logger("kassia.quick")
    logger.critical(message, category, details)