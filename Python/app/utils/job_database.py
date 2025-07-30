# app/utils/job_database.py - SQLite-kompatible Version
"""
Kassia Job Database Manager - SQLite Implementation (Fixed)
Speichert Jobs persistent zwischen App-Neustarts
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class JobDatabase:
    """SQLite Database für Job Persistierung - SQLite-kompatible Version"""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path("runtime/data/kassia_jobs.db")
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Database initialisieren
        self._init_database()
        logger.info(f"Job Database initialized: {self.db_path}")
    
    def _init_database(self):
        """Erstelle Tabellen falls sie nicht existieren - SQLite-kompatibel"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Jobs Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    device TEXT NOT NULL,
                    os_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'created',
                    progress INTEGER DEFAULT 0,
                    current_step TEXT,
                    step_number INTEGER DEFAULT 0,
                    total_steps INTEGER DEFAULT 9,
                    user_id TEXT DEFAULT 'web_user',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    skip_drivers BOOLEAN DEFAULT 0,
                    skip_updates BOOLEAN DEFAULT 0,
                    skip_validation BOOLEAN DEFAULT 0,
                    error TEXT,
                    results TEXT,
                    created_by TEXT DEFAULT 'webui',
                    version TEXT DEFAULT '2.0.0'
                )
            """)
            
            # Job Logs Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    component TEXT,
                    category TEXT,
                    details TEXT
                )
            """)
            
            # System Events Tabelle (für Audit Trail)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    user_id TEXT,
                    job_id TEXT
                )
            """)
            
            # Statistics Tabelle
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    total_jobs INTEGER DEFAULT 0,
                    completed_jobs INTEGER DEFAULT 0,
                    failed_jobs INTEGER DEFAULT 0,
                    avg_duration_seconds REAL
                )
            """)
            
            # Erstelle Indizes separat (SQLite-kompatibel)
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs (job_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_logs_timestamp ON job_logs (timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_events_timestamp ON system_events (timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_events_job_id ON system_events (job_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_statistics_date ON job_statistics (date)")
            except Exception as e:
                logger.warning(f"Could not create some indexes: {e}")
            
            conn.commit()
            logger.info("Database tables and indexes created/verified")
    
    @contextmanager
    def _get_connection(self):
        """Context manager für DB Verbindungen"""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row  # Dict-like access
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    # =================== JOB MANAGEMENT ===================
    
    def create_job(self, job_data: Dict[str, Any]) -> bool:
        """Erstelle neuen Job in der Datenbank"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Results als JSON string speichern
                results_json = json.dumps(job_data.get('results', {}))
                
                cursor.execute("""
                    INSERT INTO jobs (
                        id, device, os_id, status, progress, current_step, 
                        step_number, total_steps, user_id, created_at,
                        skip_drivers, skip_updates, skip_validation,
                        results, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_data['id'],
                    job_data['device'],
                    job_data['os_id'],
                    job_data['status'],
                    job_data.get('progress', 0),
                    job_data.get('current_step'),
                    job_data.get('step_number', 0),
                    job_data.get('total_steps', 9),
                    job_data.get('user_id', 'web_user'),
                    job_data['created_at'],
                    job_data.get('skip_drivers', False),
                    job_data.get('skip_updates', False),
                    job_data.get('skip_validation', False),
                    results_json,
                    job_data.get('created_by', 'webui')
                ))
                
                conn.commit()
                
                # System Event loggen
                self._log_system_event(conn, 'job_created', {
                    'job_id': job_data['id'],
                    'device': job_data['device'],
                    'os_id': job_data['os_id']
                }, job_data.get('user_id'))
                
                logger.info(f"Job created in database: {job_data['id']}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create job in database: {e}")
            return False
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Update Job in der Datenbank"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Build dynamic UPDATE query
                set_clauses = []
                values = []
                
                for key, value in updates.items():
                    if key == 'results':
                        set_clauses.append(f"{key} = ?")
                        values.append(json.dumps(value))
                    else:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)
                
                if not set_clauses:
                    return True  # Nothing to update
                
                values.append(job_id)  # For WHERE clause
                
                query = f"""
                    UPDATE jobs 
                    SET {', '.join(set_clauses)}
                    WHERE id = ?
                """
                
                cursor.execute(query, values)
                conn.commit()
                
                # Log wichtige Status-Änderungen
                if 'status' in updates:
                    self._log_system_event(conn, 'job_status_changed', {
                        'job_id': job_id,
                        'new_status': updates['status'],
                        'progress': updates.get('progress'),
                        'current_step': updates.get('current_step')
                    })
                
                logger.debug(f"Job updated in database: {job_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update job in database: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Hole einzelnen Job aus der Datenbank"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
                row = cursor.fetchone()
                
                if row:
                    job_dict = dict(row)
                    # Parse JSON results
                    if job_dict['results']:
                        try:
                            job_dict['results'] = json.loads(job_dict['results'])
                        except json.JSONDecodeError:
                            job_dict['results'] = {}
                    else:
                        job_dict['results'] = {}
                    
                    # Convert boolean fields
                    for bool_field in ['skip_drivers', 'skip_updates', 'skip_validation']:
                        job_dict[bool_field] = bool(job_dict[bool_field])
                    
                    return job_dict
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get job from database: {e}")
            return None
    
    def get_all_jobs(self, limit: int = None, status_filter: str = None) -> List[Dict[str, Any]]:
        """Hole alle Jobs aus der Datenbank"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM jobs"
                params = []
                
                if status_filter:
                    query += " WHERE status = ?"
                    params.append(status_filter)
                
                query += " ORDER BY created_at DESC"
                
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                jobs = []
                for row in rows:
                    job_dict = dict(row)
                    # Parse JSON results
                    if job_dict['results']:
                        try:
                            job_dict['results'] = json.loads(job_dict['results'])
                        except json.JSONDecodeError:
                            job_dict['results'] = {}
                    else:
                        job_dict['results'] = {}
                    
                    # Convert boolean fields
                    for bool_field in ['skip_drivers', 'skip_updates', 'skip_validation']:
                        job_dict[bool_field] = bool(job_dict[bool_field])
                    
                    jobs.append(job_dict)
                
                return jobs
                
        except Exception as e:
            logger.error(f"Failed to get jobs from database: {e}")
            return []
    
    def delete_job(self, job_id: str) -> bool:
        """Lösche Job aus der Datenbank"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Erst Job Logs löschen
                cursor.execute("DELETE FROM job_logs WHERE job_id = ?", (job_id,))
                
                # Job löschen
                cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
                
                conn.commit()
                
                self._log_system_event(conn, 'job_deleted', {'job_id': job_id})
                
                logger.info(f"Job deleted from database: {job_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete job from database: {e}")
            return False
    
    # =================== JOB LOGS ===================
    
    def add_job_log(self, job_id: str, timestamp: str, level: str, message: str, 
                   component: str = None, category: str = None, details: Dict = None) -> bool:
        """Füge Log-Eintrag für Job hinzu"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                details_json = json.dumps(details) if details else None
                
                cursor.execute("""
                    INSERT INTO job_logs (job_id, timestamp, level, message, component, category, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (job_id, timestamp, level, message, component, category, details_json))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to add job log: {e}")
            return False
    
    def get_job_logs(self, job_id: str, level_filter: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """Hole Job Logs aus der Datenbank"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM job_logs WHERE job_id = ?"
                params = [job_id]
                
                if level_filter:
                    query += " AND level = ?"
                    params.append(level_filter)
                
                query += " ORDER BY timestamp ASC"
                
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                logs = []
                for row in rows:
                    log_dict = dict(row)
                    # Parse JSON details
                    if log_dict['details']:
                        try:
                            log_dict['details'] = json.loads(log_dict['details'])
                        except json.JSONDecodeError:
                            log_dict['details'] = None
                    
                    logs.append(log_dict)
                
                return logs
                
        except Exception as e:
            logger.error(f"Failed to get job logs: {e}")
            return []
    
    # =================== STATISTICS ===================
    
    def update_daily_statistics(self):
        """Update tägliche Statistiken"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Berechne Statistiken für heute
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_jobs,
                        SUM(CASE WHEN status = 'failed' OR status = 'cancelled' THEN 1 ELSE 0 END) as failed_jobs,
                        AVG(
                            CASE 
                                WHEN completed_at IS NOT NULL AND started_at IS NOT NULL 
                                THEN (julianday(completed_at) - julianday(started_at)) * 86400
                                ELSE NULL 
                            END
                        ) as avg_duration_seconds
                    FROM jobs 
                    WHERE DATE(created_at) = ?
                """, (today,))
                
                stats = cursor.fetchone()
                
                # Insert or Replace
                cursor.execute("""
                    INSERT OR REPLACE INTO job_statistics 
                    (date, total_jobs, completed_jobs, failed_jobs, avg_duration_seconds)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    today,
                    stats['total_jobs'],
                    stats['completed_jobs'], 
                    stats['failed_jobs'],
                    stats['avg_duration_seconds']
                ))
                
                conn.commit()
                logger.info(f"Daily statistics updated for {today}")
                
        except Exception as e:
            logger.error(f"Failed to update daily statistics: {e}")
    
    def get_statistics(self, days: int = 30) -> List[Dict[str, Any]]:
        """Hole Statistiken der letzten N Tage"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM job_statistics 
                    WHERE date >= date('now', '-{} days')
                    ORDER BY date DESC
                """.format(days))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return []
    
    # =================== SYSTEM EVENTS ===================
    
    def _log_system_event(self, conn, event_type: str, event_data: Dict = None, user_id: str = None, job_id: str = None):
        """Logge System Event (internal method mit existing connection)"""
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO system_events (timestamp, event_type, event_data, user_id, job_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                event_type,
                json.dumps(event_data) if event_data else None,
                user_id,
                job_id
            ))
            
            # No commit here - will be handled by caller
                
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
    
    def get_system_events(self, limit: int = 100, event_type_filter: str = None) -> List[Dict[str, Any]]:
        """Hole System Events"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM system_events"
                params = []
                
                if event_type_filter:
                    query += " WHERE event_type = ?"
                    params.append(event_type_filter)
                
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                events = []
                for row in rows:
                    event_dict = dict(row)
                    if event_dict['event_data']:
                        try:
                            event_dict['event_data'] = json.loads(event_dict['event_data'])
                        except json.JSONDecodeError:
                            event_dict['event_data'] = None
                    events.append(event_dict)
                
                return events
                
        except Exception as e:
            logger.error(f"Failed to get system events: {e}")
            return []
    
    # =================== MAINTENANCE ===================
    
    def cleanup_old_data(self, days: int = 90):
        """Lösche alte Daten (Jobs älter als X Tage)"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Lösche alte Job Logs
                cursor.execute("""
                    DELETE FROM job_logs 
                    WHERE job_id IN (
                        SELECT id FROM jobs WHERE created_at < ?
                    )
                """, (cutoff_date,))
                
                # Lösche alte Jobs
                cursor.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff_date,))
                
                # Lösche alte System Events
                cursor.execute("DELETE FROM system_events WHERE timestamp < ?", (cutoff_date,))
                
                # Lösche alte Statistiken
                cursor.execute("""
                    DELETE FROM job_statistics 
                    WHERE date < date('now', '-{} days')
                """.format(days))
                
                conn.commit()
                
                logger.info(f"Cleaned up data older than {days} days")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    def get_database_info(self) -> Dict[str, Any]:
        """Hole Datenbank Informationen"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Table row counts
                cursor.execute("SELECT COUNT(*) FROM jobs")
                job_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM job_logs")
                log_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM system_events")
                event_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM job_statistics")
                stats_count = cursor.fetchone()[0]
                
                # Database file size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                
                return {
                    'database_path': str(self.db_path),
                    'database_size_bytes': db_size,
                    'database_size_mb': round(db_size / (1024 * 1024), 2),
                    'job_count': job_count,
                    'log_count': log_count,
                    'event_count': event_count,
                    'statistics_count': stats_count
                }
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {}


# Global database instance
_job_db = None

def get_job_database() -> JobDatabase:
    """Singleton für Job Database"""
    global _job_db
    if _job_db is None:
        _job_db = JobDatabase()
    return _job_db

def init_job_database(db_path: Path = None) -> JobDatabase:
    """Initialisiere Job Database"""
    global _job_db
    _job_db = JobDatabase(db_path)
    return _job_db