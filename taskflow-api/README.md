# TaskFlow API

A lightweight RESTful Task Management API microservice.

## Architecture
- `src/auth/service.py`: Authentication, JWT verification, session handling.
- `src/tasks/service.py`: Task management, status updates, owner filtering.
- `src/database/connection.py`: SQLite connection pool and schema migrations.
- `src/api/routes.py`: HTTP routes and payload dispatchers.
