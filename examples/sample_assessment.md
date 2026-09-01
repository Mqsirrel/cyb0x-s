# Assessment Workspace: Lab-Assessment-01
> Target machine lab assessment field notebook

# Target: 10.10.10.20
> Hostname: `target.local` | OS: Linux
> Notes: Lab host running web application and file share services

## Services
- 22/tcp — SSH — OpenSSH 8.2p1
- 80/tcp — HTTP — Apache 2.4.41
- 445/tcp — SMB — Samba 4.3

## Findings
- [HIGH] SMB anonymous access enabled
  Read access confirmed to backup share
  Note: Anonymous session allowed by server
- [INFO] HTTP redirects to `/login`
  Landing page presents standard authentication form

## Credentials
- admin : ******** (Source: backup.zip / config.php, Scope: Web Administration)

## Checklist
- [x] TCP enumeration
- [x] HTTP enumeration
- [ ] SMB enumeration
- [-] UDP service sweep (DEFERRED)
- [!] NetBIOS over TCP port 139 (DEAD-END)

## Evidence
- [screenshot] `evidence/proof_screenshot_01.png` — Anonymous SMB access listing backup share
- [flag] `c8d10b7145229ad1283e1c6684784a1d` — User flag proof

## Notes
- backup share contains archive.zip
- archive.zip contains old site configs and admin credentials
---
