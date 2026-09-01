"""Tests for offline scan parsers in CYB0X-S."""

import pytest
from cyb0x_s.parsers import parse_nmap_xml, parse_nmap_gnmap, parse_netexec_output, derive_potential_and_next


def test_derive_potential_and_next() -> None:
    pot, nxt = derive_potential_and_next("smb", 445, "10.10.10.20")
    assert pot == "HIGH"
    assert "10.10.10.20" in nxt

    pot_http, nxt_http = derive_potential_and_next("http", 80, "10.10.10.20")
    assert pot_http == "HIGH"
    assert "feroxbuster" in nxt_http


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
