# monitor_logs.py
"""
Real-time log monitoring and analysis script for Kassia
Provides live log viewing, filtering, and analysis capabilities
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
from collections import defaultdict, deque

def parse_log_line(line: str) -> Optional[Dict]:
    """Parse a JSON log line."""
    try:
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None

class LogMonitor:
    """Real-time log monitor with filtering and analysis."""
    
    def __init__(self, log_file: Path, max_buffer_size: int = 1000):
        self.log_file = log_file
        self.max_buffer_size = max_buffer_size
        self.log_buffer = deque(maxlen=max_buffer_size)
        self.running = False
        self.filters = {}
        self.stats = defaultdict(int)
        
    def add_filter(self, key: str, value: str):
        """Add a filter for log entries."""
        self.filters[key] = value
    
    def clear_filters(self):
        """Clear all filters."""
        self.filters.clear()
    
    def matches_filters(self, log_entry: Dict) -> bool:
        """Check if log entry matches all filters."""
        for key, value in self.filters.items():
            if key not in log_entry:
                return False
            
            entry_value = str(log_entry[key]).lower()
            filter_value = value.lower()
            
            if filter_value not in entry_value:
                return False
        
        return True
    
    def format_log_entry(self, log_entry: Dict, colorize: bool = True) -> str:
        """Format log entry for display."""
        timestamp = log_entry.get('timestamp', '')[:19]  # Remove microseconds
        level = log_entry.get('level', 'INFO')
        category = log_entry.get('category', 'SYSTEM')
        component = log_entry.get('component', 'unknown')
        message = log_entry.get('message', '')
        job_id = log_entry.get('job_id', '')
        
        # Color codes for terminal
        colors = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
            'RESET': '\033[0m'      # Reset
        } if colorize else defaultdict(str)
        
        level_colored = f"{colors[level]}{level:8}{colors['RESET']}"
        category_colored = f"{colors.get(category, '')}{category:8}{colors['RESET']}"
        
        # Format job ID if present
        job_part = f"[{job_id[:8]}] " if job_id else ""
        
        # Build main line
        main_line = f"{timestamp} {level_colored} {category_colored} {component:15} {job_part}{message}"
        
        # Add details if present
        details = log_entry.get('details')
        if details and isinstance(details, dict):
            details_str = ", ".join([f"{k}={v}" for k, v in details.items() if k != 'exception'])
            if details_str:
                main_line += f"\n                                                     📋 {details_str}"
        
        # Add exception if present
        if details and 'exception' in details:
            exc_info = details['exception']
            exc_type = exc_info.get('type', 'Exception')
            exc_msg = exc_info.get('message', '')
            main_line += f"\n                                                     💥 {exc_type}: {exc_msg}"
        
        return main_line
    
    def update_stats(self, log_entry: Dict):
        """Update statistics."""
        self.stats['total_logs'] += 1
        self.stats[f"level_{log_entry.get('level', 'UNKNOWN')}"] += 1
        self.stats[f"category_{log_entry.get('category', 'UNKNOWN')}"] += 1
        
        if log_entry.get('job_id'):
            self.stats['with_job_id'] += 1
        
        if log_entry.get('details'):
            self.stats['with_details'] += 1
    
    def tail_logs(self, follow: bool = True, show_existing: bool = False):
        """Tail log file and display matching entries."""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                # Skip to end if not showing existing logs
                if not show_existing:
                    f.seek(0, 2)  # Seek to end
                
                self.running = True
                
                while self.running:
                    line = f.readline()
                    
                    if line:
                        log_entry = parse_log_line(line)
                        
                        if log_entry and self.matches_filters(log_entry):
                            formatted = self.format_log_entry(log_entry)
                            print(formatted)
                            
                            self.log_buffer.append(log_entry)
                            self.update_stats(log_entry)
                    
                    elif follow:
                        time.sleep(0.1)  # Brief pause when no new lines
                    else:
                        break
        
        except KeyboardInterrupt:
            self.running = False
        except FileNotFoundError:
            print(f"❌ Log file not found: {self.log_file}")
        except Exception as e:
            print(f"❌ Error reading log file: {e}")
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
    
    def print_stats(self):
        """Print current statistics."""
        print("\n📊 Log Statistics:")
        print(f"   Total logs processed: {self.stats['total_logs']}")
        print(f"   Logs with job ID: {self.stats['with_job_id']}")
        print(f"   Logs with details: {self.stats['with_details']}")
        
        # Level statistics
        print("\n📈 By Level:")
        for key, value in sorted(self.stats.items()):
            if key.startswith('level_'):
                level = key.replace('level_', '')
                print(f"   {level}: {value}")
        
        # Category statistics
        print("\n📂 By Category:")
        for key, value in sorted(self.stats.items()):
            if key.startswith('category_'):
                category = key.replace('category_', '')
                print(f"   {category}: {value}")

class LogAnalyzer:
    """Analyze log files for patterns and issues."""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.logs = []
    
    def load_logs(self, limit: Optional[int] = None):
        """Load logs from file."""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                if limit:
                    lines = lines[-limit:]  # Get last N lines
                
                for line in lines:
                    log_entry = parse_log_line(line)
                    if log_entry:
                        self.logs.append(log_entry)
            
            print(f"✅ Loaded {len(self.logs)} log entries")
            
        except FileNotFoundError:
            print(f"❌ Log file not found: {self.log_file}")
        except Exception as e:
            print(f"❌ Error loading logs: {e}")
    
    def analyze_errors(self):
        """Analyze error patterns."""
        print("\n🔍 Error Analysis:")
        
        errors = [log for log in self.logs if log.get('level') in ['ERROR', 'CRITICAL']]
        
        if not errors:
            print("   ✅ No errors found")
            return
        
        print(f"   Total errors: {len(errors)}")
        
        # Group by component
        error_by_component = defaultdict(list)
        for error in errors:
            component = error.get('component', 'unknown')
            error_by_component[component].append(error)
        
        print("\n   Errors by component:")
        for component, component_errors in sorted(error_by_component.items()):
            print(f"     {component}: {len(component_errors)}")
            
            # Show recent error
            recent_error = component_errors[-1]
            message = recent_error.get('message', '')[:60]
            timestamp = recent_error.get('timestamp', '')[:19]
            print(f"       Most recent: {timestamp} - {message}")
    
    def analyze_performance(self):
        """Analyze performance metrics."""
        print("\n⚡ Performance Analysis:")
        
        # Find operation logs
        operations = []
        for log in self.logs:
            details = log.get('details', {})
            if 'duration_seconds' in details:
                operations.append({
                    'operation': details.get('operation', 'unknown'),
                    'duration': details['duration_seconds'],
                    'timestamp': log.get('timestamp')
                })
        
        if not operations:
            print("   📊 No performance data found")
            return
        
        print(f"   Operations with timing: {len(operations)}")
        
        # Group by operation type
        op_times = defaultdict(list)
        for op in operations:
            op_times[op['operation']].append(op['duration'])
        
        print("\n   Average durations:")
        for operation, durations in sorted(op_times.items()):
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            print(f"     {operation}: {avg_duration:.2f}s avg, {max_duration:.2f}s max ({len(durations)} samples)")
    
    def analyze_jobs(self):
        """Analyze job-related logs."""
        print("\n👔 Job Analysis:")
        
        job_logs = [log for log in self.logs if log.get('job_id')]
        
        if not job_logs:
            print("   📋 No job logs found")
            return
        
        # Group by job ID
        jobs = defaultdict(list)
        for log in job_logs:
            job_id = log['job_id']
            jobs[job_id].append(log)
        
        print(f"   Jobs with logs: {len(jobs)}")
        
        # Analyze each job
        for job_id, job_log_entries in list(jobs.items())[:5]:  # Show first 5 jobs
            print(f"\n   Job: {job_id[:8]}...")
            print(f"     Log entries: {len(job_log_entries)}")
            
            # Find job duration if available
            start_log = next((log for log in job_log_entries 
                            if 'started' in log.get('message', '').lower()), None)
            end_log = next((log for log in job_log_entries 
                          if 'completed' in log.get('message', '').lower()), None)
            
            if start_log and end_log:
                try:
                    start_time = datetime.fromisoformat(start_log['timestamp'].replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(end_log['timestamp'].replace('Z', '+00:00'))
                    duration = (end_time - start_time).total_seconds()
                    print(f"     Duration: {duration:.1f} seconds")
                except:
                    pass
            
            # Check for errors
            job_errors = [log for log in job_log_entries if log.get('level') == 'ERROR']
            if job_errors:
                print(f"     ❌ Errors: {len(job_errors)}")
            else:
                print(f"     ✅ No errors detected")
    
    def analyze_timeline(self):
        """Analyze log timeline and patterns."""
        print("\n📅 Timeline Analysis:")
        
        if not self.logs:
            print("   📊 No logs to analyze")
            return
        
        # Parse timestamps
        timestamped_logs = []
        for log in self.logs:
            try:
                timestamp_str = log.get('timestamp', '')
                if timestamp_str:
                    # Handle both ISO format with and without timezone
                    if timestamp_str.endswith('Z'):
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    elif '+' in timestamp_str or timestamp_str.endswith(')'):
                        timestamp = datetime.fromisoformat(timestamp_str.split('+')[0])
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str)
                    
                    timestamped_logs.append((timestamp, log))
            except:
                continue
        
        if not timestamped_logs:
            print("   📊 No valid timestamps found")
            return
        
        # Sort by timestamp
        timestamped_logs.sort(key=lambda x: x[0])
        
        first_log = timestamped_logs[0][0]
        last_log = timestamped_logs[-1][0]
        duration = last_log - first_log
        
        print(f"   Time range: {first_log.strftime('%Y-%m-%d %H:%M:%S')} to {last_log.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Total duration: {duration}")
        print(f"   Log entries: {len(timestamped_logs)}")
        
        # Calculate log frequency
        if duration.total_seconds() > 0:
            logs_per_minute = len(timestamped_logs) / (duration.total_seconds() / 60)
            print(f"   Average frequency: {logs_per_minute:.1f} logs/minute")
        
        # Find busiest periods (group by hour)
        hourly_logs = defaultdict(int)
        for timestamp, log in timestamped_logs:
            hour_key = timestamp.strftime('%Y-%m-%d %H:00')
            hourly_logs[hour_key] += 1
        
        if hourly_logs:
            busiest_hour = max(hourly_logs.items(), key=lambda x: x[1])
            print(f"   Busiest hour: {busiest_hour[0]} ({busiest_hour[1]} logs)")
    
    def generate_summary_report(self):
        """Generate a comprehensive summary report."""
        print("\n📄 Summary Report:")
        print("=" * 60)
        
        # Basic statistics
        total_logs = len(self.logs)
        print(f"Total log entries: {total_logs}")
        
        if total_logs == 0:
            print("No logs to analyze")
            return
        
        # Count by level
        level_counts = defaultdict(int)
        category_counts = defaultdict(int)
        component_counts = defaultdict(int)
        
        for log in self.logs:
            level_counts[log.get('level', 'UNKNOWN')] += 1
            category_counts[log.get('category', 'UNKNOWN')] += 1
            component_counts[log.get('component', 'unknown')] += 1
        
        # Display level distribution
        print(f"\nLog Levels:")
        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            count = level_counts.get(level, 0)
            percentage = (count / total_logs) * 100
            print(f"  {level:8}: {count:5} ({percentage:5.1f}%)")
        
        # Display top categories
        print(f"\nTop Categories:")
        top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for category, count in top_categories:
            percentage = (count / total_logs) * 100
            print(f"  {category:12}: {count:5} ({percentage:5.1f}%)")
        
        # Display top components
        print(f"\nTop Components:")
        top_components = sorted(component_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for component, count in top_components:
            percentage = (count / total_logs) * 100
            print(f"  {component:20}: {count:5} ({percentage:5.1f}%)")
        
        # Error analysis
        errors = [log for log in self.logs if log.get('level') in ['ERROR', 'CRITICAL']]
        if errors:
            print(f"\nError Summary:")
            print(f"  Total errors: {len(errors)}")
            print(f"  Error rate: {(len(errors) / total_logs) * 100:.1f}%")
            
            # Recent errors
            print(f"\nRecent Errors:")
            for error in errors[-3:]:  # Last 3 errors
                timestamp = error.get('timestamp', '')[:19]
                message = error.get('message', '')[:50]
                component = error.get('component', 'unknown')
                print(f"  {timestamp} [{component}] {message}")
        
        print("=" * 60)

class InteractiveLogMonitor:
    """Interactive log monitor with command interface."""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.monitor = LogMonitor(log_file)
        self.analyzer = LogAnalyzer(log_file)
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Start monitoring in a separate thread."""
        if self.monitor_thread and self.monitor_thread.is_alive():
            print("⚠️  Monitoring already running")
            return
        
        print(f"🔄 Starting log monitoring: {self.log_file}")
        self.monitor_thread = threading.Thread(target=self.monitor.tail_logs, args=(True, False))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop monitoring."""
        if self.monitor_thread and self.monitor_thread.is_alive():
            print("⏹️  Stopping log monitoring...")
            self.monitor.stop()
            self.monitor_thread.join(timeout=2)
        
    def show_help(self):
        """Show available commands."""
        print("""
