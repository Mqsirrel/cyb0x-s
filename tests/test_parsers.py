"""Tests for offline scan parsers in CYB0X-S."""

from cyb0x_s.parsers import (
    derive_potential_and_next,
    parse_netexec_output,
    parse_nmap_gnmap,
    parse_nmap_xml,
)
from cyb0x_s.settings import set_derive_guidance


def test_derive_potential_and_next_gated_off_by_default() -> None:
    """Nothing is derived unless the operator opts in (default: exam-safe)."""
    assert derive_potential_and_next("smb", 445, "10.10.10.20") == ("", "")
    assert derive_potential_and_next("http", 80, "10.10.10.20") == ("", "")


def test_derive_potential_and_next_when_enabled() -> None:
    set_derive_guidance(True)
    try:
        pot, nxt = derive_potential_and_next("smb", 445, "10.10.10.20")
        assert pot == "HIGH"
        assert "10.10.10.20" in nxt

        pot_http, nxt_http = derive_potential_and_next("http", 80, "10.10.10.20")
        assert pot_http == "HIGH"
        assert "feroxbuster" in nxt_http
    finally:
        set_derive_guidance(None)


def test_derive_potential_and_next_enabled_parameter() -> None:
    """The per-call ``enabled`` flag overrides the global switch."""
    set_derive_guidance(False)
    # Explicit opt-in restores ratings even when the global switch is off.
    pot, nxt = derive_potential_and_next("smb", 445, "10.10.10.20", enabled=True)
    assert pot == "HIGH"
    assert "10.10.10.20" in nxt

    # Explicit opt-out suppresses even when the global switch is on.
    set_derive_guidance(True)
    pot_off, nxt_off = derive_potential_and_next("http", 80, "10.10.10.20", enabled=False)
    assert pot_off == ""
    assert nxt_off == ""
    set_derive_guidance(None)


def test_parse_functions_accept_derive_guidance_flag() -> None:
    """Parsers thread the opt-in flag through to derivation."""
    xml_data = (
        '<?xml version="1.0"?><nmaprun><host><status state="up"/>'
        '<address addr="10.10.11.50" addrtype="ipv4"/>'
        '<ports><port protocol="tcp" portid="445"><state state="open"/>'
        '<service name="smb" product="Samba" version="4.3"/></port></ports>'
        "</host></nmaprun>"
    )
    off = parse_nmap_xml(xml_data, derive_guidance=False)
    assert off[0]["services"][0]["access_potential"] == ""
    assert off[0]["services"][0]["next_action"] == ""

    on = parse_nmap_xml(xml_data, derive_guidance=True)
    assert on[0]["services"][0]["access_potential"] == "HIGH"
    assert on[0]["services"][0]["next_action"]


def test_parse_nmap_xml_string() -> None:
    xml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <nmaprun scanner="nmap" start="1700000000">
      <host>
        <status state="up" />
        <address addr="10.10.11.50" addrtype="ipv4" />
        <hostnames>
          <hostname name="target.htb" type="user" />
        </hostnames>
        <ports>
          <port protocol="tcp" portid="22">
            <state state="open" />
            <service name="ssh" product="OpenSSH" version="8.9p1" />
          </port>
          <port protocol="tcp" portid="80">
            <state state="open" />
            <service name="http" product="Apache httpd" version="2.4.52" />
          </port>
        </ports>
        <os>
          <osmatch name="Linux 5.4" accuracy="95" />
        </os>
      </host>
    </nmaprun>
    """
    results = parse_nmap_xml(xml_data)
    assert len(results) == 1
    target = results[0]
    assert target["ip"] == "10.10.11.50"
    assert target["hostname"] == "target.htb"
    assert target["os"] == "Linux 5.4"
    assert len(target["services"]) == 2
    assert target["services"][0]["port"] == 22
    assert target["services"][0]["service"] == "ssh"
    assert target["services"][1]["port"] == 80
    assert target["services"][1]["service"] == "http"


def test_parse_nmap_gnmap_string() -> None:
    gnmap_data = (
        "Host: 10.10.11.60 (box.local)\tStatus: Up\n"
        "Host: 10.10.11.60 (box.local)\tPorts: 21/open/tcp//ftp//vsftpd 3.0.3/, 80/open/tcp//http//nginx 1.18.0/\n"
    )
    results = parse_nmap_gnmap(gnmap_data)
    assert len(results) == 1
    target = results[0]
    assert target["ip"] == "10.10.11.60"
    assert target["hostname"] == "box.local"
    assert len(target["services"]) == 2
    assert target["services"][0]["port"] == 21
    assert target["services"][0]["service"] == "ftp"


def test_parse_netexec_output() -> None:
    nxc_data = (
        "SMB         10.10.11.70     445    DC01             [*] Windows 10 / Server 2019 (name:DC01) (domain:CORP.LOCAL) (signing:True) (SMBv1:False)\n"
        "WINRM       10.10.11.70    5985    DC01             [*] Windows 10 / Server 2019 (name:DC01) (domain:CORP.LOCAL)\n"
    )
    results = parse_netexec_output(nxc_data)
    assert len(results) == 1
    target = results[0]
    assert target["ip"] == "10.10.11.70"
    assert target["hostname"] == "DC01"
    assert len(target["services"]) == 2
