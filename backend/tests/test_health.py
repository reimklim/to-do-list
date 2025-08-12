from app import app as flask_app

def test_health_ok():
    client=flask_app.test_client()
    response=client.get('/health')
    assert response.status_code==200
    assert response.data.decode("UTF-8")=="OK"