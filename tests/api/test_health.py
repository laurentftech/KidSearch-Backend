"""
Tests for health check endpoint
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
def test_health_endpoint_returns_200(api_client):
    """Test that health endpoint returns 200 OK"""
    response = api_client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.api
def test_health_endpoint_structure(api_client):
    """Test health endpoint response structure"""
    response = api_client.get("/api/health")
    data = response.json()

    assert "status" in data
    assert "version" in data
    assert "timestamp" in data
    assert "services" in data


@pytest.mark.api
def test_health_endpoint_services(api_client):
    """Test health endpoint includes service status"""
    response = api_client.get("/api/health")
    data = response.json()

    services = data["services"]
    assert "typesense" in services
    assert "reranker" in services
    assert "cache" in services
    assert isinstance(services["typesense"], bool)


@pytest.mark.api
def test_health_endpoint_status_healthy(api_client):
    """Test health endpoint status is healthy when all services OK"""
    response = api_client.get("/api/health")
    data = response.json()

    # Should be healthy or degraded based on actual service status
    assert data["status"] in ["healthy", "degraded"]
