MONITORING_GUIDES = {
    "server": {
        "asset_type": "server",
        "protocols": [
            {
                "protocol": "ssh",
                "port": 22,
                "os": ["linux", "other"],
                "fields": ["username", "password"],
                "description": "Linux: uptime, memory, disk via SSH",
            },
            {
                "protocol": "winrm",
                "port": 5985,
                "os": ["windows"],
                "fields": ["username", "password"],
                "description": "Windows: CPU load via WinRM (requires pywinrm)",
            },
            {
                "protocol": "snmp",
                "port": 161,
                "os": ["linux", "windows", "other"],
                "fields": ["community"],
                "description": "Generic HOST-RESOURCES-MIB monitoring",
            },
            {
                "protocol": "rest",
                "port": 443,
                "os": ["vmware"],
                "fields": ["api_token", "username", "password"],
                "description": "VMware ESXi/vCenter REST API",
            },
            {
                "protocol": "ipmi",
                "port": 623,
                "os": ["linux", "windows", "other"],
                "fields": ["username", "password"],
                "description": "Hardware sensors via ipmitool (BMC/iDRAC/iLO)",
            },
        ],
    },
    "storage": {
        "asset_type": "storage",
        "protocols": [
            {
                "protocol": "rest",
                "port": 443,
                "vendors": ["pure_storage"],
                "fields": ["api_token"],
                "description": "Pure Storage FlashArray REST API (api-token header, /api/1.17/array?space=true)",
            },
            {
                "protocol": "snmp",
                "port": 161,
                "vendors": ["pure_storage"],
                "fields": ["community"],
                "description": "Pure Storage SNMP (enterprise OID 40482) — capacity monitoring",
            },
            {
                "protocol": "snmp",
                "port": 161,
                "vendors": ["netapp", "dell_emc", "hpe", "generic"],
                "fields": ["community"],
                "description": "Capacity OIDs per vendor (NetApp 789, Dell 674, HPE 232)",
            },
            {
                "protocol": "rest",
                "port": 443,
                "vendors": ["qnap", "synology", "netapp"],
                "fields": ["api_token"],
                "description": "REST API for NAS/SAN management interface",
            },
            {
                "protocol": "ssh",
                "port": 22,
                "vendors": ["generic", "qnap", "synology"],
                "fields": ["username", "password"],
                "description": "Disk usage via df command",
            },
        ],
    },
    "network": {
        "asset_type": "network",
        "protocols": [
            {"protocol": "snmp", "port": 161, "vendors": ["cisco", "juniper", "fortinet"], "fields": ["community"]},
            {"protocol": "ssh", "port": 22, "vendors": ["cisco", "juniper", "fortinet"], "fields": ["username", "password"]},
            {"protocol": "netconf", "port": 830, "vendors": ["cisco", "juniper"], "fields": ["username", "password"]},
            {"protocol": "rest", "port": 443, "vendors": ["cisco", "fortinet"], "fields": ["api_token"]},
        ],
    },
}
