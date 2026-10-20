import cloudmesh.core.firewall as fw


def fake_ssh(responses):
    def _run(host, user, key, cmd):
        for needle, (out, rc) in responses.items():
            if needle in cmd:
                return out, rc
        return "", 0

    return _run


def test_backend_detection_prefers_pf_over_ipfw(monkeypatch):
    monkeypatch.setattr(
        fw,
        "_run_ssh",
        fake_ssh({"which ufw": ("", 1), "pfctl -s info": ("Status: Enabled for 1 days\n", 0)}),
    )
    assert fw._detect_backend("h", "root", "") == "pf"


def test_pf_add_rule_writes_anchor_and_quotes(monkeypatch):
    seen = {}

    def run(host, user, key, cmd):
        seen["cmd"] = cmd
        if "pfctl -a cloudmesh -sr" in cmd:
            return "pass in proto tcp from any to any port 22\n", 0
        return "", 0

    monkeypatch.setattr(fw, "_run_ssh", run)
    out = fw._pf_add_rule("h", "root", "", "pass in proto tcp from any to any port 80")
    assert "pfctl -a cloudmesh -f -" in seen["cmd"]
    assert "port 80" in seen["cmd"]
    assert "port 22" in seen["cmd"]  # existing rule preserved
    assert out.startswith("Rule added")


def test_pf_add_rule_does_not_duplicate_an_existing_rule(monkeypatch):
    written = {}

    def run(host, user, key, cmd):
        if "pfctl -a cloudmesh -sr" in cmd:
            return "pass in proto tcp from any to any port 80\n", 0
        written["payload"] = cmd
        return "", 0

    monkeypatch.setattr(fw, "_run_ssh", run)
    fw._pf_add_rule("h", "root", "", "pass in proto tcp from any to any port 80")
    assert written["payload"].count("port 80") == 1


def test_pf_delete_rule_removes_only_the_match(monkeypatch):
    written = {}

    def run(host, user, key, cmd):
        if "pfctl -a cloudmesh -sr" in cmd:
            return (
                "pass in proto tcp from any to any port 22\n"
                "block in proto tcp from any to any port 80\n",
                0,
            )
        written["payload"] = cmd
        return "", 0

    monkeypatch.setattr(fw, "_run_ssh", run)
    out = fw._pf_delete_rule("h", "root", "", "block in proto tcp from any to any port 80")
    assert out == "Rule deleted"
    assert "port 22" in written["payload"]
    assert "port 80" not in written["payload"]


def test_ipfw_reports_explicit_limitation(monkeypatch):
    monkeypatch.setattr(
        fw,
        "_run_ssh",
        fake_ssh(
            {
                "which ufw": ("", 1),
                "pfctl -s info": ("", 1),
                "ipfw list": ("65535 allow ip from any to any\n", 0),
            }
        ),
    )
    monkeypatch.setattr(fw, "_get_server", lambda n: {"host": "h", "user": "root", "key": ""})
    msg = fw.firewall_add_rule("bsd1", "allow 80/tcp")
    assert "ipfw" in msg and "not supported" in msg.lower()


def test_pf_translates_a_ufw_style_rule(monkeypatch):
    monkeypatch.setattr(
        fw,
        "_run_ssh",
        fake_ssh(
            {
                "which ufw": ("", 1),
                "pfctl -s info": ("Status: Enabled\n", 0),
                "pfctl -a cloudmesh -sr": ("", 0),
            }
        ),
    )
    monkeypatch.setattr(fw, "_get_server", lambda n: {"host": "h", "user": "root", "key": ""})
    record = {}
    orig = fw._run_ssh

    def run(host, user, key, cmd):
        if "pfctl -a cloudmesh -f -" in cmd:
            record["cmd"] = cmd
        return orig(host, user, key, cmd)

    monkeypatch.setattr(fw, "_run_ssh", run)
    msg = fw.firewall_add_rule("bsd1", "allow 80/tcp")
    assert msg.startswith("Rule added")
    assert "pass in proto tcp from any to any port 80" in record["cmd"]
