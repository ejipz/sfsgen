import threading
import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import main
from main import app, AC_EVENTS, generate_credential_theft_scenario

client = TestClient(app)

VALID_PAYLOAD = {"scenario": "credential_theft", "users": 1, "devices": 1, "events": 6, "seed": 42}

# helper functions
def wait_for_completion(id, timeout = 5.0):
    start = time.time()
    
    while time.time() - start < timeout:
        response = client.get(f"/api/scenarios/{id}")
        data = response.json()

        if data["status"] in ("completed", "failed"):
            return data
        
        time.sleep(0.02)

    raise TimeoutError(f"scenario {id} did not finish within {timeout}s")

# tests
def test_scenario_creation():
    response = client.post("/api/scenarios", json=VALID_PAYLOAD)
    assert response.status_code == 202

    body = response.json()
    assert isinstance(body["id"], int) and body["id"] > 0
    assert body["status"] == "pending"
    assert response.headers["location"] == f"/api/scenarios/{body['id']}"

@pytest.mark.parametrize(
    "payload, expected_fragment",
    [
        ({**VALID_PAYLOAD, "scenario": "privilege_escalation"}, "scenario"),
        ({**VALID_PAYLOAD, "scenario": 1}, "scenario"),

        ({**VALID_PAYLOAD, "users": "yes"}, "users"),        
        ({**VALID_PAYLOAD, "users": 0}, "users"),

        ({**VALID_PAYLOAD, "devices": "yes"}, "devices"),
        ({**VALID_PAYLOAD, "devices": 0}, "devices"),

        ({**VALID_PAYLOAD, "events": "yes"}, "events"),
        ({**VALID_PAYLOAD, "events": 3}, "events"),

        ({**VALID_PAYLOAD, "seed": "no"}, "seed"),

        ({k: v for k, v in VALID_PAYLOAD.items() if k !="seed"}, "missing"),
        ({k: v for k, v in VALID_PAYLOAD.items() if k not in ("events", "seed")}, "missing")
    ]
)

def test_invalid_config(payload, expected_fragment):
    response = client.post("/api/scenarios", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_configuration"
    assert expected_fragment in body["message"]

def test_malformed_req():
    response = client.post("/api/scenarios", content="test")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_json"

def test_get_unknown_scenario():
    response = client.get("/api/scenarios/291018")
    assert response.status_code == 404
    assert response.json()["error"] == "scenario_not_found"

def test_deterministic_generation():
    response1 = client.post("/api/scenarios", json=VALID_PAYLOAD)
    response2 = client.post("/api/scenarios", json=VALID_PAYLOAD)

    data1 = wait_for_completion(response1.json()["id"])
    data2 = wait_for_completion(response2.json()["id"])

    assert data1["scenario"] == data2["scenario"]

def test_req_counts():
    response = client.post("/api/scenarios", json=VALID_PAYLOAD)
    data = wait_for_completion(response.json()["id"])
    scenario = data["scenario"]
    assert len(scenario["users"]) == 1
    assert len(scenario["devices"]) == 1
    assert len(scenario["events"]) == 6

def test_entity_ref_id():
    response = client.post("/api/scenarios", json=VALID_PAYLOAD)
    data = wait_for_completion(response.json()["id"])
    scenario = data["scenario"]

    user_ids = {u["id"] for u in scenario["users"]}
    device_ids = {d["id"] for d in scenario["devices"]}
    event_ids = [e["id"] for e in scenario["events"]]

    # check uniqueness
    assert len(user_ids) == len(set(user_ids))
    assert len(device_ids) == len(set(device_ids))
    assert len(event_ids) == len(set(event_ids))

    # referential integrity
    for event in scenario["events"]:
        assert event["actor_user_id"] in user_ids
        assert event["device_id"] in device_ids

def test_timestamp_ac_ordering():
    response = client.post("/api/scenarios", json=VALID_PAYLOAD)
    data = wait_for_completion(response.json()["id"])
    events = data["scenario"]["events"]

    # check if timestamps are valid and chronologically ordered
    timestamps = [datetime.strptime(e["timestamp"], "%Y-%m-%dT%H:%M:%SZ") for e in events]
    assert timestamps == sorted(timestamps)

    types = {e["type"] for e in events}
    for t in AC_EVENTS:
        assert t in types

    def first_index(type):
        return next(i for i, e in enumerate(events) if e["type"] == type)

    assert first_index("process_execution") > first_index("authentication")
    assert first_index("credential_access") > first_index("process_execution")
    assert first_index("network_connection") > first_index("credential_access")
    assert first_index("data_exfiltration") > first_index("network_connection")

@pytest.mark.parametrize(
    "should_fail, expected_status",
    [
        (False, "completed"),
        (True, "failed")
    ]
)

def test_status_transitions(monkeypatch, should_fail, expected_status):
    generate = main.generate_credential_theft_scenario

    def test_generate(*args, **kwargs):
        time.sleep(0.03)

        if should_fail:
            raise RuntimeError("testing status transitions")
        
        return generate(*args, **kwargs)

    monkeypatch.setattr(main, "generate_credential_theft_scenario", test_generate)

    existing_ids = set(main.scenarios.keys())
    post_thread = threading.Thread(
        target=lambda: client.post("/api/scenarios", json=VALID_PAYLOAD)
    )
    post_thread.start()

    deadline = time.time() + 2.0
    scenario_id = None
    while time.time() < deadline:
        new_id = set(main.scenarios.keys()) - existing_ids
        if new_id:
            scenario_id = next(iter(new_id))
            break
        time.sleep(0.01)
    assert scenario_id is not None, "scenario was not created"

    seen_statuses = []
    while time.time() < deadline:
        status = client.get(f"/api/scenarios/{scenario_id}").json()["status"]
        if not seen_statuses or seen_statuses[-1] != status:
            seen_statuses.append(status)
        if status == expected_status:
            break
        time.sleep(0.02)

    post_thread.join(timeout=2.0)

    assert "running" in seen_statuses
    assert seen_statuses[-1] == expected_status
    assert seen_statuses.index("running") < seen_statuses.index(expected_status)

def test_get_completed_scenario():
    # create scenario
    response = client.post("/api/scenarios", json=VALID_PAYLOAD)
    scenario_id = response.json()["id"]

    # check if scenario is completed
    data = wait_for_completion(scenario_id)
    assert data["status"] == "completed"

    # test retrieval
    response = client.get(f"/api/scenarios/{scenario_id}")
    assert response.status_code == 200