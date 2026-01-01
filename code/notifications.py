"""
PrivacyGuardian - Desktop Notifications
========================================
System notifications for startup, PII blocking, and errors.
"""

import subprocess
import shutil
from typing import Optional
from pathlib import Path


class NotificationManager:
    """
    Desktop notification handler using notify-send (libnotify).
    Works on GNOME, KDE, XFCE, and other freedesktop-compliant desktops.
    """

    # Notification icons (using system theme icons)
    ICONS = {
        "startup": "security-high",
        "active": "security-high",
        "blocked": "dialog-warning",
        "error": "dialog-error",
        "info": "dialog-information",
    }

    def __init__(self):
        self.enabled = self._check_available()
        self.app_name = "PrivacyGuardian"

    def _check_available(self) -> bool:
        """Check if notify-send is available"""
        return shutil.which("notify-send") is not None

    def send(
        self,
        title: str,
        message: str,
        icon: str = "info",
        urgency: str = "normal",
        timeout: int = 5000,
    ) -> bool:
        """
        Send a desktop notification.

        Args:
            title: Notification title
            message: Notification body
            icon: Icon key from ICONS dict or custom icon name/path
            urgency: "low", "normal", or "critical"
            timeout: Display time in milliseconds (0 = never expire)

        Returns:
            True if notification was sent successfully
        """
        if not self.enabled:
            print(f"[Notification] {title}: {message}")
            return False

        icon_name = self.ICONS.get(icon, icon)

        cmd = [
            "notify-send",
            "--app-name", self.app_name,
            "--icon", icon_name,
            "--urgency", urgency,
            "--expire-time", str(timeout),
            title,
            message,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            print(f"Notification error: {e}")
            return False

    def startup(self):
        """Send startup notification"""
        self.send(
            "🛡️ PrivacyGuardian Active",
            "PII protection is now running.\nAll LLM traffic is being filtered.",
            icon="startup",
            urgency="normal",
            timeout=5000,
        )

    def pii_blocked(self, count: int, types: list, provider: str = None):
        """Send notification when PII is blocked"""
        type_str = ", ".join(types[:3])
        if len(types) > 3:
            type_str += f" +{len(types) - 3} more"

        provider_str = f" → {provider}" if provider else ""

        self.send(
            f"🛡️ Protected {count} item{'s' if count > 1 else ''}",
            f"{type_str}{provider_str}",
            icon="blocked",
            urgency="low",
            timeout=3000,
        )

    def error(self, message: str):
        """Send error notification"""
        self.send(
            "⚠️ PrivacyGuardian Error",
            message,
            icon="error",
            urgency="critical",
            timeout=0,  # Don't auto-dismiss errors
        )

    def stopped(self):
        """Send notification when service stops"""
        self.send(
            "🛡️ PrivacyGuardian Stopped",
            "PII protection is no longer active.\nYour traffic may be unprotected.",
            icon="error",
            urgency="critical",
            timeout=0,
        )


# Singleton instance
_notifier: Optional[NotificationManager] = None


def get_notifier() -> NotificationManager:
    """Get or create the global notification manager"""
    global _notifier
    if _notifier is None:
        _notifier = NotificationManager()
    return _notifier


def notify_startup():
    """Send startup notification (called from CLI)"""
    get_notifier().startup()


def notify_blocked(count: int, types: list, provider: str = None):
    """Send PII blocked notification"""
    get_notifier().pii_blocked(count, types, provider)


def notify_error(message: str):
    """Send error notification"""
    get_notifier().error(message)


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "startup":
            notify_startup()
        elif cmd == "test":
            notifier = NotificationManager()
            print(f"Notifications available: {notifier.enabled}")
            notifier.startup()
            import time
            time.sleep(2)
            notifier.pii_blocked(3, ["EMAIL", "API_KEY", "PHONE"], "Anthropic")
        else:
            print(f"Unknown command: {cmd}")
    else:
        print("Usage: python notifications.py [startup|test]")
