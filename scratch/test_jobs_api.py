import httpx
import sys

def test_api_jobs():
    base_url = "http://localhost:8000/api"
    print("Testing GET /api/ ...")
    try:
        r = httpx.get("http://localhost:8000/")
        print("Root response:", r.status_code, r.json())
    except Exception as e:
        print("Root request failed:", e)
        return

    # Check health / auth
    print("Signing up test user...")
    signup_resp = httpx.post(f"{base_url}/auth/signup", json={
        "email": "testuser@example.com",
        "password": "Password123!",
        "name": "Test User"
    })
    print("Signup status:", signup_resp.status_code)

    # Login
    login_resp = httpx.post(f"{base_url}/auth/login", data={
        "username": "testuser@example.com",
        "password": "Password123!"
    })
    print("Login status:", login_resp.status_code)
    token = login_resp.json().get("access_token")
    print("Token received:", token[:20] if token else "None")

    # Post Job
    dummy_file_path = "scratch/dummy.accdb"
    with open(dummy_file_path, "wb") as f:
        f.write(b"Standard Jet DB header dummy content")

    headers = {"Authorization": f"Bearer {token}"}
    with open(dummy_file_path, "rb") as f:
        files = {"file": ("dummy.accdb", f, "application/octet-stream")}
        params = {"project_name": "TestApp", "base_package": "com.test.app"}
        job_resp = httpx.post(f"{base_url}/jobs", headers=headers, params=params, files=files)
        print("Job Creation status:", job_resp.status_code)
        print("Job Creation response:", job_resp.json() if job_resp.status_code == 200 else job_resp.text)

if __name__ == "__main__":
    test_api_jobs()
