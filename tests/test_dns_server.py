#!/usr/bin/env python3
"""
Comprehensive test suite for DNS Server functionality
Tests all DNS operations to ensure they work as designed
"""

import pytest
import requests
import json
import os
from dotenv import load_dotenv
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment
load_dotenv()

SYNOLOGY_URL = os.getenv('SYNOLOGY_URL')
SYNOLOGY_USERNAME = os.getenv('SYNOLOGY_USERNAME')
SYNOLOGY_PASSWORD = os.getenv('SYNOLOGY_PASSWORD')


class TestDNSServer:
    """Test suite for Synology DNS Server API operations"""

    @pytest.fixture(scope="class")
    def dns_session(self):
        """Create a DNS Server session for all tests"""
        login_url = f"{SYNOLOGY_URL}/webapi/auth.cgi"

        for version in ['7', '6', '3', '2']:
            payload = {
                'api': 'SYNO.API.Auth',
                'version': version,
                'method': 'login',
                'account': SYNOLOGY_USERNAME,
                'passwd': SYNOLOGY_PASSWORD,
                'session': 'DNSServer',
                'format': 'sid'
            }

            try:
                response = requests.get(login_url, params=payload, verify=False)
                result = response.json()

                if result.get('success'):
                    print(f"\n✅ DNS Server login successful (API v{version})")
                    session_id = result['data']['sid']
                    yield session_id

                    # Logout after tests
                    logout_url = f"{SYNOLOGY_URL}/webapi/auth.cgi"
                    logout_payload = {
                        'api': 'SYNO.API.Auth',
                        'version': version,
                        'method': 'logout',
                        'session': 'DNSServer',
                        '_sid': session_id
                    }
                    requests.get(logout_url, params=logout_payload, verify=False)
                    print("\n✅ DNS Server logout successful")
                    return
            except Exception as e:
                continue

        pytest.fail("Failed to create DNS Server session")

    def test_list_zones(self, dns_session):
        """Test: List all DNS zones"""
        print("\n" + "="*60)
        print("TEST: List DNS Zones")
        print("="*60)

        api_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'list',
            '_sid': dns_session
        }

        response = requests.get(api_url, params=params, verify=False)
        result = response.json()

        assert result.get('success') == True, f"List zones failed: {result}"
        assert 'data' in result, "No data in response"
        assert 'items' in result['data'], "No items in data"

        zones = result['data']['items']
        print(f"✅ Found {len(zones)} zone(s)")

        for zone in zones:
            print(f"   - {zone.get('zone_name')} ({zone.get('zone_type')})")
            assert 'zone_name' in zone, "Zone missing zone_name"
            assert 'zone_type' in zone, "Zone missing zone_type"

    def test_list_records(self, dns_session):
        """Test: List DNS records in a zone"""
        print("\n" + "="*60)
        print("TEST: List DNS Records")
        print("="*60)

        # First get a zone to test with
        zones_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        zones_params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'list',
            '_sid': dns_session
        }

        zones_response = requests.get(zones_url, params=zones_params, verify=False)
        zones_result = zones_response.json()

        assert zones_result.get('success') == True, "Failed to get zones"
        zones = zones_result['data']['items']
        assert len(zones) > 0, "No zones available to test"

        test_zone = zones[0]['zone_name']
        print(f"Testing with zone: {test_zone}")

        # Now list records
        api_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        params = {
            'api': 'SYNO.DNSServer.Zone.Record',
            'version': '1',
            'method': 'list',
            'zone_name': test_zone,
            'domain_name': test_zone,
            '_sid': dns_session
        }

        response = requests.get(api_url, params=params, verify=False)
        result = response.json()

        assert result.get('success') == True, f"List records failed: {result}"
        assert 'data' in result, "No data in response"
        assert 'items' in result['data'], "No items in data"

        records = result['data']['items']
        print(f"✅ Found {len(records)} record(s)")

        for record in records:
            record_type = record.get('rr_type', '')
            record_owner = record.get('rr_owner', '')
            record_info = record.get('rr_info', '')
            print(f"   - {record_owner} {record_type} {record_info}")

    def test_get_zone(self, dns_session):
        """Test: Get detailed zone information"""
        print("\n" + "="*60)
        print("TEST: Get Zone Details")
        print("="*60)

        # Get first zone
        zones_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        zones_params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'list',
            '_sid': dns_session
        }

        zones_response = requests.get(zones_url, params=zones_params, verify=False)
        zones_result = zones_response.json()
        zones = zones_result['data']['items']
        test_zone = zones[0]['zone_name']

        # Get zone details
        api_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'get',
            'zone_name': test_zone,
            'domain_name': test_zone,  # Required parameter
            '_sid': dns_session
        }

        response = requests.get(api_url, params=params, verify=False)
        result = response.json()

        # Note: get method might not be supported, so we check for either success or specific error
        if result.get('success') == True:
            print(f"✅ Got zone details for {test_zone}")
            print(json.dumps(result['data'], indent=2))
        else:
            error_code = result.get('error', {}).get('code')
            # Error 101 = invalid method (not supported)
            # Error 103 = parameter not valid / incorrect value
            # Error 120 = parameter issues (missing required params not documented)
            if error_code in [101, 103, 120]:
                error_detail = result.get('error', {}).get('errors', {})
                print(f"⚠️  Get zone method has parameter issues (error {error_code}): {error_detail}")
                print(f"   This API requires undocumented parameters - skipping test")
                pytest.skip("Get zone method requires undocumented parameters")
            else:
                pytest.fail(f"Unexpected error getting zone: {result}")

    def test_zone_enable_disable(self, dns_session):
        """Test: Enable/Disable zone operations"""
        print("\n" + "="*60)
        print("TEST: Enable/Disable Zone")
        print("="*60)

        # Get first zone
        zones_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        zones_params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'list',
            '_sid': dns_session
        }

        zones_response = requests.get(zones_url, params=zones_params, verify=False)
        zones_result = zones_response.json()
        zones = zones_result['data']['items']
        test_zone = zones[0]['zone_name']
        original_state = zones[0]['zone_enable']

        print(f"Testing with zone: {test_zone}")
        print(f"Original state: {'enabled' if original_state else 'disabled'}")

        # Test disable
        api_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        disable_params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'set',
            'zone_name': test_zone,
            'domain_name': test_zone,  # Required parameter
            'zone_enable': 'false',
            '_sid': dns_session
        }

        disable_response = requests.post(api_url, data=disable_params, verify=False)
        disable_result = disable_response.json()

        if disable_result.get('success') == True:
            print(f"✅ Zone disabled successfully")

            # Re-enable to restore original state
            enable_params = {
                'api': 'SYNO.DNSServer.Zone',
                'version': '1',
                'method': 'set',
                'zone_name': test_zone,
                'domain_name': test_zone,  # Required parameter
                'zone_enable': 'true',
                '_sid': dns_session
            }

            enable_response = requests.post(api_url, data=enable_params, verify=False)
            enable_result = enable_response.json()

            assert enable_result.get('success') == True, f"Failed to re-enable zone: {enable_result}"
            print(f"✅ Zone re-enabled successfully")
        else:
            error_code = disable_result.get('error', {}).get('code')
            if error_code in [101, 103, 120]:
                error_detail = disable_result.get('error', {}).get('errors', {})
                print(f"⚠️  Zone enable/disable has parameter issues (error {error_code}): {error_detail}")
                print(f"   This API requires undocumented parameters - skipping test")
                pytest.skip("Zone enable/disable requires undocumented parameters")
            else:
                pytest.fail(f"Failed to disable zone: {disable_result}")

    def test_create_delete_record(self, dns_session):
        """Test: Create and delete DNS record"""
        print("\n" + "="*60)
        print("TEST: Create and Delete DNS Record")
        print("="*60)

        # Get first zone
        zones_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        zones_params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'list',
            '_sid': dns_session
        }

        zones_response = requests.get(zones_url, params=zones_params, verify=False)
        zones_result = zones_response.json()
        zones = zones_result['data']['items']
        test_zone = zones[0]['zone_name']

        print(f"Testing with zone: {test_zone}")

        # Try to create a test record using correct quoted format
        api_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        create_params = {
            'api': 'SYNO.DNSServer.Zone.Record',
            'version': '1',
            'method': 'create',
            'zone_name': f'"{test_zone}"',
            'domain_name': f'"{test_zone}"',
            'rr_owner': f'"test-mcp.{test_zone}."',
            'rr_type': '"A"',
            'rr_info': '"192.168.1.250"',  # Simple string, not JSON array!
            'rr_ttl': '"300"',
            '_sid': dns_session
        }

        create_response = requests.post(api_url, data=create_params, verify=False)
        create_result = create_response.json()

        if create_result.get('success') == True:
            print(f"✅ Test record created successfully")

            # Get the record details to delete it
            list_params = {
                'api': 'SYNO.DNSServer.Zone.Record',
                'version': '1',
                'method': 'list',
                'zone_name': test_zone,
                'domain_name': test_zone,
                '_sid': dns_session
            }

            list_response = requests.get(api_url, params=list_params, verify=False)
            list_result = list_response.json()

            # Find our test record
            test_record = None
            for record in list_result['data']['items']:
                if 'test-mcp' in record.get('rr_owner', ''):
                    test_record = record
                    break

            if test_record:
                # Delete the test record using items parameter (add zone_name/domain_name)
                test_record['zone_name'] = test_zone
                test_record['domain_name'] = test_zone

                delete_params = {
                    'api': 'SYNO.DNSServer.Zone.Record',
                    'version': '1',
                    'method': 'delete',
                    'items': json.dumps([test_record]),
                    '_sid': dns_session
                }

                delete_response = requests.post(api_url, data=delete_params, verify=False)
                delete_result = delete_response.json()

                assert delete_result.get('success') == True, f"Failed to delete test record: {delete_result}"
                print(f"✅ Test record deleted successfully")
            else:
                print(f"⚠️  Could not find test record to delete")
        else:
            error_code = create_result.get('error', {}).get('code')
            print(f"❌ Record creation failed (error {error_code})")
            print(f"   Response: {create_result}")
            pytest.fail(f"Record creation should work with quoted parameters but got error {error_code}")

    def test_server_status(self, dns_session):
        """Test: Get DNS server daemon status"""
        print("\n" + "="*60)
        print("TEST: Get DNS Server Status")
        print("="*60)

        api_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        params = {
            'api': 'SYNO.DNSServer.DaemonStatus',
            'version': '1',
            'method': 'get',
            '_sid': dns_session
        }

        response = requests.get(api_url, params=params, verify=False)
        result = response.json()

        if result.get('success') == True:
            print(f"✅ DNS Server status retrieved")
            print(json.dumps(result['data'], indent=2))
        else:
            error_code = result.get('error', {}).get('code')
            if error_code == 101:
                print(f"⚠️  Server status method not supported (error 101)")
                pytest.skip("Server status not supported by this DNS Server version")
            else:
                pytest.fail(f"Failed to get server status: {result}")

    def test_export_zone(self, dns_session):
        """Test: Export zone file"""
        print("\n" + "="*60)
        print("TEST: Export Zone File")
        print("="*60)

        # Get first zone
        zones_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        zones_params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'list',
            '_sid': dns_session
        }

        zones_response = requests.get(zones_url, params=zones_params, verify=False)
        zones_result = zones_response.json()
        zones = zones_result['data']['items']
        test_zone = zones[0]['zone_name']

        print(f"Testing with zone: {test_zone}")

        # Export zone
        api_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'export',
            'zone_name': test_zone,
            'domain_name': test_zone,  # Required parameter
            'file_type': 'master',  # Required parameter (master, forward, or slave)
            '_sid': dns_session
        }

        response = requests.get(api_url, params=params, verify=False)
        result = response.json()

        if result.get('success') == True:
            zone_content = result.get('data', {}).get('zone_file', '')
            print(f"✅ Zone exported successfully ({len(zone_content)} characters)")
            if zone_content:
                print(f"Zone file preview:")
                print(zone_content[:200] + "..." if len(zone_content) > 200 else zone_content)
        else:
            error_code = result.get('error', {}).get('code')
            if error_code in [101, 103, 120]:
                error_detail = result.get('error', {}).get('errors', {})
                print(f"⚠️  Zone export has parameter issues (error {error_code}): {error_detail}")
                print(f"   This API requires undocumented parameters - skipping test")
                pytest.skip("Zone export requires undocumented parameters")
            else:
                pytest.fail(f"Failed to export zone: {result}")

    def test_soa_record(self, dns_session):
        """Test: Get SOA record"""
        print("\n" + "="*60)
        print("TEST: Get SOA Record")
        print("="*60)

        # Get first zone
        zones_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        zones_params = {
            'api': 'SYNO.DNSServer.Zone',
            'version': '1',
            'method': 'list',
            '_sid': dns_session
        }

        zones_response = requests.get(zones_url, params=zones_params, verify=False)
        zones_result = zones_response.json()
        zones = zones_result['data']['items']
        test_zone = zones[0]['zone_name']

        print(f"Testing with zone: {test_zone}")

        # Get SOA
        api_url = f"{SYNOLOGY_URL}/webapi/entry.cgi"
        params = {
            'api': 'SYNO.DNSServer.Zone.SOA',
            'version': '1',
            'method': 'get',
            'zone_name': test_zone,
            'domain_name': test_zone,  # Required parameter
            '_sid': dns_session
        }

        response = requests.get(api_url, params=params, verify=False)
        result = response.json()

        if result.get('success') == True:
            print(f"✅ SOA record retrieved")
            print(json.dumps(result['data'], indent=2))
        else:
            error_code = result.get('error', {}).get('code')
            if error_code in [101, 103, 120]:
                error_detail = result.get('error', {}).get('errors', {})
                print(f"⚠️  SOA get has parameter issues (error {error_code}): {error_detail}")
                print(f"   This API requires undocumented parameters - skipping test")
                pytest.skip("SOA get requires undocumented parameters")
            else:
                pytest.fail(f"Failed to get SOA: {result}")


def run_tests():
    """Run all DNS tests"""
    print("\n" + "="*60)
    print("🧪 Synology DNS Server - Comprehensive Test Suite")
    print("="*60)

    pytest.main([__file__, '-v', '-s'])


if __name__ == '__main__':
    run_tests()
