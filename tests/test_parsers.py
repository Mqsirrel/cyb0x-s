"""Tests for offline scan parsers in CYB0X-S."""

from cyb0x_s.parsers import (
    detect_file_scan_type,
    parse_netexec_output,
    parse_nmap_gnmap,
    parse_nmap_text,
    parse_nmap_xml,
    parse_web_enum_file,
)


def test_parsers_emit_pure_facts_without_heuristic_derivation() -> None:
    """Parsers strictly emit raw scanner facts; access_potential and next_action remain empty."""
    xml_data = (
        '<?xml version="1.0"?><nmaprun><host><status state="up"/>'
        '<address addr="10.10.11.50" addrtype="ipv4"/>'
        '<ports><port protocol="tcp" portid="445"><state state="open"/>'
        '<service name="smb" product="Samba" version="4.3"/></port></ports>'
        "</host></nmaprun>"
    )
    res_xml = parse_nmap_xml(xml_data)
    svc_xml = res_xml[0]["services"][0]
    assert svc_xml["port"] == 445
    assert svc_xml["service"] == "smb"
    assert svc_xml["access_potential"] == ""
    assert svc_xml["next_action"] == ""

    # NetExec
    nxc_data = "SMB 10.10.11.50 445 DC01 [*] Windows\n"
    res_nxc = parse_netexec_output(nxc_data)
    svc_nxc = res_nxc[0]["services"][0]
    assert svc_nxc["access_potential"] == ""
    assert svc_nxc["next_action"] == ""

    # Gnmap
    gnmap_data = (
        "Host: 10.10.11.50 (dc01)\tStatus: Up\n"
        "Host: 10.10.11.50 (dc01)\tPorts: 445/open/tcp//microsoft-ds///\n"
    )
    res_gnmap = parse_nmap_gnmap(gnmap_data)
    svc_gnmap = res_gnmap[0]["services"][0]
    assert svc_gnmap["access_potential"] == ""
    assert svc_gnmap["next_action"] == ""

    # Normal text
    text_data = (
        "Nmap scan report for 10.10.11.50\n"
        "PORT    STATE SERVICE      VERSION\n"
        "445/tcp open  microsoft-ds Windows 10\n"
    )
    res_text = parse_nmap_text(text_data)
    svc_text = res_text[0]["services"][0]
    assert svc_text["access_potential"] == ""
    assert svc_text["next_action"] == ""


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


def test_parse_web_enum_file_ffuf(tmp_path) -> None:
    ffuf_content = """{
      "results": [
        {
          "input": {"FUZZ": "admin"},
          "position": 1,
          "status": 200,
          "length": 1243,
          "words": 85,
          "lines": 30,
          "redirectlocation": "",
          "url": "http://10.10.10.10/admin"
        },
        {
          "input": {"FUZZ": "login.php"},
          "position": 2,
          "status": 302,
          "length": 0,
          "words": 0,
          "lines": 1,
          "redirectlocation": "dashboard.php",
          "url": "http://10.10.10.10/login.php"
        }
      ]
    }"""
    f = tmp_path / "ffuf.json"
    f.write_text(ffuf_content, encoding="utf-8")
    results = parse_web_enum_file(f)
    assert len(results) == 2
    assert results[0]["path"] == "/admin"
    assert results[0]["status"] == 200
    assert results[0]["size"] == 1243
    assert results[0]["tool"] == "ffuf"

    assert results[1]["path"] == "/login.php"
    assert results[1]["status"] == 302
    assert results[1]["redirect"] == "dashboard.php"


def test_parse_web_enum_file_feroxbuster(tmp_path) -> None:
    ferox_content = """{"type":"response","url":"http://10.10.10.10/images","path":"/images","status":200,"content_length":542,"word_count":25}
{"type":"response","url":"http://10.10.10.10/uploads","path":"/uploads","status":403,"content_length":153,"word_count":10}
"""
    f = tmp_path / "ferox.json"
    f.write_text(ferox_content, encoding="utf-8")
    results = parse_web_enum_file(f)
    assert len(results) == 2
    assert results[0]["path"] == "/images"
    assert results[0]["status"] == 200
    assert results[0]["size"] == 542
    assert results[0]["tool"] == "feroxbuster"

    assert results[1]["path"] == "/uploads"
    assert results[1]["status"] == 403


def test_parse_web_enum_file_gobuster_and_dirsearch(tmp_path) -> None:
    gobuster_content = """===============================================================
Gobuster v3.5
===============================================================
/api                  (Status: 200) [Size: 84]
/secret               (Status: 301) [Size: 178] [--> http://10.10.10.10/secret/]
"""
    f = tmp_path / "gobuster.txt"
    f.write_text(gobuster_content, encoding="utf-8")
    results = parse_web_enum_file(f)
    assert len(results) == 2
    assert results[0]["path"] == "/api"
    assert results[0]["status"] == 200
    assert results[0]["size"] == 84
    assert results[0]["tool"] == "gobuster"
    assert results[1]["path"] == "/secret"
    assert results[1]["status"] == 301
    assert results[1]["redirect"] == "http://10.10.10.10/secret/"

    dirsearch_content = """[12:00:01] 200 -  512B  - /robots.txt
[12:00:02] 401 -   42B  - /management
"""
    f2 = tmp_path / "dirsearch.txt"
    f2.write_text(dirsearch_content, encoding="utf-8")
    results2 = parse_web_enum_file(f2)
    assert len(results2) == 2
    assert results2[0]["path"] == "/robots.txt"
    assert results2[0]["status"] == 200
    assert results2[0]["tool"] == "dirsearch"
    assert results2[1]["path"] == "/management"
    assert results2[1]["status"] == 401


def test_detect_file_scan_type(tmp_path) -> None:
    f_nmap = tmp_path / "nmap.xml"
    f_nmap.write_text('<?xml version="1.0"?><nmaprun>', encoding="utf-8")
    assert detect_file_scan_type(f_nmap) == "nmap"

    f_ffuf = tmp_path / "ffuf.json"
    f_ffuf.write_text('{"results": [], "config": {"commandline": "ffuf -u http://10.10.10.10/FUZZ"}}', encoding="utf-8")
    assert detect_file_scan_type(f_ffuf) == "web_enum"

    f_gobuster = tmp_path / "gobuster.txt"
    f_gobuster.write_text("Gobuster v3.5\n/admin (Status: 200)", encoding="utf-8")
    assert detect_file_scan_type(f_gobuster) == "web_enum"

