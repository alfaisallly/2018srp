# DCMS Production Checklist

## Security
- [ ] `SECRET_KEY` — random 48+ chars in `.env`
- [ ] `DEBUG=false`
- [ ] Admin password changed from default
- [ ] PostgreSQL strong password
- [ ] HTTPS via Nginx + valid certificate
- [ ] Port 8080 not exposed publicly (reverse proxy only)
- [ ] Firewall configured (UFW/iptables)

## Infrastructure
- [ ] PostgreSQL 16 running with persistent volume
- [ ] Redis 7 running
- [ ] systemd service enabled (`dcms.service`)
- [ ] Log rotation configured (`journalctl` or file logs)
- [ ] Daily PostgreSQL backup cron job
- [ ] Server monitoring (disk, RAM, CPU)

## Application
- [ ] Data centers created
- [ ] Network devices imported (Excel or manual)
- [ ] SNMP/SSH credentials verified
- [ ] PRTG integration configured and synced
- [ ] VMware integration (if applicable)
- [ ] IP prefixes defined in IPAM
- [ ] Config backup tested on one Cisco/Juniper device

## Operations
- [ ] Poll interval appropriate (`POLL_INTERVAL_SECONDS=300`)
- [ ] Users and roles assigned per team
- [ ] Alert email SMTP configured (optional)
- [ ] Documentation shared with operations team
