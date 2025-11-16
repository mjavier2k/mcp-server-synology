# src/dnsserver/synology_dnsserver.py - Synology DNS Server API utilities

import requests
from typing import Dict, List, Any, Optional


class SynologyDNSServer:
    """Handles Synology DNS Server API operations."""

    def __init__(self, base_url: str, session_id: str):
        self.base_url = base_url.rstrip('/')
        self.session_id = session_id
        self.api_url = f"{self.base_url}/webapi/entry.cgi"

    def _make_request(self, api: str, version: str, method: str, use_post: bool = False, **params) -> Dict[str, Any]:
        """Make a request to Synology DNS Server API."""
        request_params = {
            'api': api,
            'version': version,
            'method': method,
            '_sid': self.session_id,
            **params
        }

        if use_post:
            response = requests.post(
                self.api_url,
                data=request_params,
                verify=False
            )
        else:
            response = requests.get(self.api_url, params=request_params, verify=False)

        response.raise_for_status()

        data = response.json()
        if not data.get('success'):
            error_code = data.get('error', {}).get('code', 'unknown')
            error_info = data.get('error', {})
            raise Exception(f"DNS Server API error: {error_code} - {error_info}")

        return data.get('data', {})

    # ====================================================================
    # ZONE MANAGEMENT
    # ====================================================================

    def list_zones(self) -> List[Dict[str, Any]]:
        """
        List all DNS zones.

        Returns:
            List of zones with their configuration
        """
        data = self._make_request('SYNO.DNSServer.Zone', '1', 'list')

        zones = data.get('items', [])
        return [{
            'zone_name': zone.get('zone_name'),
            'domain_name': zone.get('domain_name'),
            'zone_type': zone.get('zone_type'),  # master, slave, forward
            'domain_type': zone.get('domain_type'),  # forward, reverse
            'zone_enable': zone.get('zone_enable'),
            'is_readonly': zone.get('is_readonly', False)
        } for zone in zones]

    def get_zone(self, zone_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific zone.

        Args:
            zone_name: Name of the DNS zone

        Returns:
            Zone configuration details
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone', '1', 'get',
            zone_name=zone_name,
            domain_name=zone_name  # Required parameter
        )
        return data

    def create_master_zone(self, zone_name: str, serial: Optional[int] = None,
                          refresh: int = 10800, retry: int = 3600,
                          expire: int = 604800, ttl: int = 86400) -> Dict[str, Any]:
        """
        Create a new master DNS zone.

        Args:
            zone_name: Name of the DNS zone (e.g., 'example.com')
            serial: Serial number (default: auto-generated)
            refresh: Refresh interval in seconds
            retry: Retry interval in seconds
            expire: Expire time in seconds
            ttl: Default TTL in seconds

        Returns:
            Result of zone creation
        """
        params = {
            'zone_name': zone_name,
            'refresh': refresh,
            'retry': retry,
            'expire': expire,
            'ttl': ttl
        }

        if serial is not None:
            params['serial'] = serial

        data = self._make_request(
            'SYNO.DNSServer.Zone', '1', 'create',
            use_post=True,
            **params
        )
        return data

    def create_forward_zone(self, zone_name: str, forwarders: List[str]) -> Dict[str, Any]:
        """
        Create a forward DNS zone.

        Args:
            zone_name: Name of the DNS zone
            forwarders: List of DNS forwarder IP addresses

        Returns:
            Result of zone creation
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone', '1', 'create',
            use_post=True,
            zone_name=zone_name,
            zone_type='forward',
            forwarders=','.join(forwarders) if isinstance(forwarders, list) else forwarders
        )
        return data

    def delete_zone(self, zone_name: str) -> Dict[str, Any]:
        """
        Delete a DNS zone.

        Args:
            zone_name: Name of the zone to delete

        Returns:
            Result of zone deletion
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone', '1', 'delete',
            use_post=True,
            zone_name=zone_name
        )
        return data

    def enable_zone(self, zone_name: str) -> Dict[str, Any]:
        """
        Enable a DNS zone.

        Args:
            zone_name: Name of the zone to enable

        Returns:
            Result of zone enable operation
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone', '1', 'set',
            use_post=True,
            zone_name=zone_name,
            domain_name=zone_name,  # Required parameter
            zone_enable=True
        )
        return data

    def disable_zone(self, zone_name: str) -> Dict[str, Any]:
        """
        Disable a DNS zone.

        Args:
            zone_name: Name of the zone to disable

        Returns:
            Result of zone disable operation
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone', '1', 'set',
            use_post=True,
            zone_name=zone_name,
            domain_name=zone_name,  # Required parameter
            zone_enable=False
        )
        return data

    # ====================================================================
    # DNS RECORD MANAGEMENT
    # ====================================================================

    def list_records(self, zone_name: str) -> List[Dict[str, Any]]:
        """
        List all DNS records in a zone.

        Args:
            zone_name: Name of the DNS zone

        Returns:
            List of DNS records
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone.Record', '1', 'list',
            zone_name=zone_name,
            domain_name=zone_name  # API needs both parameters
        )

        records = data.get('items', [])
        return [{
            'record_key': record.get('record_key', ''),
            'name': record.get('rr_owner', ''),  # Owner name
            'type': record.get('rr_type', ''),   # Record type
            'rdata': record.get('rr_info', ''),  # Record data
            'ttl': record.get('rr_ttl', ''),     # TTL
            'full_record': record.get('full_record', '')  # Full DNS record string
        } for record in records]

    def create_record(self, zone_name: str, name: str, record_type: str,
                     rdata: str, ttl: int = 86400) -> Dict[str, Any]:
        """
        Create a new DNS record.

        Args:
            zone_name: Name of the DNS zone
            name: Record name (e.g., 'www', '@' for root, 'subdomain')
            record_type: Record type (A, AAAA, CNAME, MX, TXT, NS, PTR, SRV)
            rdata: Record data (e.g., IP address, hostname, text)
            ttl: Time to live in seconds

        Returns:
            Result of record creation
        """
        # Format rr_owner: needs to be full domain with trailing dot
        if not name.endswith('.'):
            if name == '@':
                rr_owner = f'"{zone_name}."'
            else:
                rr_owner = f'"{name}.{zone_name}."'
        else:
            rr_owner = f'"{name}"'

        data = self._make_request(
            'SYNO.DNSServer.Zone.Record', '1', 'create',
            use_post=True,
            zone_name=f'"{zone_name}"',
            domain_name=f'"{zone_name}"',
            rr_owner=rr_owner,
            rr_type=f'"{record_type}"',
            rr_info=f'"{rdata}"',
            rr_ttl=f'"{ttl}"'
        )
        return data

    def update_record(self, zone_name: str, record_key: str, name: Optional[str] = None,
                     record_type: Optional[str] = None, rdata: Optional[str] = None,
                     ttl: Optional[int] = None) -> Dict[str, Any]:
        """
        Update an existing DNS record.

        Args:
            zone_name: Name of the DNS zone
            record_key: Unique identifier of the record to update
            name: New record name (optional)
            record_type: New record type (optional)
            rdata: New record data (optional)
            ttl: New TTL value (optional)

        Returns:
            Result of record update
        """
        params = {
            'zone_name': f'"{zone_name}"',
            'domain_name': f'"{zone_name}"',
            'record_key': f'"{record_key}"'
        }

        if name is not None:
            # Format as full domain with trailing dot
            if not name.endswith('.'):
                if name == '@':
                    params['rr_owner'] = f'"{zone_name}."'
                else:
                    params['rr_owner'] = f'"{name}.{zone_name}."'
            else:
                params['rr_owner'] = f'"{name}"'
        if record_type is not None:
            params['rr_type'] = f'"{record_type}"'
        if rdata is not None:
            params['rr_info'] = f'"{rdata}"'
        if ttl is not None:
            params['rr_ttl'] = f'"{ttl}"'

        data = self._make_request(
            'SYNO.DNSServer.Zone.Record', '1', 'set',
            use_post=True,
            **params
        )
        return data

    def delete_record(self, zone_name: str, rr_owner: str, rr_type: str,
                     rr_info: str, rr_ttl: str = None) -> Dict[str, Any]:
        """
        Delete a DNS record.

        Args:
            zone_name: Name of the DNS zone
            rr_owner: Full record owner name (e.g., 'www.example.com.')
            rr_type: Record type (A, AAAA, CNAME, etc.)
            rr_info: Record data (IP address, hostname, etc.)
            rr_ttl: TTL value (optional, will be fetched if not provided)

        Returns:
            Result of record deletion
        """
        import json

        # Build the full record object needed for deletion
        # Note: We need the full_record field which is tab-separated
        full_record = f"{rr_owner}\t{rr_ttl or '86400'}\t{rr_type}\t{rr_info}"

        # The delete API requires an items array with the full record details
        items = [{
            "zone_name": zone_name,
            "domain_name": zone_name,
            "rr_owner": rr_owner,
            "rr_type": rr_type,
            "rr_ttl": rr_ttl or "86400",
            "rr_info": rr_info,
            "full_record": full_record
        }]

        data = self._make_request(
            'SYNO.DNSServer.Zone.Record', '1', 'delete',
            use_post=True,
            items=json.dumps(items)
        )
        return data

    # ====================================================================
    # SOA RECORD MANAGEMENT
    # ====================================================================

    def get_soa(self, zone_name: str) -> Dict[str, Any]:
        """
        Get SOA (Start of Authority) record for a zone.

        Args:
            zone_name: Name of the DNS zone

        Returns:
            SOA record details
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone.SOA', '1', 'get',
            zone_name=zone_name,
            domain_name=zone_name  # Required parameter
        )
        return data

    def update_soa(self, zone_name: str, primary_ns: Optional[str] = None,
                  admin_email: Optional[str] = None, serial: Optional[int] = None,
                  refresh: Optional[int] = None, retry: Optional[int] = None,
                  expire: Optional[int] = None, ttl: Optional[int] = None) -> Dict[str, Any]:
        """
        Update SOA record for a zone.

        Args:
            zone_name: Name of the DNS zone
            primary_ns: Primary nameserver
            admin_email: Administrator email
            serial: Serial number
            refresh: Refresh interval in seconds
            retry: Retry interval in seconds
            expire: Expire time in seconds
            ttl: Default TTL in seconds

        Returns:
            Result of SOA update
        """
        params = {'zone_name': zone_name}

        if primary_ns is not None:
            params['primary_ns'] = primary_ns
        if admin_email is not None:
            params['admin_email'] = admin_email
        if serial is not None:
            params['serial'] = serial
        if refresh is not None:
            params['refresh'] = refresh
        if retry is not None:
            params['retry'] = retry
        if expire is not None:
            params['expire'] = expire
        if ttl is not None:
            params['ttl'] = ttl

        data = self._make_request(
            'SYNO.DNSServer.Zone.SOA', '1', 'set',
            use_post=True,
            **params
        )
        return data

    # ====================================================================
    # ZONE CONFIGURATION
    # ====================================================================

    def get_master_zone_conf(self, zone_name: str) -> Dict[str, Any]:
        """
        Get master zone configuration.

        Args:
            zone_name: Name of the DNS zone

        Returns:
            Master zone configuration
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone.MasterZoneConf', '1', 'get',
            zone_name=zone_name
        )
        return data

    def get_forward_zone_conf(self, zone_name: str) -> Dict[str, Any]:
        """
        Get forward zone configuration.

        Args:
            zone_name: Name of the DNS zone

        Returns:
            Forward zone configuration
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone.ForwardZoneConf', '1', 'get',
            zone_name=zone_name
        )
        return data

    def export_zone(self, zone_name: str, file_type: str = 'master') -> str:
        """
        Export zone file content.

        Args:
            zone_name: Name of the DNS zone to export
            file_type: Type of zone file (master, forward, or slave)

        Returns:
            Zone file content as string
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone', '1', 'export',
            zone_name=zone_name,
            domain_name=zone_name,  # Required parameter
            file_type=file_type  # Required parameter
        )
        return data.get('zone_file', '')

    def import_zone(self, zone_name: str, zone_content: str) -> Dict[str, Any]:
        """
        Import zone file content.

        Args:
            zone_name: Name of the DNS zone
            zone_content: Zone file content to import

        Returns:
            Result of zone import
        """
        data = self._make_request(
            'SYNO.DNSServer.Zone', '1', 'import',
            use_post=True,
            zone_name=zone_name,
            zone_content=zone_content
        )
        return data

    # ====================================================================
    # DNS SERVER STATUS
    # ====================================================================

    def get_server_status(self) -> Dict[str, Any]:
        """
        Get DNS server daemon status.

        Returns:
            DNS server status information
        """
        data = self._make_request(
            'SYNO.DNSServer.DaemonStatus', '1', 'get'
        )
        return data
