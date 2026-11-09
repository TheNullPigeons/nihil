"""Interactive editor for preset config and container settings."""

from copy import deepcopy
import time

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.events import Key, Resize
from textual.widgets import DataTable, Footer, Header, Input, Static


_CONFIG_INFO = {
    "network.default_network": ("Default container network.", "host | docker | nat | disabled"),
    "container_defaults.privileged": ("Enable Docker privileged mode by default for new containers.", "true | false"),
    "workspace.default_path": ("Host path mounted at /workspace by default.", "path | null"),
    "shell.default_shell": ("Shell opened in the container.", "zsh | bash | tmux"),
    "shell.logging.always_enable": ("Record each shell session by default.", "true | false"),
    "shell.logging.method": ("Session recording format.", "asciinema | script"),
    "my_resources.enabled": ("Mount ~/.nihil/my-resources into new containers.", "true | false"),
    "my_resources.path": ("Host path for my-resources.", "path"),
    "nihil_resources.enabled": ("Mount the shared nihil-resources catalog.", "true | false"),
    "nihil_resources.path": ("Host path to the nihil-resources checkout.", "path"),
    "nihil_resources.auto_update": ("Pull nihil-resources at container start.", "true | false"),
    "display.x11_by_default": ("Forward X11/XWayland to new containers.", "true | false"),
    "display.wayland_by_default": ("Forward the Wayland socket to new containers.", "true | false"),
    "updates.auto_check": ("Check for image updates when starting a container.", "true | false"),
    "nihil_history.sync_credentials": ("Import credentials from supported tools into nihil-history.", "true | false"),
    "nihil_history.sync_hosts": ("Import discovered hosts into nihil-history.", "true | false"),
    "build.images_path": ("Default local nihil-images source used by build.", "path | null"),
    "image_sources.home": ("Root directory for image source checkouts.", "path"),
    "image_sources.active": ("Image source used by Nihil.", "upstream | personal"),
    "image_sources.channel": ("Upstream image release channel.", "main | dev"),
    "image_sources.prompt_for_dev": ("Offer the dev image channel during setup.", "true | false"),
    "image_sources.upstream_repo": ("GitHub repository for upstream images.", "owner/repository"),
    "image_sources.upstream_path": ("Local upstream image source checkout.", "path"),
    "image_sources.personal_path": ("Local personal image source checkout.", "path | null"),
    "image_sources.personal_repo": ("GitHub repository for personal images.", "owner/repository | null"),
    "image_sources.personal_branch": ("Branch for personal images.", "branch name | null"),
}

_CONTAINER_INFO = {
    "privileged": ("Override the default Docker privileged setting for this preset.", "true | false | default"),
    "network": ("Docker network or network mode used when creating the container.", "host | docker | nat | disabled | existing network name | default"),
    "image": ("Image variant used for the container.", "full | ad | web | blueteam | local image tag | default"),
    "workspace": ("Host directory mounted at /workspace.", "path | default"),
    "workspace_here": ("Mount the current directory at /workspace.", "true | false | default"),
    "vpn": ("Start OpenVPN inside the container.", "true | false | .ovpn file path | null (off)"),
    "env": ("Environment variables passed to the container; repeat KEY=VALUE entries.", "YAML list of strings | null (none)"),
    "disable_x11": ("Disable X11/XWayland forwarding.", "true | false | default"),
    "disable_wayland": ("Disable Wayland forwarding.", "true | false | default"),
    "no_my_resources": ("Do not mount my-resources.", "true | false | default"),
    "no_nihil_resources": ("Do not mount nihil-resources.", "true | false | default"),
    "browser_ui": ("Enable the browser-based desktop.", "true | false | null (off)"),
    "browser_ui_resolution": ("Browser desktop resolution.", "1280x720 | 1920x1080 | 2560x1440 | null (1280x720)"),
    "browser_ui_port": ("Host port for the browser desktop.", "1-65535 | null for random"),
    "browser_ui_password": ("Browser desktop password; stored in this protected preset file.", "string | null for generated"),
    "log": ("Record the shell session.", "true | false | default"),
    "tmux": ("Open the shell in tmux.", "true | false | null (off)"),
    "no_shell": ("Skip opening a shell after startup.", "true | false | null (open shell)"),
    "scripts": ("Run these startup scripts after container creation.", "YAML list of script names | null (default setup)"),
}

