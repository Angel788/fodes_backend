import os
import sys
import httpx
import pytest
import asyncio
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

# Setup Base URL - you can change this to test a live server
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# Use a unique email for testing to avoid collisions
TEST_USER = {
    "nombre": "Test User",
    "correo": f"test_{os.urandom(4).hex()}@example.com",
    "password": f"testpassword123{os.urandom(4).hex()}"
}


@pytest.mark.asyncio
async def test_api_workflow():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Register User
        print(f"\nRegistering user: {TEST_USER['correo']}")
        reg_res = await client.post("/register", json=TEST_USER)
        if reg_res.status_code != 200:
            print(
                f"Registration failed: {reg_res.status_code} - {reg_res.text}")
        assert reg_res.status_code == 200
        assert reg_res.json()["status"] == "success"

        # 2. Login
        print("Logging in...")
        login_data = {
            "correo": TEST_USER["correo"],
            "password": TEST_USER["password"]
        }
        login_res = await client.post("/login", json=login_data)
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.status_code} - {login_res.text}")
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Create Publication
        print("Creating publication...")
        pub_data = {
            "title": "Async Test Publication",
            "content": "Testing with httpx async client",
            "tags": ["async", "httpx"],
            "category": "Tecnología"
        }
        pub_res = await client.post("/publications", json=pub_data, headers=headers)
        assert pub_res.status_code == 200
        pub_cid = pub_res.json()["data"]["cid_content"]
        assert pub_cid.startswith("bafy")

        # 4. Search Publication
        print(f"Searching for CID: {pub_cid}")
        search_res = await client.get(f"/publications/search-cids", params={"cid": pub_cid}, headers=headers)
        assert search_res.status_code == 200
        assert pub_cid in search_res.json()["cids"]

        # 5. Create Comment
        print("Creating comment...")
        comment_data = {
            "titulo": "Async Test Comment",
            "publication_cid": pub_cid,
            "contenido": "This is an async test comment",
            "tags": [1, 2]
        }
        comment_res = await client.post("/comments", json=comment_data, headers=headers)
        assert comment_res.status_code == 200
        comment_cid = comment_res.json()["cid"]
        assert comment_cid.startswith("bafy")

        # 6. Get Comments for Publication
        print("Retrieving comments...")
        comments_res = await client.get(f"/comments/publication/{pub_cid}", headers=headers)
        assert comments_res.status_code == 200
        assert comment_cid in comments_res.json()["data"]

        # 7. Vote and get Rating (Batch)
        print("Voting and checking batch rating...")
        vote_data = {"cid_content": pub_cid, "vote": 4}
        vote_res = await client.post("/publications/vote", json=vote_data, headers=headers)
        assert vote_res.status_code == 200

        # Batch Rating Request { "cids": ["..."] }
        rating_res = await client.post("/publications/rating", json={"cids": [pub_cid]}, headers=headers)
        if rating_res.status_code != 200:
            print(
                f"Rating batch failed: {rating_res.status_code} - {rating_res.text}")
        assert rating_res.status_code == 200
        rating_info = rating_res.json()["ratings"][pub_cid]
        assert rating_info["average_rating"] == 4.0
        assert rating_info["total_votes"] == 1

        # 8. Network Info
        print("Checking network info...")
        net_res = await client.get("/network/bootstrap-info", headers=headers)
        print(net_res.json())
        # May be 404 if no node registered, but we check structure if 200
        if net_res.status_code == 200:
            assert "bootstrap_node" in net_res.json()
            assert "psk" in net_res.json()

        print("\nAll tests passed successfully using httpx!")

if __name__ == "__main__":
    # To run this script directly: python tests/test_api.py
    asyncio.run(test_api_workflow())
