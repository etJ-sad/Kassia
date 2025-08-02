# app/utils/job_database.py - Fixed Database Cleanup Implementation

"""
Fixed Job Database System with Proper Cleanup Functions
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger("kassia.database")

class JobDatabase:
    """Enhanced Job Database with proper cleanup functionality."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with proper schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Jobs table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    device TEXT NOT NULL,
                    os_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    current_step TEXT,
                    step_number INTEGER DEFAULT 0,
                    total_steps INTEGER DEFAULT 9,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    error TEXT,
                    results TEXT,
                    user_id TEXT DEFAULT 'web_user',
                    skip_drivers BOOLEAN DEFAULT 0,
                    skip_updates BOOLEAN DEFAULT 0,
                    skip_validation BOOLEAN DEFAULT 0,
                    created_by TEXT DEFAULT 'webui'
                )
            ''')
            
            # Job logs table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS job_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    component TEXT DEFAULT 'webui',
                    category TEXT DEFAULT 'JOB',
                    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
                )
            ''')
            
            # Daily statistics table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_statistics (
                    date TEXT PRIMARY KEY,
                    total_jobs INTEGER DEFAULT 0,
                    completed_jobs INTEGER DEFAULT 0,
                    failed_jobs INTEGER DEFAULT 0,
                    cancelled_jobs INTEGER DEFAULT 0,
                    avg_duration_seconds REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # System events table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    timestamp TEXT NOT NULL,
                    user_id TEXT
                )
            ''')
            
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def create_job(self, job_data: Dict[str, Any]) -> bool:
        """Create a new job record."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Convert results dict to JSON string
                results_json = json.dumps(job_data.get('results', {}))
                
                conn.execute('''
                    INSERT INTO jobs (
                        id, device, os_id, status, progress, current_step, 
                        step_number, total_steps, created_at, started_at, 
                        completed_at, error, results, user_id, skip_drivers, 
                        skip_updates, skip_validation, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job_data['id'], job_data['device'], job_data['os_id'],
                    job_data['status'], job_data['progress'], job_data['current_step'],
                    job_data['step_number'], job_data['total_steps'], job_data['created_at'],
                    job_data.get('started_at'), job_data.get('completed_at'),
                    job_data.get('error'), results_json, job_data['user_id'],
                    job_data['skip_drivers'], job_data['skip_updates'],
                    job_data['skip_validation'], job_data['created_by']
                ))
                
                conn.commit()
                logger.info(f"Job {job_data['id']} created in database")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create job {job_data['id']}: {e}")
            return False

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing job record."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Build dynamic UPDATE query
                set_clauses = []
                values = []
                
                for key, value in updates.items():
                    if key == 'results' and isinstance(value, dict):
                        value = json.dumps(value)
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
                
                if not set_clauses:
                    return True  # No updates to apply
                
                values.append(job_id)  # For WHERE clause
                
                query = f"UPDATE jobs SET {', '.join(set_clauses)} WHERE id = ?"
                conn.execute(query, values)
                
                conn.commit()
                logger.debug(f"Job {job_id} updated in database")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a single job by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
                row = cursor.fetchone()
                
                if row:
                    job_dict = dict(row)
                    # Parse results JSON
                    if job_dict['results']:
                        try:
                            job_dict['results'] = json.loads(job_dict['results'])
                        except json.JSONDecodeError:
                            job_dict['results'] = {}
                    else:
                        job_dict['results'] = {}
                    
                    return job_dict
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None

    def get_all_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all jobs, newest first."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute('''
                    SELECT * FROM jobs 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
                
                jobs = []
                for row in cursor.fetchall():
                    job_dict = dict(row)
                    # Parse results JSON
                    if job_dict['results']:
                        try:
                            job_dict['results'] = json.loads(job_dict['results'])
                        except json.JSONDecodeError:
                            job_dict['results'] = {}
                    else:
                        job_dict['results'] = {}
                    
                    jobs.append(job_dict)
                
                return jobs
                
        except Exception as e:
            logger.error(f"Failed to get all jobs: {e}")
            return []

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and all its logs."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Delete job (logs will be deleted automatically due to CASCADE)
                cursor = conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Job {job_id} deleted from database")
                    return True
                else:
                    logger.warning(f"Job {job_id} not found for deletion")
                    return False
                
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False

    def add_job_log(self, job_id: str, timestamp: str, level: str, 
                   message: str, component: str = "webui", category: str = "JOB"):
        """Add a log entry for a job."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                conn.execute('''
                    INSERT INTO job_logs (job_id, timestamp, level, message, component, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (job_id, timestamp, level, message, component, category))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to add log for job {job_id}: {e}")

    def get_job_logs(self, job_id: str, level_filter: str = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get logs for a specific job."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if level_filter:
                    cursor = conn.execute('''
                        SELECT * FROM job_logs 
                        WHERE job_id = ? AND level = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ''', (job_id, level_filter, limit))
                else:
                    cursor = conn.execute('''
                        SELECT * FROM job_logs 
                        WHERE job_id = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    ''', (job_id, limit))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get logs for job {job_id}: {e}")
            return []

    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, int]:
        """
        FIXED: Properly delete old data from the database.
        
        Args:
            days_to_keep: Number of days to keep data for
            
        Returns:
            Dictionary with counts of deleted records
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_date_str = cutoff_date.isoformat()
        
        logger.info(f"Starting database cleanup: removing data older than {cutoff_date_str}")
        
        deleted_counts = {
            'jobs': 0,
            'logs': 0,
            'events': 0,
            'statistics': 0
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Delete old jobs (this will cascade to job_logs due to foreign key)
                cursor = conn.execute(
                    'DELETE FROM jobs WHERE created_at < ?', 
                    (cutoff_date_str,)
                )
                deleted_counts['jobs'] = cursor.rowcount
                logger.info(f"Deleted {deleted_counts['jobs']} old jobs")
                
                # Delete old system events
                cursor = conn.execute(
                    'DELETE FROM system_events WHERE timestamp < ?', 
                    (cutoff_date_str,)
                )
                deleted_counts['events'] = cursor.rowcount
                logger.info(f"Deleted {deleted_counts['events']} old system events")
                
                # Delete old statistics (keep last 365 days regardless)
                stats_cutoff = datetime.now() - timedelta(days=365)
                stats_cutoff_str = stats_cutoff.date().isoformat()
                
                cursor = conn.execute(
                    'DELETE FROM daily_statistics WHERE date < ?', 
                    (stats_cutoff_str,)
                )
                deleted_counts['statistics'] = cursor.rowcount
                logger.info(f"Deleted {deleted_counts['statistics']} old statistics")
                
                # Count remaining logs (should be automatically cleaned by CASCADE)
                cursor = conn.execute('SELECT COUNT(*) FROM job_logs')
                remaining_logs = cursor.fetchone()[0]
                
                # If there are orphaned logs (shouldn't happen with CASCADE), clean them manually
                cursor = conn.execute('''
                    DELETE FROM job_logs 
                    WHERE job_id NOT IN (SELECT id FROM jobs)
                ''')
                orphaned_logs = cursor.rowcount
                if orphaned_logs > 0:
                    logger.info(f"Cleaned up {orphaned_logs} orphaned log entries")
                
                deleted_counts['logs'] = orphaned_logs
                
                conn.commit()
                
                # VACUUM to reclaim space
                conn.execute('VACUUM')
                
                logger.info(f"Database cleanup completed: {deleted_counts}")
                
                # Log cleanup event
                self._log_system_event('database_cleanup', {
                    'cutoff_date': cutoff_date_str,
                    'days_kept': days_to_keep,
                    'deleted_counts': deleted_counts
                })
                
                return deleted_counts
                
        except Exception as e:
            logger.error(f"Database cleanup failed: {e}")
            raise e

    def get_database_info(self) -> Dict[str, Any]:
        """Get comprehensive database information."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                info = {
                    'database_path': str(self.db_path),
                    'database_size_bytes': 0,
                    'database_size_mb': 0,
                    'job_count': 0,
                    'log_count': 0,
                    'event_count': 0,
                    'statistics_count': 0,
                    'last_updated': datetime.now().isoformat()
                }
                
                # Get file size
                if self.db_path.exists():
                    size_bytes = self.db_path.stat().st_size
                    info['database_size_bytes'] = size_bytes
                    info['database_size_mb'] = round(size_bytes / (1024 * 1024), 2)
                
                # Count records in each table
                cursor = conn.execute('SELECT COUNT(*) FROM jobs')
                info['job_count'] = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM job_logs')
                info['log_count'] = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM system_events')
                info['event_count'] = cursor.fetchone()[0]
                
                cursor = conn.execute('SELECT COUNT(*) FROM daily_statistics')
                info['statistics_count'] = cursor.fetchone()[0]
                
                return info
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                'database_path': str(self.db_path),
                'database_size_bytes': 0,
                'database_size_mb': 0,
                'job_count': 0,
                'log_count': 0,
                'event_count': 0,
                'statistics_count': 0,
                'error': str(e)
            }

    def get_statistics(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily statistics for the last N days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cutoff_date = datetime.now() - timedelta(days=days)
                cutoff_date_str = cutoff_date.date().isoformat()
                
                cursor = conn.execute('''
                    SELECT * FROM daily_statistics 
                    WHERE date >= ?
                    ORDER BY date DESC
                ''', (cutoff_date_str,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return []

    def update_daily_statistics(self):
        """Update daily statistics from job data."""
        try:
            today = datetime.now().date().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                # Calculate today's statistics
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_jobs,
                        SUM(CASE WHEN status IN ('failed', 'cancelled') THEN 1 ELSE 0 END) as failed_jobs,
                        SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_jobs
                    FROM jobs 
                    WHERE DATE(created_at) = ?
                ''', (today,))
                
                row = cursor.fetchone()
                total_jobs = row[0]
                completed_jobs = row[1]
                failed_jobs = row[2]
                cancelled_jobs = row[3]
                
                # Calculate average duration for completed jobs
                avg_duration = None
                if completed_jobs > 0:
                    cursor = conn.execute('''
                        SELECT AVG(
                            (JULIANDAY(completed_at) - JULIANDAY(started_at)) * 24 * 3600
                        ) as avg_duration
                        FROM jobs 
                        WHERE DATE(created_at) = ? 
                        AND status = 'completed' 
                        AND started_at IS NOT NULL 
                        AND completed_at IS NOT NULL
                    ''', (today,))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        avg_duration = float(result[0])
                
                # Insert or update statistics
                now = datetime.now().isoformat()
                
                conn.execute('''
                    INSERT OR REPLACE INTO daily_statistics (
                        date, total_jobs, completed_jobs, failed_jobs, 
                        cancelled_jobs, avg_duration_seconds, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    today, total_jobs, completed_jobs, failed_jobs,
                    cancelled_jobs, avg_duration, now, now
                ))
                
                conn.commit()
                logger.info(f"Daily statistics updated for {today}")
                
        except Exception as e:
            logger.error(f"Failed to update daily statistics: {e}")

    def _log_system_event(self, event_type: str, event_data: Dict[str, Any], user_id: str = None):
        """Log a system event."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO system_events (event_type, event_data, timestamp, user_id)
                    VALUES (?, ?, ?, ?)
                ''', (
                    event_type, 
                    json.dumps(event_data), 
                    datetime.now().isoformat(), 
                    user_id
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")

# Global database instance
_job_database_instance = None

def init_job_database(db_path: Path) -> JobDatabase:
    """Initialize the global job database instance."""
    global _job_database_instance
    _job_database_instance = JobDatabase(db_path)
    return _job_database_instance

def get_job_database() -> JobDatabase:
    """Get the global job database instance."""
    if _job_database_instance is None:
        raise RuntimeError("Job database not initialized. Call init_job_database() first.")
    return _job_database_instance