📖 Available Commands:
  start          - Start real-time monitoring
  stop           - Stop monitoring
  filter <key> <value> - Add filter (e.g., filter level ERROR)
  clearfilters   - Clear all filters
  stats          - Show current statistics
  analyze        - Run full log analysis
  errors         - Analyze errors only
  performance    - Analyze performance metrics
  jobs          - Analyze job-related logs
  timeline      - Analyze log timeline
  summary       - Generate summary report
  tail <n>      - Show last n log entries
  help          - Show this help
  quit          - Exit monitor

💡 Filter Examples:
  filter level ERROR      - Show only ERROR logs
  filter category WIM     - Show only WIM-related logs
  filter component dism   - Show only DISM component logs
  filter job_id abc123    - Show only logs for specific job
        """)
    
    def handle_command(self, command: str):
        """Handle interactive commands."""
        parts = command.strip().split()
        if not parts:
            return True
        
        cmd = parts[0].lower()
        
        if cmd == 'start':
            self.start_monitoring()
        
        elif cmd == 'stop':
            self.stop_monitoring()
        
        elif cmd == 'filter' and len(parts) >= 3:
            key = parts[1]
            value = ' '.join(parts[2:])
            self.monitor.add_filter(key, value)
            print(f"🔍 Added filter: {key} = {value}")
        
        elif cmd == 'clearfilters':
            self.monitor.clear_filters()
            print("🧹 Filters cleared")
        
        elif cmd == 'stats':
            self.monitor.print_stats()
        
        elif cmd == 'analyze':
            print("🔍 Loading logs for analysis...")
            self.analyzer.load_logs()
            self.analyzer.analyze_errors()
            self.analyzer.analyze_performance()
            self.analyzer.analyze_jobs()
            self.analyzer.analyze_timeline()
        
        elif cmd == 'errors':
            print("🔍 Analyzing errors...")
            self.analyzer.load_logs()
            self.analyzer.analyze_errors()
        
        elif cmd == 'performance':
            print("⚡ Analyzing performance...")
            self.analyzer.load_logs()
            self.analyzer.analyze_performance()
        
        elif cmd == 'jobs':
            print("👔 Analyzing jobs...")
            self.analyzer.load_logs()
            self.analyzer.analyze_jobs()
        
        elif cmd == 'timeline':
            print("📅 Analyzing timeline...")
            self.analyzer.load_logs()
            self.analyzer.analyze_timeline()
        
        elif cmd == 'summary':
            print("📄 Generating summary...")
            self.analyzer.load_logs()
            self.analyzer.generate_summary_report()
        
        elif cmd == 'tail' and len(parts) >= 2:
            try:
                n = int(parts[1])
                print(f"📄 Last {n} log entries:")
                self.analyzer.load_logs(limit=n)
                for log in self.analyzer.logs[-n:]:
                    formatted = self.monitor.format_log_entry(log)
                    print(formatted)
            except ValueError:
                print("❌ Invalid number for tail command")
        
        elif cmd == 'help':
            self.show_help()
        
        elif cmd in ['quit', 'exit', 'q']:
            return False
        
        else:
            print(f"❌ Unknown command: {cmd}. Type 'help' for available commands.")
        
        return True
    
    def run_interactive(self):
        """Run interactive monitor."""
        print("🚀 Kassia Log Monitor - Interactive Mode")
        print("Type 'help' for commands, 'quit' to exit")
        
        try:
            while True:
                try:
                    command = input("\nlogmonitor> ").strip()
                    if not self.handle_command(command):
                        break
                except KeyboardInterrupt:
                    print("\n\n👋 Exiting...")
                    break
                except EOFError:
                    break
        finally:
            self.stop_monitoring()

def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(
        description="Kassia Log Monitor - Real-time log analysis tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python monitor_logs.py                           # Interactive mode
  python monitor_logs.py --tail                    # Tail current logs
  python monitor_logs.py --analyze                 # Analyze existing logs
  python monitor_logs.py --filter level ERROR     # Monitor only errors
  python monitor_logs.py --file custom.log        # Use custom log file
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        type=Path,
        default=Path('runtime/logs/kassia.log'),
        help='Log file to monitor (default: runtime/logs/kassia.log)'
    )
    
    parser.add_argument(
        '--tail', '-t',
        action='store_true',
        help='Tail log file continuously'
    )
    
    parser.add_argument(
        '--analyze', '-a',
        action='store_true',
        help='Analyze existing logs and exit'
    )
    
    parser.add_argument(
        '--filter',
        nargs=2,
        metavar=('KEY', 'VALUE'),
        action='append',
        help='Add filter for monitoring (can be used multiple times)'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    
    parser.add_argument(
        '--show-existing',
        action='store_true',
        help='Show existing logs when tailing'
    )
    
    args = parser.parse_args()
    
    # Check if log file exists
    if not args.file.exists():
        print(f"❌ Log file not found: {args.file}")
        print("💡 Make sure Kassia has been run at least once to create logs")
        return 1
    
    # Create monitor
    if args.analyze:
        # Analysis mode
        print(f"🔍 Analyzing log file: {args.file}")
        analyzer = LogAnalyzer(args.file)
        analyzer.load_logs()
        analyzer.analyze_errors()
        analyzer.analyze_performance()
        analyzer.analyze_jobs()
        analyzer.analyze_timeline()
        analyzer.generate_summary_report()
        
    elif args.tail:
        # Tail mode
        print(f"📄 Tailing log file: {args.file}")
        print("Press Ctrl+C to stop...")
        
        monitor = LogMonitor(args.file)
        
        # Add filters if specified
        if args.filter:
            for key, value in args.filter:
                monitor.add_filter(key, value)
                print(f"🔍 Filter added: {key} = {value}")
        
        try:
            monitor.tail_logs(follow=True, show_existing=args.show_existing)
        except KeyboardInterrupt:
            print("\n\n📊 Final Statistics:")
            monitor.print_stats()
        
    else:
        # Interactive mode
        interactive_monitor = InteractiveLogMonitor(args.file)
        interactive_monitor.run_interactive()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
