#!/usr/bin/env python3
"""
Tests for MCP configuration validation module.
"""

import json
import pytest
from pathlib import Path
import sys

# Add bin directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'bin'))

from mcp_validation import (
    validate_mcp_servers_config,
    validate_server_config,
    validate_central_config_format,
    MCPValidationError,
    MCPSchemaError,
    MCPConfigError,
    get_validation_status,
    JSONSCHEMA_AVAILABLE
)


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / 'fixtures'


@pytest.fixture
def valid_config_path(fixtures_dir):
    """Return path to valid test configuration."""
    return fixtures_dir / 'valid-config.json'


@pytest.fixture
def invalid_config_path(fixtures_dir):
    """Return path to invalid test configuration."""
    return fixtures_dir / 'invalid-config.json'


@pytest.fixture
def malformed_config_path(fixtures_dir):
    """Return path to malformed JSON configuration."""
    return fixtures_dir / 'malformed.json'


class TestSchemaValidation:
    """Tests for JSON schema validation."""
    
    def test_validate_valid_config(self, valid_config_path):
        """Test validation of a valid configuration file."""
        config_data = validate_mcp_servers_config(valid_config_path)
        assert isinstance(config_data, dict)
        assert 'version' in config_data
        assert 'description' in config_data
        assert 'servers' in config_data
        assert 'test-server' in config_data['servers']
    
    def test_validate_invalid_config_missing_command(self, invalid_config_path):
        """Test validation fails for config with missing required field."""
        if JSONSCHEMA_AVAILABLE:
            with pytest.raises((MCPSchemaError, MCPConfigError)):
                validate_mcp_servers_config(invalid_config_path)
        else:
            # Without jsonschema, basic validation should still catch missing command
            with pytest.raises(MCPConfigError):
                validate_mcp_servers_config(invalid_config_path)
    
    def test_validate_malformed_json(self, malformed_config_path):
        """Test validation fails for malformed JSON."""
        with pytest.raises(MCPConfigError):
            validate_mcp_servers_config(malformed_config_path)
    
    def test_validate_nonexistent_file(self):
        """Test validation fails for non-existent file."""
        nonexistent = Path('/nonexistent/path/config.json')
        with pytest.raises(FileNotFoundError):
            validate_mcp_servers_config(nonexistent)


class TestServerConfigValidation:
    """Tests for individual server configuration validation."""
    
    def test_validate_valid_server(self):
        """Test validation of a valid server configuration."""
        server_info = {
            'command': 'npx',
            'args': ['-y', 'test@latest'],
            'env': {'VAR': 'value'},
            'enabled': True
        }
        # Should not raise
        validate_server_config('test-server', server_info)
    
    def test_validate_server_missing_command(self):
        """Test validation fails for server without command."""
        server_info = {'enabled': True}
        with pytest.raises(MCPValidationError) as exc_info:
            validate_server_config('test-server', server_info)
        assert 'command' in str(exc_info.value).lower()
    
    def test_validate_server_empty_command(self):
        """Test validation fails for server with empty command."""
        server_info = {'command': ''}
        with pytest.raises(MCPValidationError):
            validate_server_config('test-server', server_info)
    
    def test_validate_server_invalid_args(self):
        """Test validation fails for server with invalid args."""
        server_info = {
            'command': 'npx',
            'args': [123]  # Should be string
        }
        with pytest.raises(MCPValidationError):
            validate_server_config('test-server', server_info)
    
    def test_validate_server_invalid_env(self):
        """Test validation fails for server with invalid env."""
        server_info = {
            'command': 'npx',
            'env': {'VAR': 123}  # Should be string
        }
        with pytest.raises(MCPValidationError):
            validate_server_config('test-server', server_info)
    
    def test_validate_server_invalid_enabled(self):
        """Test validation fails for server with invalid enabled value."""
        server_info = {
            'command': 'npx',
            'enabled': 'yes'  # Should be boolean
        }
        with pytest.raises(MCPValidationError):
            validate_server_config('test-server', server_info)


class TestConfigFormatValidation:
    """Tests for central configuration format validation."""
    
    def test_validate_valid_format(self):
        """Test validation of valid configuration format."""
        config_data = {
            'version': '1.1.0',
            'description': 'Test config',
            'servers': {
                'test': {
                    'command': 'npx',
                    'args': ['test']
                }
            }
        }
        result = validate_central_config_format(config_data)
        assert result == config_data
    
    def test_validate_missing_version(self):
        """Test validation fails for missing version."""
        config_data = {
            'description': 'Test',
            'servers': {}
        }
        with pytest.raises(MCPConfigError):
            validate_central_config_format(config_data)
    
    def test_validate_missing_description(self):
        """Test validation fails for missing description."""
        config_data = {
            'version': '1.0',
            'servers': {}
        }
        with pytest.raises(MCPConfigError):
            validate_central_config_format(config_data)
    
    def test_validate_missing_servers(self):
        """Test validation fails for missing servers."""
        config_data = {
            'version': '1.0',
            'description': 'Test'
        }
        with pytest.raises(MCPConfigError):
            validate_central_config_format(config_data)


class TestValidationStatus:
    """Tests for validation status reporting."""
    
    def test_get_validation_status(self):
        """Test getting validation status information."""
        status = get_validation_status()
        assert isinstance(status, dict)
        assert 'jsonschema_available' in status
        assert 'schema_validation_enabled' in status
        assert 'validation_functions' in status
        assert status['jsonschema_available'] == JSONSCHEMA_AVAILABLE


class TestGracefulFallback:
    """Tests for graceful fallback when jsonschema is not available."""
    
    def test_validation_works_without_jsonschema(self, valid_config_path, monkeypatch):
        """Test that validation still works without jsonschema."""
        # Mock jsonschema as unavailable
        import mcp_validation
        original_available = mcp_validation.JSONSCHEMA_AVAILABLE
        mcp_validation.JSONSCHEMA_AVAILABLE = False
        
        try:
            # Should still work with basic validation
            config_data = validate_mcp_servers_config(valid_config_path)
            assert isinstance(config_data, dict)
        finally:
            mcp_validation.JSONSCHEMA_AVAILABLE = original_available
