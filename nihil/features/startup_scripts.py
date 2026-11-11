"""Selector for scripts run once when a container is created."""

from pathlib import Path
from shutil import get_terminal_size
from time import monotonic

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Static

from nihil.config.defaults import NIHIL_HOME


SETUP_DIR = NIHIL_HOME / "my-resources" / "setup"
SCRIPT_DIR = SETUP_DIR / "scripts"


def _script_description(script: Path) -> str:
    try:
        for line in script.read_text(errors="replace").splitlines():
            comment = line.strip()
            if comment.startswith("#") and not comment.startswith("#!"):
                if description := comment[1:].strip():
                    return description
    except OSError:
        pass
    return ""


class StartupScriptSelector(App[list[Path] | None]):
    CSS = """
    Screen { layout: vertical; }
    Screen:inline { height: 70vh; }
    #panel-wrap { height: 1fr; width: 100%; align: center middle; }
    #panel { width: 95%; height: 100%; border: round $accent; padding: 1; }
    #title { height: 1; }
    DataTable { height: 1fr; }
    """
    BINDINGS = [
        Binding("j", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("space", "toggle", "Select"),
        Binding("enter", "select", "Run selected", priority=True),
        Binding("q", "cancel", "Cancel"),
    ]

    def __init__(self, scripts: list[Path]) -> None:
        super().__init__()
        self.scripts = scripts
        self.selected: set[Path] = set()
        self.descriptions: list[str] = []
        self.description_width = 0
        self.scrolling_row: int | None = None
        self.description_offset = 0
        self.row_selected_at = 0.0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="panel-wrap"):
            with Container(id="panel"):
                yield Static("Choose scripts to run when the container starts", id="title")
                yield Static("↑/↓ or j/k: move | Space: select multiple | Enter: run selected or current | q: cancel")
                yield DataTable(id="scripts", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        script_width = max(len("SCRIPT"), *(len(script.name) for script in self.scripts))
        table.add_column("SELECT", width=8)
        table.add_column("SCRIPT", width=script_width)
        self.description_width = max(8, int(get_terminal_size().columns * 0.95) - script_width - 18)
        table.add_column("DESCRIPTION", width=self.description_width)
        for script in self.scripts:
            self.descriptions.append(_script_description(script))
            table.add_row("[ ]", script.name, self.descriptions[-1])
        table.focus()
        self.set_interval(0.1, self._scroll_description)

    def _scroll_description(self) -> None:
        table = self.query_one(DataTable)
        row = table.cursor_row
        if row != self.scrolling_row:
            if self.scrolling_row is not None:
                table.update_cell_at(Coordinate(self.scrolling_row, 2), self.descriptions[self.scrolling_row])
            self.scrolling_row = row
            self.description_offset = 0
            self.row_selected_at = monotonic()
            return
        if row is None or len(self.descriptions[row]) <= self.description_width:
            return
        if monotonic() - self.row_selected_at < 2:
            return

        loop = f"{self.descriptions[row]}   "
        self.description_offset = (self.description_offset + 1) % len(loop)
        frame = (loop + loop)[self.description_offset:self.description_offset + self.description_width]
        table.update_cell_at(Coordinate(row, 2), frame)

    def action_move_down(self) -> None:
        table = self.query_one(DataTable)
        table.move_cursor(row=min((table.cursor_row or 0) + 1, max(table.row_count - 1, 0)))

    def action_move_up(self) -> None:
        table = self.query_one(DataTable)
        table.move_cursor(row=max((table.cursor_row or 0) - 1, 0))

    def action_toggle(self) -> None:
        table = self.query_one(DataTable)
        row = table.cursor_row or 0
        script = self.scripts[row]
        if script in self.selected:
            self.selected.remove(script)
            marker = "[ ]"
        else:
            self.selected.add(script)
            marker = "[✓]"
        table.update_cell_at(Coordinate(row, 0), marker)

    def action_select(self) -> None:
        selected = [script for script in self.scripts if script in self.selected]
        if not selected and self.scripts:
            selected = [self.scripts[self.query_one(DataTable).cursor_row or 0]]
        self.exit(selected)

    def action_cancel(self) -> None:
        self.exit(None)


def select_startup_scripts() -> list[Path] | None:
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    scripts = [SETUP_DIR / "load_user_setup.sh", *sorted(SCRIPT_DIR.glob("*.sh"))]
    return StartupScriptSelector(scripts).run(inline=True)


def resolve_startup_scripts(names: list[str]) -> list[Path]:
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    scripts = [SETUP_DIR / "load_user_setup.sh", *sorted(SCRIPT_DIR.glob("*.sh"))]
    by_name = {script.name: script for script in scripts}
    unknown = set(names) - by_name.keys()
    if unknown:
        raise ValueError(f"Unknown startup script(s): {', '.join(sorted(unknown))}")
    return [by_name[name] for name in names]