_ENUMS = {
    "network.default_network": ("host", "docker", "nat", "disabled"),
    "shell.default_shell": ("zsh", "bash", "tmux"),
    "shell.logging.method": ("asciinema", "script"),
    "image_sources.active": ("upstream", "personal"),
    "image_sources.channel": ("main", "dev"),
}
_CONTAINER_CYCLE_VALUES = {
    "privileged": (None, True, False),
    "network": (None, "host", "docker", "nat", "disabled"),
    "image": (None, "full", "ad", "web", "blueteam"),
    "browser_ui_resolution": ("1280x720", "1920x1080", "2560x1440"),
}
_STRING_OR_NULL = {
    "workspace.default_path", "build.images_path", "image_sources.personal_path",
    "image_sources.personal_repo", "image_sources.personal_branch",
}
_BOOLEAN_CONTAINER_FIELDS = {
    "privileged", "workspace_here", "disable_x11", "disable_wayland", "no_my_resources",
    "no_nihil_resources", "browser_ui", "log", "tmux", "no_shell",
}
_CONTAINER_LABELS = {
    "privileged": "--privileged",
    "network": "--network",
    "image": "--image",
    "workspace": "--workspace",
    "workspace_here": "--workspace-here",
    "vpn": "--vpn",
    "env": "--env",
    "disable_x11": "--disable-x11",
    "disable_wayland": "--disable-wayland",
    "no_my_resources": "--no-my-resources",
    "no_nihil_resources": "--no-nihil-resources",
    "browser_ui": "--browser-ui",
    "browser_ui_resolution": "--browser-ui-resolution",
    "browser_ui_port": "--browser-ui-port",
    "browser_ui_password": "--browser-ui-password",
    "log": "--log",
    "tmux": "--tmux",
    "no_shell": "--no-shell",
    "scripts": "--startup-script",
}


class PresetSettingsTable(DataTable):
    BINDINGS = [Binding("/", "search", show=False, priority=True)]

    def action_search(self) -> None:
        self.app.action_search()


