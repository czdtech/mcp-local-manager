#!/usr/bin/env python3
"""
MCP Configuration Validation Module

Provides schema validation and configuration validation for MCP server configurations
with graceful fallback when jsonschema is not available.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Union

# Try to import jsonschema, fall back gracefully if not available
try:
    import jsonschema
    from jsonschema import validate, ValidationError as JSONSchemaValidationError
    from jsonschema import Draft7Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    JSONSchemaValidationError = Exception


# Custom exception classes
class MCPValidationError(Exception):
    """Base exception for MCP configuration validation errors."""
    pass


class MCPSchemaError(MCPValidationError):
    """Exception raised when JSON schema validation fails."""
    pass


class MCPConfigError(MCPValidationError):
    """Exception raised when configuration content validation fails."""
    pass


def format_validation_error(error: Exception) -> str:
    """Format validation error messages in Chinese for better user experience.
    
    Args:
        error: The exception to format
        
    Returns:
        Formatted error message in Chinese
    """
    if isinstance(error, JSONSchemaValidationError):
        if hasattr(error, 'path') and error.path:
            path_str = ' → '.join(str(p) for p in error.path)
            return f"❌ Schema 验证失败 - {path_str}: {error.message}"
        else:
            return f"❌ Schema 验证失败: {error.message}"
    elif isinstance(error, MCPValidationError):
        return f"❌ 配置验证错误: {str(error)}"
    else:
        return f"❌ 验证错误: {str(error)}"


def validate_mcp_servers_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    """Validate MCP servers configuration using JSON schema.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Parsed configuration dictionary
        
    Raises:
        MCPSchemaError: If schema validation fails
        MCPConfigError: If configuration content is invalid
        FileNotFoundError: If configuration file doesn't exist
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    # Read and parse JSON
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        raise MCPConfigError(f"JSON 格式错误: {e}")
    except Exception as e:
        raise MCPConfigError(f"读取配置文件失败: {e}")
    
    # If jsonschema is available, perform schema validation
    if JSONSCHEMA_AVAILABLE:
        try:
            schema_path = Path(__file__).parent.parent / 'config' / 'mcp-servers.schema.json'
            if schema_path.exists():
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                
                # Validate against schema
                validate(instance=config_data, schema=schema)
                
            else:
                print(f"⚠️  警告: Schema 文件不存在: {schema_path}", file=sys.stderr)
        except JSONSchemaValidationError as e:
            raise MCPSchemaError(f"Schema 验证失败: {e}")
        except Exception as e:
            print(f"⚠️  警告: Schema 验证过程出错: {e}", file=sys.stderr)
    else:
        print("ℹ️  信息: jsonschema 库未安装，跳过 schema 验证", file=sys.stderr)
    
    # 无论是否安装 jsonschema，均执行基础内容校验，确保在缺少 schema 库时也能拦截明显错误
    try:
        config_data = validate_central_config_format(config_data)
    except MCPValidationError as e:
        # 统一异常类型
        raise MCPConfigError(str(e))
    
    return config_data


