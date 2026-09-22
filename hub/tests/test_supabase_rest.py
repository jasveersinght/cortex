import pytest

from hub.supabase_rest import SupabaseError, SupabaseRest


class Resp:
    def __init__(self, status=200, data=None, text=""):
        self.status_code, self._data, self.text = status, data, text or str(data)

    def json(self):
        return self._data


class Session:
    def __init__(self, resp):
        self.resp, self.calls = resp, []

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json, "headers": headers})
        return self.resp


def test_upsert_sends_prefer_header_and_on_conflict_param():
    s = Session(Resp(201, [{"id": "1"}]))
    client = SupabaseRest("https://proj.supabase.co", "KEY", session=s)
    out = client.upsert("content_generations", {"id": "1"}, "id")
    assert out == [{"id": "1"}]
    call = s.calls[0]
    assert call["url"] == "https://proj.supabase.co/rest/v1/content_generations"
    assert call["params"] == {"on_conflict": "id"}
    assert call["headers"]["Prefer"] == "resolution=merge-duplicates,return=representation"
    assert call["headers"]["apikey"] == "KEY"


def test_empty_rows_short_circuit_without_a_request():
    s = Session(Resp(200, []))
    client = SupabaseRest("https://x.supabase.co", "K", session=s)
    assert client.upsert("t", [], "id") == []
    assert s.calls == []


def test_error_status_raises_supabase_error():
    s = Session(Resp(401, text="invalid api key"))
    client = SupabaseRest("https://x.supabase.co", "bad", session=s)
    with pytest.raises(SupabaseError) as e:
        client.upsert("t", {"id": "1"}, "id")
    assert e.value.status == 401


def test_disabled_without_url_or_key():
    assert not SupabaseRest("", "").enabled
    assert not SupabaseRest("https://x.supabase.co", "").enabled
    with pytest.raises(SupabaseError):
        SupabaseRest("", "").select("t")
