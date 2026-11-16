from concurrent.futures import ThreadPoolExecutor
from commercepilot.delivery import MetaTextSender, ProviderRejected
from test_whatsapp import wa_setup, onboard, payload, post


class Sender:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def send(self, phone, recipient, body):
        self.calls.append((phone, recipient, body))
        if self.error:
            raise self.error
        return "wamid.outgoing"


def draft(setup, sender=None):
    app, c, h, merchant, binding, clock = setup
    onboard(c, app.state.whatsapp)
    app.state.delivery.sender = sender
    item = c.get("/v1/whatsapp/outbox", headers=h).json()[0]
    return item["id"], f"/v1/whatsapp/outbox/{item['id']}/send"


def receipt(c, status, recipient="2348012345678", waba="111"):
    data = payload()
    data["entry"][0]["id"] = waba
    value = data["entry"][0]["changes"][0]["value"]
    value.pop("messages")
    value["statuses"] = [{"id":"wamid.outgoing", "status":status, "recipient_id":recipient}]
    assert post(c, data).status_code == 200


def test_acceptance_is_not_delivery_and_never_resubmits(wa_setup):
    app, c, h, merchant, _, _ = wa_setup
    sender = Sender()
    item, url = draft(wa_setup, sender)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: app.state.delivery.send(merchant, item), range(4)))
    assert len(sender.calls) == 1
    assert all(r["state"] in {"submitting", "accepted"} for r in results)
    assert c.post(url, headers=h).json()["resubmitted"] is False
    assert c.get("/v1/whatsapp/deliveries", headers=h).json()[0]["state"] == "accepted"
    receipt(c, "read", recipient="2348099999999")
    receipt(c, "read", waba="999")
    assert app.state.delivery.records(merchant)[0]["state"] == "accepted"
    receipt(c, "delivered")
    assert app.state.delivery.records(merchant)[0]["state"] == "delivered"
    receipt(c, "sent")
    assert app.state.delivery.records(merchant)[0]["state"] == "delivered"
    receipt(c, "read")
    assert app.state.delivery.records(merchant)[0]["state"] == "read"


def test_unknown_submission_is_not_retried(wa_setup):
    app, c, h, merchant, _, _ = wa_setup
    sender = Sender(TimeoutError("secret response"))
    _, url = draft(wa_setup, sender)
    response = c.post(url, headers=h)
    assert response.json()["state"] == "uncertain"
    assert "secret" not in response.text
    assert c.post(url, headers=h).json()["resubmitted"] is False
    assert len(sender.calls) == 1


def test_disabled_expired_and_revoked_replies(wa_setup):
    app, c, h, merchant, binding, clock = wa_setup
    _, url = draft(wa_setup)
    assert c.post(url, headers=h).status_code == 409
    sender = Sender()
    app.state.delivery.sender = sender
    other, key = app.state.services.provision("Other")
    assert c.post(url, headers={"Authorization": "Bearer " + key}).status_code == 404
    clock.time += 86400
    assert c.post(url, headers=h).status_code == 409
    clock.time -= 86400
    app.state.whatsapp.revoke(merchant, binding["id"])
    assert c.post(url, headers=h).status_code == 409
    assert sender.calls == []


def test_early_receipt_and_rejection(wa_setup):
    app, c, h, merchant, _, _ = wa_setup
    _, url = draft(wa_setup, Sender())
    receipt(c, "delivered")
    assert c.post(url, headers=h).json()["state"] == "delivered"


def test_provider_rejection_is_failed(wa_setup):
    app, c, h, merchant, _, _ = wa_setup
    sender = Sender(ProviderRejected("private details"))
    _, url = draft(wa_setup, sender)
    assert c.post(url, headers=h).json()["state"] == "failed"
    assert len(sender.calls) == 1


def test_meta_transport_uses_configured_phone_and_exact_text():
    calls = []
    def transport(phone, data):
        calls.append((phone, data))
        return {"messages":[{"id":"wamid.provider"}]}
    sender = MetaTextSender("fixture", "v25.0", "222", transport)
    assert sender.send("222", "2348012345678", "Facts only") == "wamid.provider"
    assert calls[0][1]["text"] == {"body":"Facts only", "preview_url":False}
