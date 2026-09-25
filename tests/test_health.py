from app.api.v1.routes import health_route as health_module


async def test_root_returns_hello_world(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


async def test_health_check_when_database_is_up(client, monkeypatch):
    async def fake_check_database_connection():
        return True

    monkeypatch.setattr(health_module, "check_database_connection", fake_check_database_connection)

    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"


async def test_health_check_when_database_is_down(client, monkeypatch):
    async def fake_check_database_connection():
        raise ConnectionError("boom")

    monkeypatch.setattr(health_module, "check_database_connection", fake_check_database_connection)

    response = await client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "unhealthy"