def validate_server_config(server_name: str, server_info: Dict[str, Any]) -> None:
    """Validate individual server configuration.
    
    Args:
        server_name: Name of the server
        server_info: Server configuration dictionary
        
    Raises:
        MCPValidationError: If server configuration is invalid
    """
    if not isinstance(server_info, dict):
        raise MCPValidationError(f"服务器 '{server_name}' 配置必须是对象格式")
    
    # Check required fields
    if 'command' not in server_info:
        raise MCPValidationError(f"服务器 '{server_name}' 缺少必需的 'command' 字段")
    
    command = server_info.get('command')
    if not isinstance(command, str) or not command.strip():
        raise MCPValidationError(f"服务器 '{server_name}' 的 'command' 必须是非空字符串")
    
    # Validate optional fields
    if 'args' in server_info:
        args = server_info['args']
        if not isinstance(args, list):
            raise MCPValidationError(f"服务器 '{server_name}' 的 'args' 必须是数组")
        
        # Check that all args are strings
        for i, arg in enumerate(args):
            if not isinstance(arg, str):
                raise MCPValidationError(f"服务器 '{server_name}' 的 'args[{i}]' 必须是字符串")
    
    if 'env' in server_info:
        env = server_info['env']
        if not isinstance(env, dict):
            raise MCPValidationError(f"服务器 '{server_name}' 的 'env' 必须是对象")
        
        # Check that all env values are strings
        for key, value in env.items():
            if not isinstance(value, str):
                raise MCPValidationError(f"服务器 '{server_name}' 的环境变量 '{key}' 必须是字符串")
    
    if 'enabled' in server_info:
        enabled = server_info['enabled']
        if not isinstance(enabled, bool):
            raise MCPValidationError(f"服务器 '{server_name}' 的 'enabled' 必须是布尔值")
    
    if 'type' in server_info:
        server_type = server_info['type']
        if not isinstance(server_type, str) or not server_type.strip():
            raise MCPValidationError(f"服务器 '{server_name}' 的 'type' 必须是非空字符串")
    
    if 'url' in server_info:
        url = server_info['url']
        if not isinstance(url, str) or not url.strip():
            raise MCPValidationError(f"服务器 '{server_name}' 的 'url' 必须是非空字符串")
    
    if 'headers' in server_info:
        headers = server_info['headers']
        if not isinstance(headers, dict):
            raise MCPValidationError(f"服务器 '{server_name}' 的 'headers' 必须是对象")
        
        # Check that all header values are strings
        for key, value in headers.items():
            if not isinstance(value, str):
                raise MCPValidationError(f"服务器 '{server_name}' 的 HTTP 头 '{key}' 必须是字符串")


def validate_central_config_format(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the central configuration structure and content.
    
    Args:
        config_data: Configuration dictionary to validate
        
    Returns:
        Validated configuration data
        
    Raises:
        MCPConfigError: If configuration structure is invalid
    """
    if not isinstance(config_data, dict):
        raise MCPConfigError("配置文件必须是对象格式")
    
    # Check required top-level fields
    required_fields = ['version', 'description', 'servers']
    for field in required_fields:
        if field not in config_data:
            raise MCPConfigError(f"缺少必需字段: '{field}'")
    
    # Validate version
    version = config_data['version']
    if not isinstance(version, str) or not version.strip():
        raise MCPConfigError("'version' 字段必须是非空字符串")
    
    # Validate description
    description = config_data['description']
    if not isinstance(description, str) or not description.strip():
        raise MCPConfigError("'description' 字段必须是非空字符串")
    
    # Validate servers
    servers = config_data['servers']
    if not isinstance(servers, dict):
        raise MCPConfigError("'servers' 字段必须是对象格式")
    
    # Validate each server
    for server_name, server_info in servers.items():
        try:
            validate_server_config(server_name, server_info)
        except MCPValidationError as e:
            raise MCPConfigError(f"服务器 '{server_name}' 配置错误: {e}")
    
    return config_data


def get_validation_status() -> Dict[str, Any]:
    """Get information about validation capabilities and status.
    
    Returns:
        Dictionary with validation capability information
    """
    return {
        'jsonschema_available': JSONSCHEMA_AVAILABLE,
        'schema_validation_enabled': JSONSCHEMA_AVAILABLE,
        'validation_functions': {
            'validate_mcp_servers_config': True,
            'validate_server_config': True,
            'validate_central_config_format': True,
        }
    }


# Backward compatibility function names for existing code
def validate_schema(config_path: Union[str, Path], schema_path: Optional[Union[str, Path]] = None):
    """Backward compatibility function for schema validation.
    
    Args:
        config_path: Path to configuration file
        schema_path: Path to schema file (optional, uses default if not provided)
        
    Returns:
        Validated configuration dictionary
    """
    return validate_mcp_servers_config(config_path)


def validate_server_config_compat(server_name: str, server_info: Dict[str, Any]):
    """Backward compatibility function for server validation."""
    return validate_server_config(server_name, server_info)


# Main validation entry point for backward compatibility
def main():
    """Main function for command-line validation testing."""
    if len(sys.argv) < 2:
        print("用法: python mcp_validation.py <config_path>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    try:
        print(f"验证配置文件: {config_path}")
        config_data = validate_mcp_servers_config(config_path)
        print("✅ 配置验证通过")
        
        # Print validation status
        status = get_validation_status()
        print(f"📊 验证状态: {status}")
        
    except MCPValidationError as e:
        print(f"❌ 配置验证失败: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"❌ 文件不存在: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 意外错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
