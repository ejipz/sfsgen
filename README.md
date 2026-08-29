# Synthetic Forensic Scenario Generator
A local REST API that deterministically generates synthetic digital forensics scenarios and serves as a backend component for systems that may use these scenarios for development, integration testing, demonstrations or automated testing of forensic-analysis workflows.

## Getting Started
### Prerequisites
Before running the service, ensure that the following dependencies are installed:
- FastAPI
- Uvicorn
- pytest

### Dependency Installation
Install the required dependencies by running the following command:
```shell
pip install -r requirements.txt
```

### Running the Service
Start the service using the following command:
```shell
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Running Automated Tests
Test the service using the following command:
```shell
pytest
```

## API Endpoints
### 1. `GET /health` 
Check whether the service is running.

**Response**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "status": "ok"
}
```

### 2. `POST /api/scenarios`
Create a new scenario.

**Valid Request**
```http
Content-Type: application/json

{
    "scenario": "credential_theft",
    "users": 1,
    "devices": 1,
    "events": 6,
    "seed": 42
}
```

**Successful Response**
```http
HTTP/1.1 202 Accepted
Content-Type: application/json
Location: /api/scenarios/1

{
    "id": 1,
    "status": "pending"
}
```

**Invalid Request**
```http
Content-Type: application/json

{
    "scenario": "credential_theft",
    "users": 0,
    "devices": 1,
    "events": 6,
    "seed": 42
}
```

**Error Response**
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
    "error": "invalid_configuration",
    "message": "users must be at least 1"
}
```

### 3. `GET /api/scenarios/{id}`
Retrieve a scenario by ID.  

**Valid Request**
```http
GET /api/scenarios/1
```

**Successful Response**  
**Running**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "id": 1,
    "status": "running"
}
```

**Completed**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "id": 1,
    "status": "completed",
    "scenario": {
        "users": [
            {
                "id": "user-001",
                "username": "alice",
                "role": "supervisor"
            }
        ],
        "devices": [
            {
                "id": "device-001",
                "hostname": "WORKSTATION-01",
                "os": "Windows"
            }
        ],
        "events": [
            {
                "id": "event-001",
                "type": "authentication",
                "timestamp": "2025-01-10T10:01:00Z",
                "actor_user_id": "user-001",
                "device_id": "device-001",
                "details": {
                    "source_ip": "10.0.15.24", 
                    "method": "sso",
                    "result": "success"
                }
            },
            {
                "id": "event-002",
                "type": "process_execution",
                "timestamp": "2025-01-10T10:05:00Z",
                "actor_user_id": "user-001",
                "device_id": "device-001",
                "details": {
                    "process_id": 34118,
                    "process_name": "zsh",
                    "parent_process": "explorer.exe",
                    "command": "certutil -decode payload.b64 payload.exe"
                }
            },
            {
                "id": "event-003",
                "type": "credential_access",
                "timestamp": "2025-01-10T10:09:00Z", 
                "actor_user_id": "user-001",
                "device_id": "device-001",
                "details": {
                    "method": "sam_registry_dump",
                    "process_name": "powershell.exe",
                    "target_process": "msedge.exe"
                }
            },
            {
                "id": "event-004",
                "type": "network_connection",
                "timestamp": "2025-01-10T10:16:00Z",
                "actor_user_id": "user-001",
                "device_id": "device-001",
                "details": {
                    "destination_ip": "203.0.113.57",
                    "destination_port": 22, 
                    "protocol": tcp,
                    "direction": "outbound",
                    "bytes_sent": 38718
                }
            },
            {
                "id": "event-005", 
                "type": "scheduled_task_created",
                "timestamp": "2025-01-10T10:21:00Z",
                "actor_user_id": "user-001",
                "device_id": "device-001",
                "details": {
                    "task_name": "System Health Check",
                    "trigger": "at_startup"
                }
            },
            {
                "id": "event-006",
                "type": "data_exfiltration",
                "timestamp": "2025-01-10T10:27:00Z",
                "actor_user_id": "user-001",
                "device_id": "device-001",
                "details": {
                    "destination_ip": "203.0.113.72",
                    "channel": "https",
                    "bytes_transferred": 15449461
                }
            }
        ]
    }
}
```

**Failed**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "id": 1,
    "status": "failed",
    "error": "generation failed"
}
```

**Invalid Request**
```http
GET /api/scenarios/291018
```

**Error Response**
```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{
    "error": "scenario_not_found",
    "message": "Scenario 291018 was not found"
}
```

## Data Model
![Entity Relationship Diagram](/images/erd.png)

## Design Decisions
### Deterministic Generation
A seed, provided as part of the scenario configuration, is used to initialise the random number generator. All random values used during scenario generation are derived from this generator so the same configuration and seed produce the same scenario.

### Asynchronous Generation
FastAPI's `BackgroundTasks` is used to run the scenario generation in the background. `BackgroundTasks` was chosen because it provides the required functionality without adding unnecessary complexity.

### Storage
A dictionary is used as it provides a simple way to store the generated data while the service is running.

## Limitations and Future Work
| Limitation | Future Work |
|---|---|
| Only one scenario type is supported | Implement more scenario types |
| Generated data is lost when the service restarts | Use databases like SQLite |
| Limited scalability of background processing | Introduce a task queue |