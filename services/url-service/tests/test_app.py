import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app


def test_health():
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_shorten_url():
    client = app.test_client()

    response = client.post(
        "/shorten",
        json={"url": "https://github.com"}
    )

    assert response.status_code == 201

    data = response.json

    assert "code" in data
    assert data["url"] == "https://github.com"


def test_redirect():
    client = app.test_client()

    response = client.post(
        "/shorten",
        json={"url": "https://github.com"}
    )

    code = response.json["code"]

    response = client.get(
        f"/{code}",
        follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "https://github.com"


def test_missing_url():
    client = app.test_client()

    response = client.post(
        "/shorten",
        json={}
    )

    assert response.status_code == 400


def test_unknown_code():
    client = app.test_client()

    response = client.get("/does-not-exist")

    assert response.status_code == 404
