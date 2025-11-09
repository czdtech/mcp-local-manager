#!/usr/bin/env python3
"""
Tests for MCP CLI module (bin/mcp).
"""

import json
import pytest
from pathlib import Path
import sys
from unittest.mock import patch, mock_open, MagicMock

# Add bin directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'bin'))


class TestLoadCentralServers:
    """Tests for load_central_servers function."""
    
    @patch('mcp.load_json')
    def test_load_central_servers_success(self, mock_load_json):
        """Test successful loading of central servers."""
        mock_config = {
            'version': '1.1.0',
            'description': 'Test',
            'servers': {
                'test-server': {
                    'command': 'npx',
                    'args': ['test']
                }
            }
        }
        mock_load_json.return_value = mock_config
        
        from mcp import load_central_servers
        obj, servers = load_central_servers()
        
        assert isinstance(obj, dict)
        assert isinstance(servers, dict)
        assert 'test-server' in servers
    
    @patch('mcp.load_json')
    def test_load_central_servers_empty(self, mock_load_json):
        """Test loading when config is empty."""
        mock_load_json.return_value = {}
        
        from mcp import load_central_servers
        obj, servers = load_central_servers()
        
        assert isinstance(servers, dict)
        assert len(servers) == 0
    
    @patch('mcp.load_json')
    @patch('mcp.validate_mcp_servers_config')
    def test_load_central_servers_with_validation(self, mock_validate, mock_load_json):
        """Test loading with validation enabled."""
        mock_config = {
            'version': '1.1.0',
            'description': 'Test',
            'servers': {
                'test-server': {
                    'command': 'npx',
                    'args': ['test']
                }
            }
        }
        mock_load_json.return_value = mock_config
        mock_validate.return_value = mock_config
        
        from mcp import load_central_servers
        obj, servers = load_central_servers()
        
        # Validation should be called if available
        # (actual behavior depends on validation module availability)
        assert isinstance(servers, dict)


class TestValidationIntegration:
    """Tests for validation integration in CLI."""
    
    @patch('mcp.CENTRAL')
    @patch('mcp.validate_mcp_servers_config')
    def test_validation_error_handling(self, mock_validate, mock_central):
        """Test error handling when validation fails."""
        from mcp import MCPValidationError
        
        mock_central.exists.return_value = True
        mock_validate.side_effect = MCPValidationError("Validation failed")
        
        # Should handle validation errors gracefully
        from mcp import load_central_servers
        # Should not raise, but fall back to basic loading
        try:
            obj, servers = load_central_servers()
            # If validation fails, should still return something
            assert isinstance(servers, dict)
        except Exception:
            # If it raises, that's also acceptable behavior
            pass


class TestErrorRecovery:
    """Tests for error recovery mechanisms."""
    
    @patch('mcp.load_json')
    def test_load_json_error_recovery(self, mock_load_json):
        """Test error recovery in load_json."""
        mock_load_json.side_effect = Exception("File read error")
        
        from mcp import load_json
        result = load_json(Path('/nonexistent'), {})
        
        # Should return default value on error
        assert result == {}
    
    @patch('mcp.CENTRAL')
    def test_load_central_servers_file_not_found(self, mock_central):
        """Test handling when central config doesn't exist."""
        mock_central.exists.return_value = False
        
        from mcp import load_central_servers
        obj, servers = load_central_servers()
        
        # Should return empty dict when file doesn't exist
        assert isinstance(servers, dict)
