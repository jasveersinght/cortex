from __future__ import annotations

from datetime import datetime, timezone

import pytest
import requests

from hands.providers import BufferProvider, PermanentProviderError, PostPayload, TransientProviderError

WHEN = datetime(2026, 9, 22, 0, 30, tzinfo=timezone.utc)
CHANNELS = {"linkedin": "ch_li", "instagram": "ch_ig", "Jade:instagram": "ch_ig_jade", "tiktok": "ch_tt", "x": "ch_x"}


class Resp:
    def __init__(self, data=None, status=200, headers=None):
        self.status_code, self._data, self.headers, self.text = status, data, headers or {}, str(data)

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def provider(*responses):
    s = Session(*responses)
    return BufferProvider("KEY", CHANNELS, session=s), s


def payload(**kw):
    base = dict(text="Hello", platform="linkedin", brand="Jade", scheduled_for=WHEN)
    base.update(kw)
    return PostPayload(**base)


def ok(post_id="p1"):
    return Resp({"data": {"createPost": {"post": {"id": post_id, "dueAt": "x", "text": "t"}}}})


def test_instagram_reel_payload_matches_buffer_schema():
    p, s = provider(ok())
    res = p.schedule_post(payload(platform="instagram", media_url="https://cdn.x/v.mp4", media_type="video",
                                  first_comment="#A #B", ai_generated=True))
    sent = s.calls[0]
    assert res.post_id == "p1" and sent["url"] == "https://api.buffer.com"
    assert sent["headers"]["Authorization"] == "Bearer KEY"
    inp = sent["json"]["variables"]["input"]
    assert inp["channelId"] == "ch_ig_jade"                                  # brand-specific channel wins
    assert inp["mode"] == "customScheduled" and inp["dueAt"] == "2026-09-22T00:30:00.000Z"
    assert inp["schedulingType"] == "automatic"
    assert inp["assets"] == [{"video": {"url": "https://cdn.x/v.mp4"}}]
    assert inp["metadata"]["instagram"] == {"type": "reel", "shouldShareToFeed": True, "firstComment": "#A #B", "isAiGenerated": True}
    assert "MutationError" in sent["json"]["query"]


def test_linkedin_and_tiktok_metadata():
    p, s = provider(ok(), ok())
    p.schedule_post(payload(first_comment="#Tag"))
    p.schedule_post(payload(platform="tiktok", media_url="https://cdn.x/v.mp4", media_type="video", ai_generated=True))
    assert s.calls[0]["json"]["variables"]["input"]["metadata"] == {"linkedin": {"firstComment": "#Tag"}}
    assert s.calls[1]["json"]["variables"]["input"]["metadata"] == {"tiktok": {"isAiGenerated": True}}


def test_typed_mutation_errors_are_classified():
    p, _ = provider(Resp({"data": {"createPost": {"message": "LinkedIn posts cannot exceed 3000 characters."}}}))
    with pytest.raises(PermanentProviderError):
        p.schedule_post(payload())
    p, _ = provider(Resp({"data": {"createPost": {"message": "Too many requests, try again later"}}}))
    with pytest.raises(TransientProviderError):
        p.schedule_post(payload())


def test_http_errors_are_classified():
    p, _ = provider(Resp({}, status=429, headers={"Retry-After": "30"}))
    with pytest.raises(TransientProviderError) as e:
        p.schedule_post(payload())
    assert e.value.retry_after == 30 and not e.value.ambiguous
    p, _ = provider(Resp({}, status=401))
    with pytest.raises(PermanentProviderError):
        p.schedule_post(payload())
    p, _ = provider(Resp({}, status=502))
    with pytest.raises(TransientProviderError) as e:
        p.schedule_post(payload())
    assert e.value.ambiguous                                                  # server may have processed it


def test_network_failures_distinguish_safe_and_ambiguous():
    p, _ = provider(requests.ConnectionError("dns"))
    with pytest.raises(TransientProviderError) as e:
        p.schedule_post(payload())
    assert not e.value.ambiguous
    p, _ = provider(requests.Timeout("slow"))
    with pytest.raises(TransientProviderError) as e:
        p.schedule_post(payload())
    assert e.value.ambiguous


def test_graphql_system_error_unauthorized_is_permanent():
    p, _ = provider(Resp({"data": None, "errors": [{"message": "Not authorized", "extensions": {"code": "UNAUTHORIZED"}}]}))
    with pytest.raises(PermanentProviderError):
        p.schedule_post(payload())


def test_validate_reports_missing_channel_and_key():
    p, _ = provider()
    assert p.validate("linkedin", "Jade") is None
    assert "no Buffer channel" in BufferProvider("KEY", {}).validate("x", None)
    assert "BUFFER_API_KEY" in BufferProvider("", CHANNELS).validate("x", None)


def test_metrics_mapping_sums_reposts_and_keeps_missing_as_none():
    data = {"data": {"post": {"id": "p1", "status": "sent", "metrics": [
        {"type": "reactions", "value": 12, "unit": "count"}, {"type": "comments", "value": 3, "unit": "count"},
        {"type": "shares", "value": 2, "unit": "count"}, {"type": "reposts", "value": 5, "unit": "count"},
        {"type": "impressions", "value": 900, "unit": "count"}, {"type": "engagementRate", "value": 2.5, "unit": "percentage"}]}}}
    p, _ = provider(Resp(data))
    m = p.fetch_metrics("p1", "linkedin")
    assert (m.likes, m.comments, m.shares, m.impressions, m.engagement_rate, m.status) == (12, 3, 7, 900, 2.5, "sent")
    assert m.clicks is None and m.saves is None and m.has_data


def test_metrics_empty_means_not_reported_yet():
    p, _ = provider(Resp({"data": {"post": {"id": "p1", "status": "scheduled", "metrics": []}}}))
    m = p.fetch_metrics("p1", "x")
    assert not m.has_data and m.status == "scheduled"
