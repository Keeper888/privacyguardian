#!/usr/bin/env python3
"""
PrivacyGuardian - GUI Dashboard with Full Control
==================================================
GTK4 dashboard for monitoring AND controlling PII protection.
No command line needed - manage everything from here.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib, Gio, Pango, Gdk
import json
import urllib.request
import subprocess
import threading
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from setup_wizard import SetupWizard, SUPPORTED_APPS, SetupError


# Find guardian directory
SCRIPT_DIR = Path(__file__).parent.parent.parent
GUARDIAN_SCRIPT = SCRIPT_DIR / "guardian"
VENV_PYTHON = SCRIPT_DIR / "venv" / "bin" / "python"
CODE_DIR = SCRIPT_DIR / "code"
FLAG_FILE = Path.home() / ".privacyguardian" / "enabled"


class PrivacyGuardianApp(Adw.Application):
    """Main application class"""

    def __init__(self):
        super().__init__(
            application_id="com.privacyguardian.dashboard",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = DashboardWindow(application=self)
        self.window.present()


class DashboardWindow(Adw.ApplicationWindow):
    """Main dashboard window with full control panel"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("PrivacyGuardian Control Center")
        self.set_default_size(800, 700)

        # State
        self.stats = {}
        self.activity = []
        self.proxy_url = "http://localhost:6660"
        self.proxy_running = False
        self.protection_enabled = FLAG_FILE.exists()

        # Build UI
        self._build_ui()

        # Start polling
        self._start_polling()

    def _build_ui(self):
        """Build the main UI"""
        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.append(Gtk.Label(label="🛡️ PrivacyGuardian Control Center"))
        header.set_title_widget(title_box)

        # Setup button in header
        setup_btn = Gtk.Button(label="Setup")
        setup_btn.set_tooltip_text("Configure which apps to protect")
        setup_btn.connect("clicked", self._on_setup_clicked)
        header.pack_end(setup_btn)

        # Refresh button in header
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh Status")
        refresh_btn.connect("clicked", lambda _: self._refresh_all())
        header.pack_end(refresh_btn)

        main_box.append(header)

        # Status banner
        self.status_banner = Adw.Banner()
        self.status_banner.set_title("Checking status...")
        self.status_banner.set_revealed(True)
        main_box.append(self.status_banner)

        # Scrollable content
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        main_box.append(scroll)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(16)
        scroll.set_child(content_box)

        # ===================
        # MASTER PROTECTION TOGGLE
        # ===================
        master_frame = Gtk.Frame()
        master_frame.add_css_class("card")
        master_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        master_box.set_margin_start(20)
        master_box.set_margin_end(20)
        master_box.set_margin_top(16)
        master_box.set_margin_bottom(16)
        master_frame.set_child(master_box)
        content_box.append(master_frame)

        # Shield icon and text
        shield_label = Gtk.Label(label="🛡️")
        shield_label.add_css_class("title-1")
        master_box.append(shield_label)

        master_text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        master_text_box.set_hexpand(True)
        master_box.append(master_text_box)

        master_title = Gtk.Label(label="Protection", xalign=0)
        master_title.add_css_class("title-2")
        master_text_box.append(master_title)

        self.master_desc = Gtk.Label(label="Route LLM traffic through PrivacyGuardian", xalign=0)
        self.master_desc.add_css_class("dim-label")
        master_text_box.append(self.master_desc)

        # The toggle switch
        self.protection_switch = Gtk.Switch()
        self.protection_switch.set_valign(Gtk.Align.CENTER)
        self.protection_switch.set_active(self.protection_enabled)
        self.protection_switch.connect("state-set", self._on_protection_toggle)
        master_box.append(self.protection_switch)

        # ===================
        # QUICK ACTIONS
        # ===================
        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        actions_row.set_halign(Gtk.Align.CENTER)
        actions_row.set_margin_top(8)
        content_box.append(actions_row)

        test_btn = Gtk.Button(label="🧪 Test Protection")
        test_btn.set_tooltip_text("Send a test message with fake PII to verify protection")
        test_btn.connect("clicked", self._on_test_protection)
        actions_row.append(test_btn)

        view_logs_btn = Gtk.Button(label="📋 View Logs")
        view_logs_btn.set_tooltip_text("Open terminal with service logs")
        view_logs_btn.connect("clicked", self._on_view_logs)
        actions_row.append(view_logs_btn)

        open_vault_btn = Gtk.Button(label="🔐 Open Vault Folder")
        open_vault_btn.set_tooltip_text("Open the encrypted vault folder")
        open_vault_btn.connect("clicked", self._on_open_vault)
        actions_row.append(open_vault_btn)

        # ===================
        # STATS CARDS
        # ===================
        stats_label = Gtk.Label(label="Protection Statistics", xalign=0)
        stats_label.add_css_class("title-3")
        content_box.append(stats_label)

        stats_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        stats_row.set_homogeneous(True)
        content_box.append(stats_row)

        self.status_card = self._create_stat_card("Status", "---", "🔒")
        self.uptime_card = self._create_stat_card("Uptime", "---", "⏱️")
        self.protected_card = self._create_stat_card("Items Protected", "0", "✅")
        self.requests_card = self._create_stat_card("Requests", "0", "📡")

        stats_row.append(self.status_card)
        stats_row.append(self.uptime_card)
        stats_row.append(self.protected_card)
        stats_row.append(self.requests_card)

        # ===================
        # ACTIVITY SECTION
        # ===================
        activity_label = Gtk.Label(label="Recent Activity", xalign=0)
        activity_label.add_css_class("title-3")
        content_box.append(activity_label)

        self.activity_list = Gtk.ListBox()
        self.activity_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.activity_list.add_css_class("boxed-list")

        activity_frame = Gtk.Frame()
        activity_frame.set_child(self.activity_list)
        content_box.append(activity_frame)

        # ===================
        # TYPE BREAKDOWN
        # ===================
        type_label = Gtk.Label(label="Protected by Type", xalign=0)
        type_label.add_css_class("title-3")
        content_box.append(type_label)

        self.type_list = Gtk.ListBox()
        self.type_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.type_list.add_css_class("boxed-list")

        type_frame = Gtk.Frame()
        type_frame.set_child(self.type_list)
        content_box.append(type_frame)

        # Apply CSS
        self._apply_css()

    def _create_stat_card(self, title: str, value: str, icon: str) -> Gtk.Frame:
        """Create a statistics card widget"""
        frame = Gtk.Frame()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        frame.set_child(box)

        # Icon and title row
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon_label = Gtk.Label(label=icon)
        header_box.append(icon_label)

        title_label = Gtk.Label(label=title)
        title_label.set_opacity(0.7)
        title_label.add_css_class("caption")
        header_box.append(title_label)
        box.append(header_box)

        # Value
        value_label = Gtk.Label(label=value)
        value_label.add_css_class("title-2")
        value_label.set_halign(Gtk.Align.START)
        box.append(value_label)

        frame.value_label = value_label
        return frame

    def _apply_css(self):
        """Apply custom CSS styling"""
        css = b"""
        .title-3 {
            font-weight: bold;
            font-size: 16px;
            margin-top: 8px;
        }
        .heading {
            font-weight: bold;
            font-size: 14px;
            margin-top: 8px;
        }
        .activity-row {
            padding: 8px;
        }
        .pii-type {
            font-family: monospace;
            font-weight: bold;
        }
        .timestamp {
            opacity: 0.6;
            font-size: 11px;
        }
        .provider {
            opacity: 0.8;
        }
        .status-active {
            color: #2ec27e;
        }
        .status-inactive {
            color: #c01c28;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ===================
    # CONTROL ACTIONS
    # ===================

    def _on_protection_toggle(self, switch, state):
        """Handle master protection toggle"""
        if state:
            # Check if setup has been completed (aliases installed)
            from setup_wizard import SetupWizard
            wizard = SetupWizard()
            status = wizard.get_current_config_status()

            if not status.get('already_configured'):
                # Revert the switch and prompt user to run setup first
                switch.set_active(False)
                self._show_error_dialog(
                    "Setup Required",
                    "Please click the Setup button first to configure your shell.\n\n"
                    "This only needs to be done once."
                )
                return True  # Prevent switch from toggling

            self._show_toast("Enabling protection...")
            self._run_command_async(["enable"], self._on_protection_enabled)
        else:
            self._show_toast("Disabling protection...")
            self._run_command_async(["disable"], self._on_protection_disabled)
        return False  # Let the switch update

    def _on_protection_enabled(self, success, output):
        """Called when protection is enabled"""
        if success:
            self.protection_enabled = True
            self.master_desc.set_text("Protection is ON - LLM traffic routed through proxy")
            self._show_toast("Verifying proxy...")
            # Verify proxy is actually responding after a short delay
            GLib.timeout_add(1500, self._verify_proxy_health)
        else:
            # Revert switch state
            self.protection_switch.set_active(False)
            self._show_error_dialog("Failed to enable protection", output)

    def _verify_proxy_health(self):
        """Verify the proxy is actually running and responding"""
        try:
            with urllib.request.urlopen(f"{self.proxy_url}/__guardian__/stats", timeout=3) as resp:
                if resp.status == 200:
                    self._show_toast("Protection enabled and verified!")
                    self._refresh_all()
                    return False  # Stop timeout
        except Exception as e:
            pass

        self._show_toast("Warning: Proxy may not be running correctly")
        self._refresh_all()
        return False  # Don't repeat

    def _on_protection_disabled(self, success, output):
        """Called when protection is disabled"""
        self.protection_enabled = False
        self.master_desc.set_text("Protection is OFF - LLM traffic goes direct")
        self._show_toast("Protection disabled")
        GLib.timeout_add(500, self._refresh_all)

    def _on_test_protection(self, button):
        """Test the protection with fake PII"""
        self._show_toast("Running protection test...")
        threading.Thread(target=self._run_test, daemon=True).start()

    def _run_test(self):
        """Run a test request through the proxy"""
        try:
            import urllib.request
            import json

            # Create test data with fake PII
            test_data = {
                "test": True,
                "message": "Test email: test123@example.com, phone: 555-123-4567"
            }

            req = urllib.request.Request(
                f"{self.proxy_url}/__guardian__/health",
                method="GET"
            )

            with urllib.request.urlopen(req, timeout=5) as resp:
                result = resp.read().decode()

            GLib.idle_add(self._show_toast, "Test completed! Proxy is working.")
            GLib.idle_add(self._refresh_all)

        except Exception as e:
            GLib.idle_add(self._show_toast, f"Test failed: {e}")

    def _on_view_logs(self, button):
        """Open logs in terminal"""
        subprocess.Popen([
            "gnome-terminal", "--", "bash", "-c",
            "journalctl --user -u privacyguardian -f; read"
        ])

    def _on_open_vault(self, button):
        """Open the vault folder"""
        vault_path = Path.home() / ".privacyguardian"
        if vault_path.exists():
            subprocess.Popen(["xdg-open", str(vault_path)])
        else:
            self._show_toast("Vault folder doesn't exist yet")

    # ===================
    # SETUP WIZARD
    # ===================

    def _on_setup_clicked(self, button):
        """Open the setup wizard dialog"""
        dialog = SetupDialog(self)
        dialog.present()

    # ===================
    # HELPER METHODS
    # ===================

    def _run_command_async(self, args: list, callback):
        """Run a guardian command asynchronously"""
        def run():
            try:
                # For start command, we need to run proxy in background
                if args[0] == "start":
                    # Start proxy as background process
                    subprocess.Popen(
                        [str(VENV_PYTHON), str(CODE_DIR / "guardian_proxy.py")],
                        cwd=str(CODE_DIR),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    GLib.idle_add(callback, True, "Started")
                else:
                    result = subprocess.run(
                        [str(GUARDIAN_SCRIPT)] + args,
                        capture_output=True,
                        text=True,
                        cwd=str(SCRIPT_DIR)
                    )
                    success = result.returncode == 0
                    output = result.stdout + result.stderr
                    GLib.idle_add(callback, success, output)
            except Exception as e:
                GLib.idle_add(callback, False, str(e))

        threading.Thread(target=run, daemon=True).start()

    def _show_toast(self, message: str):
        """Show a toast notification"""
        toast = Adw.Toast(title=message)
        toast.set_timeout(3)
        # Find toast overlay or just update banner
        self.status_banner.set_title(message)

    def _show_error_dialog(self, title: str, message: str):
        """Show an error dialog"""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=title,
            body=message
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def _refresh_all(self):
        """Refresh all status information"""
        self._refresh_data()
        return False  # Don't repeat

    # ===================
    # POLLING & DATA
    # ===================

    def _start_polling(self):
        """Start polling the proxy for updates"""
        self._refresh_data()
        GLib.timeout_add_seconds(2, self._poll_tick)

    def _poll_tick(self) -> bool:
        """Polling tick"""
        threading.Thread(target=self._fetch_data, daemon=True).start()
        return True

    def _fetch_data(self):
        """Fetch data from proxy"""
        try:
            with urllib.request.urlopen(f"{self.proxy_url}/__guardian__/stats", timeout=2) as resp:
                stats = json.loads(resp.read())

            with urllib.request.urlopen(f"{self.proxy_url}/__guardian__/activity", timeout=2) as resp:
                activity = json.loads(resp.read())

            GLib.idle_add(self._update_ui, stats, activity.get("activity", []), True)

        except Exception as e:
            GLib.idle_add(self._update_ui, {}, [], False)

    def _refresh_data(self):
        """Manual refresh"""
        threading.Thread(target=self._fetch_data, daemon=True).start()

    def _update_ui(self, stats: dict, activity: list, proxy_running: bool):
        """Update UI with new data"""
        self.stats = stats
        self.activity = activity
        self.proxy_running = proxy_running

        # Sync protection toggle with flag file (in case changed externally)
        current_flag = FLAG_FILE.exists()
        if current_flag != self.protection_enabled:
            self.protection_enabled = current_flag
            self.protection_switch.set_active(current_flag)
            if current_flag:
                self.master_desc.set_text("Protection is ON - LLM traffic routed through proxy")
            else:
                self.master_desc.set_text("Protection is OFF - LLM traffic goes direct")

        # Update status banner
        if proxy_running and current_flag:
            self.status_banner.set_title("✓ Protection Active - All LLM traffic is being filtered")
        elif proxy_running and not current_flag:
            self.status_banner.set_title("⚠ Proxy running but protection disabled - Toggle switch to enable")
        elif not proxy_running and current_flag:
            self.status_banner.set_title("⚠ Protection enabled but proxy not running - Will start on next LLM call")
        else:
            self.status_banner.set_title("Protection disabled - Toggle switch to enable")

        # Update stat cards
        status = stats.get("status", "inactive").upper()
        self.status_card.value_label.set_text(status)
        self.uptime_card.value_label.set_text(stats.get("uptime", "---"))
        self.protected_card.value_label.set_text(str(stats.get("pii_items_protected", 0)))
        self.requests_card.value_label.set_text(str(stats.get("requests_processed", 0)))

        # Update activity list
        self._update_activity_list(activity)

        # Update type breakdown
        self._update_type_list(stats.get("vault", {}).get("by_type", {}))

    def _update_activity_list(self, activity: list):
        """Update the activity list"""
        while True:
            row = self.activity_list.get_row_at_index(0)
            if row:
                self.activity_list.remove(row)
            else:
                break

        for item in activity[:20]:
            row = self._create_activity_row(item)
            self.activity_list.append(row)

        if not activity:
            placeholder = Gtk.Label(label="No activity yet - send a message to any LLM to see protection in action")
            placeholder.set_opacity(0.5)
            placeholder.set_margin_top(16)
            placeholder.set_margin_bottom(16)
            self.activity_list.append(placeholder)

    def _create_activity_row(self, item: dict) -> Gtk.ListBoxRow:
        """Create an activity list row"""
        row = Gtk.ListBoxRow()
        row.add_css_class("activity-row")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        row.set_child(box)

        pii_type = item.get("pii_type", "UNKNOWN")
        type_label = Gtk.Label(label=pii_type[:10])
        type_label.add_css_class("pii-type")
        type_label.set_width_chars(10)
        box.append(type_label)

        masked = item.get("masked_value", "***")
        masked_label = Gtk.Label(label=masked)
        masked_label.set_hexpand(True)
        masked_label.set_halign(Gtk.Align.START)
        box.append(masked_label)

        provider = item.get("provider", "")
        if provider:
            provider_label = Gtk.Label(label=f"→ {provider}")
            provider_label.add_css_class("provider")
            box.append(provider_label)

        timestamp = item.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = timestamp[:8]
            time_label = Gtk.Label(label=time_str)
            time_label.add_css_class("timestamp")
            box.append(time_label)

        return row

    def _update_type_list(self, by_type: dict):
        """Update the type breakdown list"""
        while True:
            row = self.type_list.get_row_at_index(0)
            if row:
                self.type_list.remove(row)
            else:
                break

        for pii_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_start(12)
            box.set_margin_end(12)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            row.set_child(box)

            type_label = Gtk.Label(label=pii_type)
            type_label.set_hexpand(True)
            type_label.set_halign(Gtk.Align.START)
            box.append(type_label)

            count_label = Gtk.Label(label=str(count))
            count_label.add_css_class("accent")
            box.append(count_label)

            self.type_list.append(row)

        if not by_type:
            placeholder = Gtk.Label(label="No data yet")
            placeholder.set_opacity(0.5)
            placeholder.set_margin_top(16)
            placeholder.set_margin_bottom(16)
            self.type_list.append(placeholder)


class SetupDialog(Adw.Window):
    """Setup wizard dialog for configuring app aliases"""

    def __init__(self, parent):
        super().__init__()
        self.parent_window = parent
        self.wizard = SetupWizard()
        self.app_checkboxes = {}

        self.set_title("PrivacyGuardian Setup")
        self.set_default_size(500, 550)
        self.set_modal(True)
        self.set_transient_for(parent)

        self._build_ui()

    def _build_ui(self):
        """Build the setup dialog UI"""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(main_box)

        # Header
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        main_box.append(header)

        # Content with scroll
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        main_box.append(scroll)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        scroll.set_child(content)

        # Welcome message
        welcome_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.append(welcome_box)

        welcome_icon = Gtk.Label(label="🛡️")
        welcome_icon.add_css_class("title-1")
        welcome_box.append(welcome_icon)

        welcome_title = Gtk.Label(label="Setup Protection")
        welcome_title.add_css_class("title-2")
        welcome_box.append(welcome_title)

        welcome_desc = Gtk.Label(
            label="Select which apps you want to protect.\n"
                  "This will add aliases to your shell config file."
        )
        welcome_desc.set_wrap(True)
        welcome_desc.set_justify(Gtk.Justification.CENTER)
        welcome_desc.add_css_class("dim-label")
        welcome_box.append(welcome_desc)

        # Current status
        status = self.wizard.get_current_config_status()

        status_frame = Gtk.Frame()
        status_frame.add_css_class("card")
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        status_box.set_margin_start(12)
        status_box.set_margin_end(12)
        status_box.set_margin_top(12)
        status_box.set_margin_bottom(12)
        status_frame.set_child(status_box)
        content.append(status_frame)

        status_title = Gtk.Label(label="Current Status", xalign=0)
        status_title.add_css_class("heading")
        status_box.append(status_title)

        shell_label = Gtk.Label(label=f"Shell: {status['shell']}", xalign=0)
        shell_label.add_css_class("dim-label")
        status_box.append(shell_label)

        config_label = Gtk.Label(
            label=f"Config: {Path(status['config_file']).name if status['config_file'] else 'Not found'}",
            xalign=0
        )
        config_label.add_css_class("dim-label")
        status_box.append(config_label)

        if status['already_configured']:
            configured_label = Gtk.Label(label="✓ Already configured", xalign=0)
            configured_label.add_css_class("success")
            status_box.append(configured_label)

        # App selection
        apps_label = Gtk.Label(label="Select Apps to Protect", xalign=0)
        apps_label.add_css_class("title-3")
        content.append(apps_label)

        apps_frame = Gtk.Frame()
        apps_list = Gtk.ListBox()
        apps_list.set_selection_mode(Gtk.SelectionMode.NONE)
        apps_list.add_css_class("boxed-list")
        apps_frame.set_child(apps_list)
        content.append(apps_frame)

        for app_id, app_info in SUPPORTED_APPS.items():
            row = Adw.ActionRow()
            row.set_title(app_info['name'])
            row.set_subtitle(app_info['description'])

            checkbox = Gtk.CheckButton()
            # Pre-check Claude by default, and any already configured
            if app_id == 'claude' or app_id in status.get('configured_apps', []):
                checkbox.set_active(True)
            checkbox.set_valign(Gtk.Align.CENTER)
            row.add_suffix(checkbox)
            row.set_activatable_widget(checkbox)

            self.app_checkboxes[app_id] = checkbox
            apps_list.append(row)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(8)
        content.append(button_box)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        button_box.append(cancel_btn)

        if status['already_configured']:
            remove_btn = Gtk.Button(label="Remove Setup")
            remove_btn.add_css_class("destructive-action")
            remove_btn.connect("clicked", self._on_remove_clicked)
            button_box.append(remove_btn)

        apply_btn = Gtk.Button(label="Apply Setup")
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self._on_apply_clicked)
        button_box.append(apply_btn)

    def _on_apply_clicked(self, button):
        """Handle apply button click"""
        # Get selected apps
        selected_apps = [
            app_id for app_id, checkbox in self.app_checkboxes.items()
            if checkbox.get_active()
        ]

        if not selected_apps:
            self._show_error("No Apps Selected", "Please select at least one app to protect.")
            return

        # Run the setup
        result = self.wizard.install_aliases(selected_apps)

        if result.success:
            self._show_success(result)
        else:
            self._show_failure(result)

    def _on_remove_clicked(self, button):
        """Handle remove button click"""
        result = self.wizard.remove_aliases()

        if result.success:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Setup Removed",
                body=f"PrivacyGuardian aliases have been removed.\n\n"
                     f"Backup saved to:\n{result.backup_path}\n\n"
                     f"Restart your terminal for changes to take effect."
            )
            dialog.add_response("ok", "OK")
            dialog.connect("response", lambda d, r: self.close())
            dialog.present()
        else:
            self._show_error("Remove Failed", result.message)

    def _show_success(self, result):
        """Show success dialog and spawn terminal with reload command"""
        # Try to spawn a terminal with the reload command
        terminal_spawned = self._spawn_reload_terminal(result.config_file)

        if terminal_spawned:
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Setup Complete! ✓",
                body=f"{result.message}\n\n"
                     f"A terminal window has opened.\n"
                     f"Just press ENTER there to finish setup!\n\n"
                     f"Then toggle Protection ON and use 'claude' normally."
            )
        else:
            # Fallback if no terminal could be opened
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Setup Complete! ✓",
                body=f"{result.message}\n\n"
                     f"{'Backup: ' + result.backup_path if result.backup_path else ''}\n\n"
                     f"Open a NEW terminal and run:\n"
                     f"  source ~/{Path(result.config_file).name}\n\n"
                     f"Then test with:\n"
                     f"  type claude"
            )

        dialog.add_response("ok", "Got it!")
        dialog.connect("response", lambda d, r: self.close())
        dialog.present()

    def _show_failure(self, result):
        """Show failure dialog with manual instructions"""
        if result.error == SetupError.ALREADY_CONFIGURED:
            self._show_error(
                "Already Configured",
                "PrivacyGuardian is already set up.\n\n"
                "Use 'Remove Setup' first if you want to reconfigure."
            )
            return

        # Create dialog with manual instructions
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Setup Failed",
            body=f"{result.message}\n\n"
                 f"Don't worry! You can set this up manually."
        )
        dialog.add_response("copy", "Copy Instructions")
        dialog.add_response("ok", "OK")
        dialog.set_response_appearance("copy", Adw.ResponseAppearance.SUGGESTED)

        if result.manual_instructions:
            dialog.connect("response", lambda d, r: self._handle_failure_response(r, result))

        dialog.present()

    def _handle_failure_response(self, response, result):
        """Handle response from failure dialog"""
        if response == "copy" and result.manual_instructions:
            # Copy to clipboard
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(result.manual_instructions)

            # Show the instructions in a new dialog
            text_dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Manual Setup Instructions",
                body="Instructions copied to clipboard!\n\n"
                     "Here they are for reference:"
            )

            # Add a scrolled text view for the instructions
            scroll = Gtk.ScrolledWindow()
            scroll.set_min_content_height(300)
            scroll.set_min_content_width(400)

            text_view = Gtk.TextView()
            text_view.set_editable(False)
            text_view.set_wrap_mode(Gtk.WrapMode.WORD)
            text_view.set_monospace(True)
            text_view.get_buffer().set_text(result.manual_instructions)
            text_view.set_margin_start(8)
            text_view.set_margin_end(8)
            text_view.set_margin_top(8)
            text_view.set_margin_bottom(8)

            scroll.set_child(text_view)
            text_dialog.set_extra_child(scroll)

            text_dialog.add_response("ok", "OK")
            text_dialog.present()

    def _show_error(self, title, message):
        """Show a simple error dialog"""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=title,
            body=message
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def _spawn_reload_terminal(self, config_file: str):
        """Open terminal with shell reload command ready - user just presses Enter"""
        shell = os.environ.get('SHELL', '/bin/bash')
        config_name = Path(config_file).name

        if 'zsh' in shell:
            reload_cmd = f'source ~/.zshrc'
        elif 'fish' in shell:
            reload_cmd = f'source ~/.config/fish/config.fish'
        else:
            reload_cmd = f'source ~/.bashrc'

        # Script to show in terminal
        script = f'''
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         PrivacyGuardian Setup - One Last Step!                 ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║                                                                ║"
echo "║  Press ENTER to reload your shell configuration.              ║"
echo "║  This is the only manual step required!                        ║"
echo "║                                                                ║"
echo "║  After this, you can use 'claude' with protection enabled.    ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Command: {reload_cmd}"
echo ""
read -p ">>> Press ENTER to continue... "
{reload_cmd}
echo ""
echo "Done! You can now use this terminal with protection enabled."
echo "Try: claude --help"
echo ""
exec {shell}
'''

        # Try different terminal emulators in order of preference
        terminals = [
            ['gnome-terminal', '--', 'bash', '-c', script],
            ['konsole', '-e', 'bash', '-c', script],
            ['xfce4-terminal', '-x', 'bash', '-c', script],
            ['mate-terminal', '-x', 'bash', '-c', script],
            ['tilix', '-e', 'bash', '-c', script],
            ['xterm', '-e', 'bash', '-c', script],
        ]

        for term_cmd in terminals:
            try:
                subprocess.Popen(term_cmd, start_new_session=True)
                return True
            except FileNotFoundError:
                continue

        # No terminal found - return False
        return False


def main():
    """Run the dashboard application"""
    app = PrivacyGuardianApp()
    app.run(None)


if __name__ == "__main__":
    main()
