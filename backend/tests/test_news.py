import uuid

from tests.conftest import register_and_login

NEWS = "/api/v1/news"


async def test_list_excludes_duplicates_and_sorts(client, seeded):
    r = await client.get(NEWS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    ids = {i["id"] for i in body["items"]}
    assert str(seeded["dup"]) not in ids
    item = body["items"][0]
    assert item["url"].startswith("https://") and item["source"]["slug"] == "test-feed"
    assert item["collected_at"] and "published_at" in item

    r = await client.get(NEWS, params={"include_duplicates": True})
    assert r.json()["total"] == 4


async def test_full_text_search_and_relevance(client, seeded):
    r = await client.get(NEWS, params={"q": "retrieval generation", "sort": "relevance"})
    items = r.json()["items"]
    assert [i["id"] for i in items] == [str(seeded["a1"])]


async def test_filters(client, seeded):
    r = await client.get(NEWS, params={"item_type": "vulnerability"})
    assert [i["id"] for i in r.json()["items"]] == [str(seeded["a3"])]
    assert r.json()["items"][0]["severity_basis"].startswith("NVD")

    r = await client.get(NEWS, params={"severity": ["critical", "high"]})
    assert r.json()["total"] == 1
    r = await client.get(NEWS, params={"min_importance": 50, "sort": "importance"})
    assert [i["id"] for i in r.json()["items"]] == [str(seeded["a3"]), str(seeded["a1"])]
    r = await client.get(NEWS, params={"source": "unknown-source"})
    assert r.json()["total"] == 0


async def test_pagination(client, seeded):
    r = await client.get(NEWS, params={"page_size": 2, "page": 2})
    body = r.json()
    assert body["pages"] == 2 and len(body["items"]) == 1


async def test_validation_errors(client, seeded):
    r = await client.get(NEWS, params={"page_size": 1000})
    assert r.status_code == 422
    r = await client.get(
        NEWS, params={"date_from": "2026-02-01T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"}
    )
    assert r.status_code == 400
    assert "date_from" in r.json()["error"]["message"]
    r = await client.get(NEWS, params={"severity": "apocalyptic"})
    assert r.status_code == 422


async def test_detail_and_404(client, seeded):
    r = await client.get(f"{NEWS}/{seeded['a1']}")
    assert r.status_code == 200 and r.json()["content_hash"]
    r = await client.get(f"{NEWS}/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_read_state_per_user(client, seeded):
    token = await register_and_login(client)
    h = {"Authorization": f"Bearer {token}"}
    assert (await client.put(f"{NEWS}/{seeded['a1']}/read")).status_code == 401
    assert (await client.put(f"{NEWS}/{seeded['a1']}/read", headers=h)).status_code == 204
    r = await client.get(f"{NEWS}/{seeded['a1']}", headers=h)
    assert r.json()["is_read"] is True
    assert (await client.get(f"{NEWS}/{seeded['a1']}")).json()["is_read"] is False  # anonymous
    assert (await client.delete(f"{NEWS}/{seeded['a1']}/read", headers=h)).status_code == 204
    assert (await client.get(f"{NEWS}/{seeded['a1']}", headers=h)).json()["is_read"] is False


async def test_unknown_query_parameters_are_rejected(client, seeded):
    """A misspelt filter must fail loudly instead of returning unfiltered results."""
    r = await client.get(NEWS, params={"severty": "critical"})
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["loc"] == ["query", "severty"]
    assert (await client.get(NEWS, params={"severity": "critical", "page": 1})).status_code == 200
    assert (await client.get("/api/v1/dashboard/summary", params={"x": "1"})).status_code == 422
    assert (await client.get("/api/v1/dashboard/summary")).status_code == 200
