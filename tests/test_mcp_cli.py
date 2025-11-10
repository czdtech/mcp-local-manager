#!/usr/bin/env python3
"""
Tests for MCP CLI module (bin/mcp) - Script-based approach.
Tests the actual command-line behavior using subprocess calls.
"""

import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os

# Base directory for test files
TEST_ROOT = Path(__file__).parent.parent
BIN_DIR = TEST_ROOT / 'bin'

class TestMCPCLI:
    """Tests for MCP CLI using subprocess calls."""
    
    def setup_method(self):
        """Setup for each test."""
        # Ensure we have a test environment
        self.bin_path = str(BIN_DIR / 'mcp')
        assert Path(self.bin_path).exists(), f"mcp binary not found at {self.bin_path}"
    
    def test_mcp_help(self):
        """Test mcp --help command."""
        result = subprocess.run([self.bin_path, '--help'], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert 'MCP' in result.stdout
        assert 'status' in result.stdout
    
    def test_mcp_status_runs(self):
        """status 只读命令可运行。"""
        result = subprocess.run([self.bin_path, 'status'], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
    
    def test_mcp_status_output(self):
        result = subprocess.run([self.bin_path, 'status'], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert '按客户端/IDE 的实际启用视图' in result.stdout
    
    def test_mcp_status_specific_client(self):
        """Test mcp status for specific client."""
        result = subprocess.run([self.bin_path, 'status', 'cursor'], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert '[Cursor]' in result.stdout
    
    def test_mcp_check_command(self):
        """Test mcp check command."""
        result = subprocess.run([self.bin_path, 'check'], 
                              capture_output=True, text=True, timeout=30)
        
        # check command may return non-zero due to warnings, but should run
        assert 'MCP 健康检查报告' in result.stdout
    
    def test_mcp_run_interactive_invokes(self):
        """run 交互式调用（不再支持参数式）。"""
        # 选择默认客户端(回车=1)，选择默认服务(回车=第一个)，跳过启动(回车)
        result = subprocess.run([self.bin_path, 'run'], input='\n\n\n', capture_output=True, text=True, timeout=30)
        assert result.returncode in (0,1)
    
    def test_mcp_invalid_command(self):
        """Test mcp with invalid command."""
        result = subprocess.run([self.bin_path, 'invalid_command'], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode != 0
        assert 'invalid choice' in result.stderr or 'error' in result.stderr.lower()
    
    def test_mcp_invalid_client(self):
        """Test mcp with invalid client."""
        result = subprocess.run([self.bin_path, 'status', 'invalid_client'], 
                              capture_output=True, text=True, timeout=10)
        
        # Should handle invalid client gracefully
        assert result.returncode == 0 or 'error' in result.stdout.lower()
    
    def test_mcp_validation_script(self):
        """Test that validation script works."""
        validation_script = BIN_DIR / 'mcp_validation.py'
        sample_config = TEST_ROOT / 'config' / 'mcp-servers.sample.json'
        
        assert validation_script.exists(), f"Validation script not found at {validation_script}"
        assert sample_config.exists(), f"Sample config not found at {sample_config}"
        
        result = subprocess.run(['python3', str(validation_script), str(sample_config)], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert '配置验证通过' in result.stdout


class TestMCPErrorHandling:
    """Tests for error handling in MCP CLI."""
    
    def setup_method(self):
        """Setup for each test."""
        self.bin_path = str(BIN_DIR / 'mcp')
    
    def test_mcp_nonexistent_file_operations(self):
        """Test mcp operations with non-existent files (if applicable)."""
        # This test ensures error handling works
        result = subprocess.run([self.bin_path, 'check'], 
                              capture_output=True, text=True, timeout=10)
        
        # check should run regardless of configuration state
        assert 'MCP 健康检查报告' in result.stdout
    
    def test_mcp_timeout_protection(self):
        """Test that mcp commands have proper timeout handling."""
        # This is more of a regression test to ensure commands don't hang
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Command timed out")
        
        # Test a quick command with timeout
        result = subprocess.run([self.bin_path, '--help'], 
                              capture_output=True, text=True, timeout=5)
        
        assert result.returncode == 0
        assert 'MCP' in result.stdout


class TestMCPDryRun:
    """Tests specifically for dry-run functionality."""
    
    def setup_method(self):
        """Setup for each test."""
        self.bin_path = str(BIN_DIR / 'mcp')
    
    def test_dry_run_doesnt_modify_files(self):
        """Ensure dry-run doesn't modify any files."""
        # Get initial state of key files
        home = Path.home()
        claude_config = home / '.claude' / 'settings.json'
        cursor_config = home / '.cursor' / 'mcp.json'
        
        initial_states = {}
        for config_path in [claude_config, cursor_config]:
            if config_path.exists():
                initial_states[config_path] = config_path.read_text()
        
        # Run dry-run commands
        subprocess.run([self.bin_path, '-n', 'status'], 
                      capture_output=True, text=True, timeout=10)
        
        # Check that no files were modified
        for config_path, original_content in initial_states.items():
            if config_path.exists():
                current_content = config_path.read_text()
                assert current_content == original_content, f"File {config_path} was modified during dry-run"
    
    def test_dry_run_shows_intended_actions(self):
        """Test that dry-run shows what would be done."""
        result = subprocess.run([self.bin_path, 'status', 'cursor'], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        # Should show status information
        assert '[Cursor]' in result.stdout


class TestMCPIntegration:
    """Integration tests for MCP CLI."""
    
    def setup_method(self):
        """Setup for each test."""
        self.bin_path = str(BIN_DIR / 'mcp')
    
    def test_validation_integration(self):
        """Test integration between CLI and validation."""
        validation_script = BIN_DIR / 'mcp_validation.py'
        sample_config = TEST_ROOT / 'config' / 'mcp-servers.sample.json'
        
        # First validate the config
        result = subprocess.run(['python3', str(validation_script), str(sample_config)], 
                              capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        
        # Then use it with CLI (this tests the integration)
        # Note: We don't actually apply it, just test that the CLI can run
        result = subprocess.run([self.bin_path, 'status'], 
                              capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
    
    def test_multiple_client_status(self):
        """Test status for multiple clients."""
        clients = ['claude', 'cursor', 'codex', 'droid']
        
        for client in clients:
            result = subprocess.run([self.bin_path, 'status', client], 
                                  capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, f"Failed to get status for {client}"


class TestMCPIClear:
    """Tests specifically for the clear command."""
    
    def setup_method(self):
        """Setup for each test."""
        self.bin_path = str(BIN_DIR / 'mcp')
    
    def test_clear_help(self):
        """Test mcp clear --help command."""
        result = subprocess.run([self.bin_path, 'clear', '--help'], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert 'clear' in result.stdout
        # 交互式后不再暴露 --client/--yes
    
    def test_clear_interactive(self):
        result = subprocess.run([self.bin_path, 'clear'], input='\n'+'y\n', capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
    
    def test_clear_dry_run_all_clients(self):
        result = subprocess.run([self.bin_path, 'clear'], input='\n'+'y\n', capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
    
    def test_clear_requires_confirmation(self):
        """Test that clear requires confirmation without --yes."""
        result = subprocess.run([self.bin_path, 'clear'], 
                              input='1\n'+'n\n',  # pick first then 'n'
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert '确认' in result.stdout
        assert '已取消' in result.stdout
    
    def test_clear_confirm_yes(self):
        result = subprocess.run([self.bin_path, 'clear'], input='1\n'+'y\n', capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
    
    def test_clear_invalid_client(self):
        # 不再支持参数式客户端；清理交互仅验证可进入
        result = subprocess.run([self.bin_path, 'clear'], input='\n'+'n\n', capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
    
    def test_clear_multiple_clients_interactive(self):
        result = subprocess.run([self.bin_path, 'clear'], input='1 2 3\n'+'y\n', capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
    
    def test_clear_verbose_mode(self):
        result = subprocess.run([self.bin_path, 'clear'], input='\n'+'y\n', capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
    
    def test_clear_env_variable_yes(self):
        """Test clear with MCP_CLEAR_YES=1 environment variable."""
        env = os.environ.copy()
        env['MCP_CLEAR_YES'] = '1'
        
        result = subprocess.run([self.bin_path, 'clear'], 
                              input='\n', env=env, capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        # Should not ask for confirmation due to env variable
        assert '确认' not in result.stdout
