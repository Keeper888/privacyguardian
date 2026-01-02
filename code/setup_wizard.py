#!/usr/bin/env python3
"""
PrivacyGuardian Setup Wizard
============================
Handles first-time setup: detecting shells, installing aliases,
with comprehensive error handling and user-friendly fallback instructions.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


# Supported apps and their environment variables
SUPPORTED_APPS = {
    # === CLI Apps (use aliases) ===
    'claude': {
        'name': 'Claude Code',
        'env_var': 'ANTHROPIC_BASE_URL',
        'description': 'Anthropic Claude CLI',
        'check_cmd': 'claude',
        'type': 'cli',
    },
    'chatgpt': {
        'name': 'ChatGPT CLI',
        'env_var': 'OPENAI_BASE_URL',
        'description': 'OpenAI ChatGPT CLI',
        'check_cmd': 'chatgpt',
        'type': 'cli',
    },
    'openai': {
        'name': 'OpenAI CLI',
        'env_var': 'OPENAI_BASE_URL',
        'description': 'OpenAI official CLI',
        'check_cmd': 'openai',
        'type': 'cli',
    },
    'gemini': {
        'name': 'Google Gemini',
        'env_var': 'GOOGLE_AI_BASE_URL',
        'description': 'Google Gemini CLI',
        'check_cmd': 'gemini',
        'type': 'cli',
    },
    'mistral': {
        'name': 'Mistral AI',
        'env_var': 'MISTRAL_API_BASE_URL',
        'description': 'Mistral AI CLI',
        'check_cmd': 'mistral',
        'type': 'cli',
    },
    # === GUI Apps (use launchers or .desktop files) ===
    'cursor': {
        'name': 'Cursor',
        'env_var': 'OPENAI_BASE_URL',
        'description': 'AI Code Editor (VS Code fork)',
        'check_cmd': 'cursor',
        'type': 'gui',
        'desktop_file': 'cursor.desktop',
        'launch_cmd': 'cursor',
    },
    'antigravity': {
        'name': 'Antigravity',
        'env_var': 'ANTHROPIC_BASE_URL',
        'description': 'AI Coding Assistant',
        'check_cmd': 'antigravity',
        'type': 'gui',
        'desktop_file': 'antigravity.desktop',
        'launch_cmd': 'antigravity',
    },
    'windsurf': {
        'name': 'Windsurf',
        'env_var': 'OPENAI_BASE_URL',
        'description': 'Codeium AI Editor',
        'check_cmd': 'windsurf',
        'type': 'gui',
        'desktop_file': 'windsurf.desktop',
        'launch_cmd': 'windsurf',
    },
    'zed': {
        'name': 'Zed',
        'env_var': 'OPENAI_BASE_URL',
        'description': 'Zed Editor with AI',
        'check_cmd': 'zed',
        'type': 'gui',
        'desktop_file': 'zed.desktop',
        'launch_cmd': 'zed',
    },
}

# Shell configuration files
SHELL_CONFIGS = {
    'bash': ['.bashrc', '.bash_profile'],
    'zsh': ['.zshrc'],
    'fish': ['.config/fish/config.fish'],
}


class SetupError(Enum):
    NONE = "none"
    SHELL_NOT_DETECTED = "shell_not_detected"
    CONFIG_NOT_FOUND = "config_not_found"
    PERMISSION_DENIED = "permission_denied"
    BACKUP_FAILED = "backup_failed"
    WRITE_FAILED = "write_failed"
    VERIFICATION_FAILED = "verification_failed"
    ALREADY_CONFIGURED = "already_configured"
    UNKNOWN = "unknown"


@dataclass
class SetupResult:
    success: bool
    error: SetupError
    message: str
    manual_instructions: Optional[str] = None
    backup_path: Optional[str] = None
    config_file: Optional[str] = None


class SetupWizard:
    """Handles alias setup with comprehensive error handling"""

    def __init__(self):
        self.home = Path.home()
        self.pg_wrapper = Path(__file__).parent.parent / "pg-wrapper"
        self.marker_start = "# >>> PrivacyGuardian aliases >>>"
        self.marker_end = "# <<< PrivacyGuardian aliases <<<"

    def detect_shell(self) -> Tuple[str, Optional[Path]]:
        """
        Detect user's shell and find the appropriate config file.
        Returns: (shell_name, config_path) or (shell_name, None) if not found
        """
        # Check SHELL environment variable
        shell_path = os.environ.get('SHELL', '/bin/bash')
        shell_name = Path(shell_path).name

        # Map to our known shells
        if 'zsh' in shell_name:
            shell_type = 'zsh'
        elif 'fish' in shell_name:
            shell_type = 'fish'
        else:
            shell_type = 'bash'  # Default to bash

        # Find config file
        for config_name in SHELL_CONFIGS.get(shell_type, ['.bashrc']):
            config_path = self.home / config_name
            if config_path.exists():
                return shell_type, config_path

        # Try to find any config file
        for shell, configs in SHELL_CONFIGS.items():
            for config_name in configs:
                config_path = self.home / config_name
                if config_path.exists():
                    return shell, config_path

        # Default to .bashrc even if it doesn't exist (we'll create it)
        return 'bash', self.home / '.bashrc'

    def check_existing_setup(self, config_path: Path) -> bool:
        """Check if PrivacyGuardian aliases are already configured"""
        try:
            if config_path.exists():
                content = config_path.read_text()
                return self.marker_start in content
        except Exception:
            pass
        return False

    def create_backup(self, config_path: Path) -> Tuple[bool, Optional[Path], str]:
        """
        Create a backup of the config file.
        Returns: (success, backup_path, error_message)
        """
        if not config_path.exists():
            return True, None, ""  # No backup needed for new file

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = config_path.parent / f"{config_path.name}.privacyguardian_backup_{timestamp}"
            shutil.copy2(config_path, backup_path)
            return True, backup_path, ""
        except PermissionError:
            return False, None, f"Permission denied creating backup of {config_path}"
        except Exception as e:
            return False, None, f"Failed to create backup: {str(e)}"

    def generate_aliases(self, apps: List[str]) -> str:
        """Generate the alias block for selected CLI apps"""
        # Filter to CLI apps only
        cli_apps = [a for a in apps if SUPPORTED_APPS.get(a, {}).get('type', 'cli') == 'cli']

        if not cli_apps:
            return ""

        lines = [
            "",
            self.marker_start,
            f"# Added by PrivacyGuardian on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Wrapper: {self.pg_wrapper}",
        ]

        for app in cli_apps:
            if app in SUPPORTED_APPS:
                lines.append(f"alias {app}='{self.pg_wrapper} {app}'")

        lines.append(self.marker_end)
        lines.append("")

        return "\n".join(lines)

    def create_gui_launchers(self, apps: List[str]) -> Tuple[List[str], List[str]]:
        """
        Create launcher scripts for GUI apps in ~/.local/bin/
        Returns: (created_launchers, failed_launchers)
        """
        gui_apps = [a for a in apps if SUPPORTED_APPS.get(a, {}).get('type') == 'gui']

        if not gui_apps:
            return [], []

        # Ensure ~/.local/bin exists and is in PATH
        local_bin = self.home / ".local" / "bin"
        local_bin.mkdir(parents=True, exist_ok=True)

        created = []
        failed = []

        for app in gui_apps:
            app_info = SUPPORTED_APPS[app]
            launcher_path = local_bin / f"{app}-protected"
            env_var = app_info['env_var']
            launch_cmd = app_info.get('launch_cmd', app)

            launcher_script = f'''#!/bin/bash
# PrivacyGuardian launcher for {app_info['name']}
# Routes AI traffic through local PII protection proxy

FLAG_FILE="$HOME/.privacyguardian/enabled"
PROXY_URL="http://localhost:6660"

if [ -f "$FLAG_FILE" ]; then
    # Check if proxy is running
    if curl -s --max-time 1 "$PROXY_URL/__guardian__/health" > /dev/null 2>&1; then
        export {env_var}="$PROXY_URL"
        echo "[PrivacyGuardian] Protection ENABLED for {app_info['name']}"
    else
        echo "[PrivacyGuardian] Warning: Proxy not running. Starting without protection."
    fi
else
    echo "[PrivacyGuardian] Protection disabled. Running {app_info['name']} directly."
fi

exec {launch_cmd} "$@"
'''

            try:
                launcher_path.write_text(launcher_script)
                launcher_path.chmod(0o755)
                created.append(app)
            except Exception:
                failed.append(app)

        return created, failed

    def generate_manual_instructions(self, apps: List[str], shell: str, config_file: str) -> str:
        """Generate manual setup instructions for the user"""
        alias_lines = []
        for app in apps:
            if app in SUPPORTED_APPS:
                alias_lines.append(f"alias {app}='{self.pg_wrapper} {app}'")

        aliases_text = "\n".join(alias_lines)

        return f"""
