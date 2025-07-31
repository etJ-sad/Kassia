# Logging & Database

Logging utilities are implemented in `app.utils.logging`. Structured log entries are written to JSON files and mirrored in an in‑memory buffer used by the WebUI. Each build job receives a dedicated log file.

Job and statistics data are stored in an SQLite database managed by `app.utils.job_database`. The database initialisation logic can be seen in `JobDatabase._init_database()`.
