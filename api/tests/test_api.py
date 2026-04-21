import uuid
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def mock_redis():
    """Fixture that patches the Redis client with a fake one."""
    fake_client = fakeredis.FakeStrictRedis(decode_responses=True)
    with patch('main.r', fake_client):
        yield fake_client


def test_create_job(mock_redis):
    """Test POST /jobs creates a job with queued status."""
    client = TestClient(app)
    response = client.post('/jobs')
    assert response.status_code == 200
    data = response.json()
    assert 'job_id' in data
    assert data['status'] == 'queued'
    job_id = data['job_id']
    assert mock_redis.hget(f'job:{job_id}', 'status') == 'queued'
    assert mock_redis.lrange('job', 0, -1) == [job_id]


def test_get_unknown_job(mock_redis):
    """Test GET /jobs/{unknown_id} returns 404."""
    client = TestClient(app)
    unknown_id = str(uuid.uuid4())
    response = client.get(f'/jobs/{unknown_id}')
    assert response.status_code == 404
    assert response.json()['detail'] == 'not found'


def test_get_job_status(mock_redis):
    """Test GET /jobs/{job_id} returns correct status."""
    client = TestClient(app)
    job_id = str(uuid.uuid4())
    mock_redis.hset(f'job:{job_id}', 'status', 'processing')
    response = client.get(f'/jobs/{job_id}')
    assert response.status_code == 200
    data = response.json()
    assert data['job_id'] == job_id
    assert data['status'] == 'processing'


def test_health_check(mock_redis):
    """Test GET /health returns ok when Redis is available."""
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