class PresetConfigEditor(App[tuple[dict, dict] | None]):
    CSS = """
    Screen { layout: vertical; }
    Screen:inline { height: 90vh; }
    #panel-wrap { height: 1fr; width: 100%; align: center middle; }
    #panel { width: 96%; height: 100%; border: round $accent; padding: 1; }
    #title { height: 1; }
    DataTable { height: 1fr; width: 100%; }
    #details { height: 4; }
    #hint { height: 1; }
    Input { height: 3; }
    #message { height: 1; }
    """
    BINDINGS = [
        Binding("j", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("G", "move_to_end", show=False),
        Binding("space", "toggle", "Next allowed value"),
        Binding("e", "edit", "Edit value"),
        Binding("escape", "cancel_edit", show=False),
        Binding("ctrl+s", "save", "Create preset", priority=True),
        Binding("q", "cancel", "Cancel"),
    ]

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = deepcopy(config)
        self.config.pop("container", None)
        self.options = {name: None for name in _CONTAINER_INFO}
        self.rows: list[tuple[str, str, str, str, str]] = []
        self.visible_rows: list[int] = []
        self.editing_row: int | None = None
        self.searching = False
        self.search_filter = ""
        self._last_g_press = 0.0
        self._table_ready = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="panel-wrap"):
            with Container(id="panel"):
                yield Static("Preset editor: config and container options", id="title")
                yield PresetSettingsTable(id="settings", cursor_type="row")
                yield Static("", id="details")
                yield Static("↑/↓ or j/k: move | gg/G: first/last | /: search | Space: next value | e: edit | Ctrl+S: save | q: cancel", id="hint")
                yield Input(placeholder="YAML value, for example: true, null, /home/user/work, [FOO=bar]")
                yield Static("", id="message")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("SECTION", width=34, key="section")
        table.add_column("SETTING", width=28, key="setting")
        table.add_column("VALUE", width=30, key="value")
        self._add_config_rows(table, self.config)
        for name, (description, allowed) in _CONTAINER_INFO.items():
            category = "container"
            self.rows.append(("container", name, category, description, allowed))
            table.add_row(category, _CONTAINER_LABELS[name], self._row_display("container", name, None), key=f"container.{name}")
        self.visible_rows = list(range(len(self.rows)))
        self._table_ready = True
        table.focus()
        self._resize_value_column()
        self._update_details()

    def on_resize(self, event: Resize) -> None:
        if not self._table_ready:
            return
        self._resize_value_column()

    def on_key(self, event: Key) -> None:
        if not self.query_one(DataTable).has_focus:
            self._last_g_press = 0.0
            return
        if event.key != "g":
            self._last_g_press = 0.0
            return
        now = time.monotonic()
        if now - self._last_g_press <= 0.5:
            self.action_move_to_start()
            self._last_g_press = 0.0
        else:
            self._last_g_press = now

    def _resize_value_column(self) -> None:
        table = self.query_one(DataTable)
        fixed_width = sum(table.columns[key].get_render_width(table) for key in ("section", "setting"))
        table.columns["value"].width = max(30, table.size.width - fixed_width - 2 * table.cell_padding)
        table.refresh(layout=True)

    def _add_config_rows(self, table: DataTable, config: dict, prefix: str = "") -> None:
        for key, value in config.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self._add_config_rows(table, value, path)
            else:
                category_key = path.split(".", 1)[0]
                category = category_key
                description, allowed = _CONFIG_INFO.get(
                    path, ("Custom configuration setting.", self._config_hint(path, value))
                )
                setting = path.split(".", 1)[1] if "." in path else path
                self.rows.append(("config", path, category, description, allowed))
                table.add_row(category, setting, self._display_value(value), key=f"config.{path}")

    @staticmethod
    def _config_hint(path: str, value) -> str:
        if path in _ENUMS:
            return " | ".join(_ENUMS[path])
        if isinstance(value, bool):
            return "true | false"
        if value is None:
            return "string | null"
        return type(value).__name__

    @staticmethod
    def _display_value(value) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return value
        return PresetConfigEditor._yaml_value(value)

    @staticmethod
    def _row_display(scope: str, path: str, value) -> str:
        if scope == "container" and value is None:
            defaults = {
                "privileged": "default",
                "network": "default",
                "image": "choose at start",
                "workspace": "default",
                "workspace_here": "false",
                "vpn": "off",
                "env": "none",
                "disable_x11": "default",
                "disable_wayland": "default",
                "no_my_resources": "default",
                "no_nihil_resources": "default",
                "browser_ui": "off",
                "browser_ui_resolution": "1280x720",
                "browser_ui_port": "random",
                "browser_ui_password": "generated",
                "log": "default",
                "tmux": "off",
                "no_shell": "open shell",
                "scripts": "default setup",
            }
            return f"[dim]{defaults[path]}[/]"
        return PresetConfigEditor._display_value(value)

    @staticmethod
    def _yaml_value(value) -> str:
        return yaml.safe_dump(value, default_flow_style=True, sort_keys=False).strip().removesuffix("\n...")

    def _row_value(self, row: int):
        scope, path, *_ = self.rows[row]
        source = self.config if scope == "config" else self.options
        return source[path] if scope == "container" else self._get_path(source, path)

    @staticmethod
    def _get_path(data: dict, path: str):
        value = data
        for part in path.split("."):
            value = value[part]
        return value

    @staticmethod
    def _set_path(data: dict, path: str, value) -> None:
        parts = path.split(".")
        target = data
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._update_details()

    def _update_details(self) -> None:
        row = self.query_one(DataTable).cursor_row
        if row is None or row >= len(self.visible_rows):
            self.query_one("#details", Static).update("")
            return
        source_row = self.visible_rows[row]
        scope, path, category, description, allowed = self.rows[source_row]
        setting = _CONTAINER_LABELS[path] if scope == "container" else path
        value = self._display_value(self._row_value(source_row)) if scope == "config" else self._row_display(scope, path, self._row_value(source_row))
        self.query_one("#details", Static).update(
            f"[bold]{category} · {setting}[/]  {description}\n[bold]Current: {value}[/]  [dim]Allowed: {allowed}[/]"
        )

    def action_search(self) -> None:
        if self.editing_row is not None:
            return
        self.searching = True
        editor = self.query_one(Input)
        editor.placeholder = "Search section, setting, value, or description..."
        editor.value = ""
        editor.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.searching:
            self._search_settings(event.value)

    def _search_settings(self, query: str) -> None:
        query = query.strip().casefold()
        self.search_filter = query
        message = self.query_one("#message", Static)
        matches = []
        for row, (scope, path, category, description, allowed) in enumerate(self.rows):
            if scope == "container":
                setting = _CONTAINER_LABELS[path]
            else:
                setting = path.split(".", 1)[1] if "." in path else path
            value = self._row_value(row)
            searchable = " ".join((
                category, path, setting, description, allowed,
                self._display_value(value), self._row_display(scope, path, value),
            )).casefold()
            if not query or query in searchable:
                matches.append(row)
        self.visible_rows = matches
        table = self.query_one(DataTable)
        table.clear()
        for row in matches:
            scope, path, category, *_ = self.rows[row]
            value = self._row_value(row)
            display = self._row_display(scope, path, value) if scope == "container" else self._display_value(value)
            setting = _CONTAINER_LABELS[path] if scope == "container" else path.split(".", 1)[1] if "." in path else path
            table.add_row(category, setting, display, key=f"{scope}.{path}")
        if matches:
            table.move_cursor(row=0)
            message.update("")
        else:
            message.update(f"No settings match '{query}'.")
        self._update_details()

    def action_move_down(self) -> None:
        table = self.query_one(DataTable)
        table.move_cursor(row=min((table.cursor_row or 0) + 1, max(table.row_count - 1, 0)))
        self._update_details()

    def action_move_up(self) -> None:
        table = self.query_one(DataTable)
        table.move_cursor(row=max((table.cursor_row or 0) - 1, 0))
        self._update_details()

    def action_move_to_start(self) -> None:
        self.query_one(DataTable).move_cursor(row=0)
        self._update_details()

    def action_move_to_end(self) -> None:
        table = self.query_one(DataTable)
        table.move_cursor(row=max(table.row_count - 1, 0))
        self._update_details()

    def action_toggle(self) -> None:
        table = self.query_one(DataTable)
        row = table.cursor_row or 0
        source_row = self.visible_rows[row]
        scope, path, *_ = self.rows[source_row]
        current = self._row_value(source_row)
        if scope == "config":
            choices = _ENUMS.get(path, (False, True) if isinstance(current, bool) else ())
        else:
            choices = _CONTAINER_CYCLE_VALUES.get(path, (None, True, False) if path in _BOOLEAN_CONTAINER_FIELDS else ())
        if not choices:
            self.query_one("#message", Static).update("No preset choices for this value; press e to enter a custom value.")
            return
        value = choices[(choices.index(current) + 1) % len(choices)] if current in choices else choices[0]
        if scope == "config":
            self._set_path(self.config, path, value)
        else:
            self.options[path] = value
        table.update_cell_at(Coordinate(row, 2), self._row_display(scope, path, value))
        self.query_one("#message", Static).update("")
        self._update_details()

    def action_edit(self) -> None:
        table = self.query_one(DataTable)
        row = table.cursor_row or 0
        source_row = self.visible_rows[row]
        scope, path, category, description, allowed = self.rows[source_row]
        current = self._row_value(source_row)
        self.editing_row = source_row
        self.query_one("#details", Static).update(
            f"[bold]{category} · {path}[/]  {description}\n[bold]Current: {self._display_value(current)}[/]  [dim]Allowed: {allowed}[/]"
        )
        editor = self.query_one(Input)
        editor.placeholder = f"Allowed: {allowed}"
        editor.value = self._yaml_value(current)
        editor.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.searching:
            self.searching = False
            self.query_one(DataTable).focus()
            return
        if self._commit_value(event.value):
            self.query_one(DataTable).focus()

    def _commit_value(self, raw_value: str) -> bool:
        if self.editing_row is None:
            return True
        row = self.editing_row
        try:
            value = yaml.safe_load(raw_value)
            self._validate_value(row, value)
        except (TypeError, ValueError, yaml.YAMLError) as error:
            self.query_one("#message", Static).update(str(error))
            return False
        scope, path, *_ = self.rows[row]
        if scope == "config":
            self._set_path(self.config, path, value)
        else:
            self.options[path] = value
        display_row = self.visible_rows.index(row)
        self.query_one(DataTable).update_cell_at(Coordinate(display_row, 2), self._row_display(scope, path, value))
        self.query_one("#message", Static).update("")
        self.editing_row = None
        self.query_one(Input).placeholder = "YAML value, for example: true, null, /home/user/work, [FOO=bar]"
        self._update_details()
        return True

    def _validate_value(self, row: int, value) -> None:
        scope, path, *_ = self.rows[row]
        if scope == "container":
            if path in _BOOLEAN_CONTAINER_FIELDS:
                valid = value is None or isinstance(value, bool)
            elif path in {"network", "image", "workspace", "browser_ui_password"}:
                valid = value is None or (isinstance(value, str) and (path != "network" or bool(value)))
            elif path == "vpn":
                valid = value is None or isinstance(value, (bool, str))
            elif path in {"env", "scripts"}:
                valid = value is None or (isinstance(value, list) and all(isinstance(item, str) for item in value))
            elif path == "browser_ui_resolution":
                valid = value is None or value in {"1280x720", "1920x1080", "2560x1440"}
            elif path == "browser_ui_port":
                valid = value is None or (isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535)
            else:
                valid = False
        else:
            current = self._get_path(self.config, path)
            if path in _STRING_OR_NULL:
                valid = value is None or isinstance(value, str)
            else:
                valid = value is None if current is None else isinstance(value, type(current))
            if isinstance(current, bool):
                valid = isinstance(value, bool)
            if path in _ENUMS:
                valid = isinstance(value, str) and value in _ENUMS[path]
        if not valid:
            raise ValueError(f"Invalid value for {scope}.{path}.")

    def action_save(self) -> None:
        if not self._commit_value(self.query_one(Input).value):
            return
        options = {key: value for key, value in self.options.items() if value is not None}
        if "scripts" in options:
            from nihil.features.config_presets import SETUP_DIR
            from nihil.features.startup_scripts import resolve_startup_scripts
            try:
                scripts = resolve_startup_scripts(options["scripts"])
            except ValueError as error:
                self.query_one("#message", Static).update(str(error))
                return
            options["scripts"] = [str(script.resolve().relative_to(SETUP_DIR.resolve())) for script in scripts]
        self.exit((self.config, options))

    def action_cancel(self) -> None:
        self.exit(None)

    def action_cancel_edit(self) -> None:
        if self.searching or (self.editing_row is None and self.search_filter):
            self.searching = False
            self.query_one(Input).value = ""
            self._search_settings("")
            self.query_one(Input).placeholder = "YAML value, for example: true, null, /home/user/work, [FOO=bar]"
            self.query_one("#message", Static).update("")
            self.query_one(DataTable).focus()
            return
        self.editing_row = None
        self.query_one(Input).placeholder = "YAML value, for example: true, null, /home/user/work, [FOO=bar]"
        self.query_one(DataTable).focus()


def run_config_editor(config: dict) -> tuple[dict, dict] | None:
    return PresetConfigEditor(config).run(inline=True)
