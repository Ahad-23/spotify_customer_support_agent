"""Tests for backend tasks router and dedicated event loop executor."""

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.worker.state import TaskWorkerState
from backend.main import app
from backend.routers.tasks import _run_worker_in_dedicated_loop


def test_create_and_get_task():
    client = TestClient(app)
    mock_state = TaskWorkerState(
        task="Test task",
        status="done",
        summary="Task succeeded",
        verified=True,
    )

    with patch("backend.routers.tasks.run_task_worker", return_value=mock_state):
        resp = client.post("/api/tasks", json={"task": "Create sample ticket"})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["status"] == "planning"

        task_id = data["id"]
        get_resp = client.get(f"/api/tasks/{task_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == task_id


def test_get_invalid_task_id():
    client = TestClient(app)
    resp = client.get("/api/tasks/invalid@id!with*bad*chars")
    assert resp.status_code == 400


def test_get_nonexistent_task():
    client = TestClient(app)
    resp = client.get("/api/tasks/notfound123")
    assert resp.status_code == 404


def test_run_worker_in_dedicated_loop_mock():
    mock_state = TaskWorkerState(
        task="Mock test",
        status="done",
        summary="Done",
        verified=True,
    )
    with patch("backend.routers.tasks.run_task_worker", return_value=mock_state):
        res = _run_worker_in_dedicated_loop("Mock test")
        assert res.summary == "Done"
        assert res.verified is True
