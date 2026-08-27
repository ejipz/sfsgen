import random
import threading
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse

app = FastAPI(title="Synthetic Forensic Scenario Generator")

scenarios = {}
lock = threading.Lock()

def update_scenario(scenario_id, **fields):
    with lock:
        if scenario_id in scenarios:
            scenarios[scenario_id].update(fields)

# deterministic generator
USERNAMES = ["alice", "junjie", "jayden", "kayden", "ayden", "eden", "hayden", "melvin", "kelvin", "alvin", 
"elvin", "xavier", "javier", "yiting", "ethan", "honey", "batman", "suparman", "jeff", "sumtingwong"]
ROLES = ["employee", "administrator", "supervisor"]
OS = ["Windows", "macOS", "Linux"]
HOSTNAMES = ["WORKSTATION", "SERVER", "DESKTOP"]
AC_EVENTS = ["authentication", "process_execution", "credential_access", "network_connection", "data_exfiltration"]
BG_EVENTS = ["login_attempt", "file_access", "registry_modification", "scheduled_task_created"]
TIME = datetime(2025, 1, 10, 10, 0, 0, tzinfo=timezone.utc) # predefined

def generate_users(rng, n):
    users = []
    for i in range(n):
        username = USERNAMES[i % len(USERNAMES)]
        users.append({
            "id": f"user-{i + 1:03d}",
            "username": username,
            "role": rng.choice(ROLES)
        })
    return users

def generate_devices(rng, n):
    devices = []
    for i in range(n):
        devices.append({
            "id": f"device-{i + 1:03d}",
            "hostname": f"{rng.choice(HOSTNAMES)}-{i + 1:02d}",
            "os": rng.choice(OS)
        })
    return devices

def generate_ac_events(type, rng):
    if type == "authentication":
        return {
            "result": "success",
            "method": rng.choice(["password", "sso"]),
            "source_ip": f"10.0.{rng.randint(0, 255)}.{rng.randint(1, 254)}"
        }
    if type == "process_execution":
        return {
            "process_name": rng.choice(["powershell.exe", "cmd.exe", "bash"]),
            "command": rng.choice([
                "powershell -enc <base64>",
                "whoami /all",
            ])
        }
    if type == "credential_access":
        return {"method": rng.choice(["browser_credential_store", "lsass_dump", "sam_registry_dump"])}
    if type == "network_connection":
        return {
            "destination_ip": f"203.0.113.{rng.randint(1, 254)}",
            "destination_port": rng.choice([443, 8443, 4444]),
            "protocol": "tcp"
        }
    if type == "data_exfiltration":
        return {
            "destination_ip": f"203.0.113.{rng.randint(1, 254)}",
            "bytes_transferred": rng.randint(1000000, 50000000),
            "channel": rng.choice(["https", "dns_tunnel", "ftp"])
        }
    return {}

def generate_bg_events(type, rng):
    if type == "login_attempt":
        return {"result": rng.choice(["sucess", "failure"])}
    if type == "file_access":
        return {
            "path": rng.choice(["/etc/passwd", "/etc/shadow"]),
            "action": rng.choice(["read", "write"])
        }
    if type == "registry_modification":
        return {"key": "HKLM\\Software\\Example"}
    if type == "scheduled_task_created":
        return {"task_name": "UpdaterTask"}
    return {}

def generate_credential_theft_scenario(num_users, num_devices, num_events, seed):
    rng = random.Random(seed)

    users = generate_users(rng, num_users)
    devices = generate_devices(rng, num_devices)

    # for attack chain events
    main_user = rng.choice(users)
    main_device = rng.choice(devices)

    positions = list(range(num_events))
    ac_positions = sorted(rng.sample(positions, len(AC_EVENTS)))
    bg_positions = [p for p in positions if p not in ac_positions]

    slots = {}
    for pos, type in zip(ac_positions, AC_EVENTS):
        slots[pos] = ("ac", type)

    for pos in bg_positions:
        slots[pos] = ("bg", rng.choice(BG_EVENTS))

    time = TIME
    events = []

    for pos in range(num_events):
        kind, type = slots[pos]
        time = time + timedelta(minutes=rng.randint(1, 10))

        if kind == "ac":
            actor = main_user
            device = main_device
            details = generate_ac_events(type, rng)
        else:
            actor = rng.choice(users)
            device = rng.choice(devices)
            details = generate_bg_events(type, rng)

        events.append({
            "id": f"event-{pos + 1:03d}",
            "type": type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actor_user_id": actor["id"],
            "device_id": device["id"],
            "details": details
        })

    return {"users": users, "devices": devices, "events": events}    

# functions
def error_response(code, err, msg):
    return JSONResponse(status_code=code, content={"error": err, "message": msg})

def validate_config(body):
    if not isinstance(body, dict):
        raise ValueError("request body must be a JSON object")

    # missing fields
    required = ["scenario", "users", "devices", "events", "seed"]
    missing = [f for f in required if f not in body]
    if missing: 
        raise ValueError(f"missing required field(s): {', '.join(missing)}")

    # unsupported scenario types
    scenario = body["scenario"]
    if not isinstance(scenario, str) or scenario != "credential_theft":
        raise ValueError(f"unsupported scenario type: {scenario}")

    # check int type and value
    def check_int(name, min_value = None):
        value = body[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
        if min_value is not None and value < min_value:
            raise ValueError(f"{name} must be at least {min_value}")
        return value

    users = check_int("users", 1)
    devices = check_int("devices", 1)
    events = check_int("events", 5)
    seed = check_int("seed")

    # return validated obj
    return {"scenario": scenario, "users": users, "devices": devices, "events": events, "seed": seed}

def generate_scenario(scenario_id, config):
    update_scenario(scenario_id, status="running")

    try:
        data = generate_credential_theft_scenario(
            num_users = config["users"],
            num_devices = config["devices"],
            num_events = config["events"],
            seed = config["seed"]
        )
        update_scenario(scenario_id, status="completed", scenario=data)
    except Exception as exc:
        update_scenario(scenario_id, status="failed", error=str(exc))

# routes
# health check
@app.get("/health")
async def get_health():
    return {"status": "ok"}

# create scenario
@app.post("/api/scenarios")
async def create_scenario(req: Request, bg_tasks: BackgroundTasks):
    # validate req body
    try:
        body = await req.json()
    except Exception:
        return error_response(400, "invalid_json", "Request body is not valid JSON")

    try:
        config = validate_config(body)
    except ValueError as exc:
        return error_response(400, "invalid_configuration", str(exc))

    scenario_id = len(scenarios) + 1
    with lock:
        scenarios[scenario_id] = {"id": scenario_id, "status": "pending", "scenario": None, "error": None}

    bg_tasks.add_task(generate_scenario, scenario_id, config)

    return JSONResponse(
        status_code = 202,
        content = {"id": scenario_id, "status": "pending"},
        headers={"Location": f"/api/scenarios/{scenario_id}"}
    )

# get scenario
@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id):
    try:
        scenario_id = int(scenario_id)
    except:
        return error_response(400, "invalid_id", "id must be an integer")
    
    if scenario_id <= 0:
        return error_response(400, "invalid_id", "id must be greater than 0")

    with lock:
        scenario = scenarios.get(scenario_id)
    
    if scenario is None:
        return error_response(404, "scenario_not_found", f"Scenario {scenario_id} was not found")
    
    response = {"id": scenario["id"], "status": scenario["status"]}
    if scenario["status"] == "completed":
        response["scenario"] = scenario["scenario"]
    elif scenario["status"] == "failed":
        response["error"] = scenario.get("error", "generation failed")
    return response