from fastapi.testclient import TestClient

from app.main import app

<<<<<<< HEAD
=======

>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
client = TestClient(app)


def test_health():
    response = client.get("/health")
<<<<<<< HEAD
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
=======

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
>>>>>>> 49a28aaedde5cc59922adf61aeac08e094d292b0
