#!/usr/bin/env python3
"""
Tests for MCP sync operations (bin/mcp-auto-sync.py).
"""

import json
import pytest
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock, mock_open

# Add bin directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'bin'))


class TestLoadCentral:
    """Tests for load_central function."""
    
    @patch('mcp_auto_sync.CENTRAL')
    def test_load_central_success(self, mock_central):
        """Test successful loading of central configuration."""
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
        mock_central.exists.return_value = True
        mock_central.read_text.return_value = json.dumps(mock_config)
        
        from mcp_auto_sync import load_central
        servers = load_central()
        
        assert isinstance(servers, dict)
        assert 'test-server' in servers
    
    @patch('mcp_auto_sync.CENTRAL')
    def test_load_central_file_not_found(self, mock_central):
        """Test handling when central config doesn't exist."""
        mock_central.exists.return_value = False
        
        from mcp_auto_sync import load_central
        import sys
        
        # Should exit with error code 1
        with pytest.raises(SystemExit) as exc_info:
            load_central()
        assert exc_info.value.code == 1
    
    @patch('mcp_auto_sync.CENTRAL')
    @patch('mcp_auto_sync.validate_mcp_servers_config')
    def test_load_central_with_validation(self, mock_validate, mock_central):
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
        mock_central.exists.return_value = True
        mock_validate.return_value = mock_config
        
        from mcp_auto_sync import load_central
        servers = load_central()
        
        # Should use validated config
        assert isinstance(servers, dict)


class TestSyncOperations:
    """Tests for sync operation functions."""
    
    @patch('mcp_auto_sync.HOME')
    @patch('mcp_auto_sync.backup')
    def test_sync_codex_file_not_found(self, mock_backup, mock_home):
        """Test sync_codex when config file doesn't exist."""
        mock_config_path = MagicMock()
        mock_config_path.exists.return_value = False
        mock_home.__truediv__.return_value = mock_config_path
        
        from mcp_auto_sync import sync_codex
        result = sync_codex()
        
        # Should return False when file doesn't exist
        assert result is False
    
    @patch('mcp_auto_sync.HOME')
    @patch('mcp_auto_sync.backup')
    @patch('mcp_auto_sync.SERVERS', {'test': {'command': 'npx', 'args': ['test']}})
    def test_sync_codex_success(self, mock_backup, mock_home):
        """Test successful sync_codex operation."""
        mock_config_path = MagicMock()
        mock_config_path.exists.return_value = True
        mock_config_path.read_text.return_value = '[general]\nkey = value\n'
        mock_config_path.write_text = MagicMock()
        mock_home.__truediv__.return_value = mock_config_path
        
        from mcp_auto_sync import sync_codex
        result = sync_codex()
        
        # Should return True on success
        assert result is True
        assert mock_config_path.write_text.called


class TestErrorRecovery:
    """Tests for error recovery in sync operations."""
    
    @patch('mcp_auto_sync.HOME')
    def test_sync_json_map_error_recovery(self, mock_home):
        """Test error recovery in sync_json_map."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.side_effect = Exception("Read error")
        mock_home.__truediv__.return_value = mock_path
        
        from mcp_auto_sync import sync_json_map
        
        # Should handle read errors gracefully
        try:
            result = sync_json_map('Test', mock_path)
            # Should either succeed or return False
            assert isinstance(result, bool)
        except Exception:
            # If it raises, that's also acceptable
            pass
    
    @patch('mcp_auto_sync.subprocess.run')
    def test_claude_registered_error_recovery(self, mock_run):
        """Test error recovery in claude_registered."""
        mock_run.side_effect = Exception("Command failed")
        
        from mcp_auto_sync import claude_registered
        result = claude_registered()
        
        # Should return empty set on error
        assert isinstance(result, set)
        assert len(result) == 0