MANUAL SETUP REQUIRED
=====================

The automatic setup couldn't complete. Please follow these steps:

1. Open your shell config file in a text editor:

   nano ~/{config_file}

2. Add these lines at the END of the file:

{self.marker_start}
{aliases_text}
{self.marker_end}

3. Save the file and reload your shell:

   source ~/{config_file}

4. Verify it works:

   type claude  # Should show the pg-wrapper path

ALTERNATIVE: If you use a different shell, add the aliases to:
- Bash: ~/.bashrc or ~/.bash_profile
- Zsh:  ~/.zshrc
- Fish: ~/.config/fish/config.fish
"""

    def install_aliases(self, apps: List[str]) -> SetupResult:
        """
        Install aliases for selected apps.
        Returns SetupResult with success status and error handling info.
        """
        # Validate apps
        apps = [a for a in apps if a in SUPPORTED_APPS]
        if not apps:
            return SetupResult(
                success=False,
                error=SetupError.UNKNOWN,
                message="No valid apps selected",
            )

        # Detect shell and config
        shell, config_path = self.detect_shell()

        if config_path is None:
            manual = self.generate_manual_instructions(apps, shell, ".bashrc")
            return SetupResult(
                success=False,
                error=SetupError.CONFIG_NOT_FOUND,
                message=f"Could not find shell config file for {shell}",
                manual_instructions=manual,
            )

        # Check if already configured
        if self.check_existing_setup(config_path):
            return SetupResult(
                success=False,
                error=SetupError.ALREADY_CONFIGURED,
                message="PrivacyGuardian aliases are already configured",
                config_file=str(config_path),
            )

        # Create backup
        backup_ok, backup_path, backup_error = self.create_backup(config_path)
        if not backup_ok:
            manual = self.generate_manual_instructions(apps, shell, config_path.name)
            return SetupResult(
                success=False,
                error=SetupError.BACKUP_FAILED,
                message=backup_error,
                manual_instructions=manual,
            )

        # Generate aliases
        alias_block = self.generate_aliases(apps)

        # Write to config file
        try:
            # Read existing content (if any)
            existing_content = ""
            if config_path.exists():
                existing_content = config_path.read_text()

            # Append aliases
            new_content = existing_content.rstrip() + alias_block

            # Write back
            config_path.write_text(new_content)

        except PermissionError:
            manual = self.generate_manual_instructions(apps, shell, config_path.name)
            return SetupResult(
                success=False,
                error=SetupError.PERMISSION_DENIED,
                message=f"Permission denied writing to {config_path}",
                manual_instructions=manual,
                backup_path=str(backup_path) if backup_path else None,
            )
        except Exception as e:
            manual = self.generate_manual_instructions(apps, shell, config_path.name)
            return SetupResult(
                success=False,
                error=SetupError.WRITE_FAILED,
                message=f"Failed to write config: {str(e)}",
                manual_instructions=manual,
                backup_path=str(backup_path) if backup_path else None,
            )

        # Verify the write (only if we wrote CLI aliases)
        cli_apps = [a for a in apps if SUPPORTED_APPS.get(a, {}).get('type', 'cli') == 'cli']
        if cli_apps and alias_block:
            try:
                verify_content = config_path.read_text()
                if self.marker_start not in verify_content:
                    manual = self.generate_manual_instructions(apps, shell, config_path.name)
                    return SetupResult(
                        success=False,
                        error=SetupError.VERIFICATION_FAILED,
                        message="Aliases were written but verification failed",
                        manual_instructions=manual,
                        backup_path=str(backup_path) if backup_path else None,
                    )
            except Exception:
                pass  # Verification is best-effort

        # Create GUI app launchers
        gui_created, gui_failed = self.create_gui_launchers(apps)

        # Build success message
        messages = []
        if cli_apps:
            messages.append(f"CLI aliases added to {config_path.name}")
        if gui_created:
            messages.append(f"GUI launchers created: {', '.join(gui_created)}-protected")
            messages.append("(Run from ~/.local/bin/ or add to PATH)")

        # Success!
        return SetupResult(
            success=True,
            error=SetupError.NONE,
            message=" | ".join(messages) if messages else "Setup complete",
            backup_path=str(backup_path) if backup_path else None,
            config_file=str(config_path),
        )

    def remove_aliases(self, config_path: Optional[Path] = None) -> SetupResult:
        """Remove PrivacyGuardian aliases from config file"""
        if config_path is None:
            _, config_path = self.detect_shell()

        if config_path is None or not config_path.exists():
            return SetupResult(
                success=False,
                error=SetupError.CONFIG_NOT_FOUND,
                message="Config file not found",
            )

        try:
            content = config_path.read_text()

            # Find and remove the alias block
            start_idx = content.find(self.marker_start)
            end_idx = content.find(self.marker_end)

            if start_idx == -1:
                return SetupResult(
                    success=False,
                    error=SetupError.UNKNOWN,
                    message="PrivacyGuardian aliases not found in config",
                )

            if end_idx != -1:
                end_idx = content.find("\n", end_idx) + 1  # Include the marker line
            else:
                end_idx = len(content)

            # Remove the block
            new_content = content[:start_idx] + content[end_idx:]
            new_content = new_content.strip() + "\n"

            # Create backup first
            backup_ok, backup_path, _ = self.create_backup(config_path)

            # Write back
            config_path.write_text(new_content)

            return SetupResult(
                success=True,
                error=SetupError.NONE,
                message="Successfully removed PrivacyGuardian aliases",
                backup_path=str(backup_path) if backup_path else None,
                config_file=str(config_path),
            )

        except Exception as e:
            return SetupResult(
                success=False,
                error=SetupError.WRITE_FAILED,
                message=f"Failed to remove aliases: {str(e)}",
            )

    def get_current_config_status(self) -> Dict:
        """Get current configuration status for display"""
        shell, config_path = self.detect_shell()

        status = {
            'shell': shell,
            'config_file': str(config_path) if config_path else None,
            'config_exists': config_path.exists() if config_path else False,
            'already_configured': False,
            'configured_apps': [],
        }

        if config_path and config_path.exists():
            try:
                content = config_path.read_text()
                status['already_configured'] = self.marker_start in content

                # Find which apps are configured
                for app in SUPPORTED_APPS:
                    if f"alias {app}=" in content:
                        status['configured_apps'].append(app)
            except Exception:
                pass

        return status


# For testing
if __name__ == "__main__":
    wizard = SetupWizard()

    print("Current status:")
    status = wizard.get_current_config_status()
    for k, v in status.items():
        print(f"  {k}: {v}")

    print("\nTesting alias generation:")
    print(wizard.generate_aliases(['claude', 'chatgpt']))
