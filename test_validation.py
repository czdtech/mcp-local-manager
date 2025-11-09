#!/usr/bin/env python3
"""
Test script to verify mcp_validation.py correctly detects invalid configuration
"""

import sys
import os
sys.path.append('/home/jiang/work/mcp-local-manager/bin')

from mcp_validation import validate_mcp_servers_config, MCPValidationError, MCPSchemaError

def test_invalid_config():
    """Test that validate_mcp_servers_config correctly detects invalid configuration"""
    
    invalid_config_path = "/home/jiang/work/mcp-local-manager/tests/fixtures/invalid-config.json"
    
    print("🧪 Testing mcp_validation.py with invalid configuration")
    print(f"📁 Testing file: {invalid_config_path}")
    print()
    
    try:
        # Attempt to validate the invalid configuration
        result = validate_mcp_servers_config(invalid_config_path)
        print("❌ ERROR: Validation should have failed but didn't!")
        print(f"Unexpected result: {result}")
        return False
        
    except MCPSchemaError as e:
        print("✅ SUCCESS: MCPSchemaError was raised correctly")
        print(f"🔍 Error message: {e}")
        return True
        
    except MCPValidationError as e:
        print("✅ SUCCESS: MCPValidationError was raised correctly")
        print(f"🔍 Error message: {e}")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Unexpected exception type: {type(e).__name__}")
        print(f"🔍 Error message: {e}")
        return False

def test_valid_config():
    """Test that validate_mcp_servers_config works correctly with valid configuration"""
    
    valid_config_path = "/home/jiang/work/mcp-local-manager/tests/fixtures/valid-config.json"
    
    print("🧪 Testing mcp_validation.py with valid configuration")
    print(f"📁 Testing file: {valid_config_path}")
    print()
    
    try:
        # Attempt to validate the valid configuration
        result = validate_mcp_servers_config(valid_config_path)
        print("✅ SUCCESS: Valid configuration passed validation")
        print(f"📋 Result: {result}")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: Valid configuration should not have failed: {type(e).__name__}")
        print(f"🔍 Error message: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("MCP VALIDATION TEST")
    print("=" * 60)
    print()
    
    # Test invalid config
    invalid_test_passed = test_invalid_config()
    print()
    print("-" * 40)
    print()
    
    # Test valid config for comparison
    valid_test_passed = test_valid_config()
    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Invalid config test: {'✅ PASSED' if invalid_test_passed else '❌ FAILED'}")
    print(f"Valid config test: {'✅ PASSED' if valid_test_passed else '❌ FAILED'}")
    print()
    
    if invalid_test_passed and valid_test_passed:
        print("🎉 All tests passed! mcp_validation.py is working correctly.")
        sys.exit(0)
    else:
        print("💥 Some tests failed. Please check the implementation.")
        sys.exit(1)
