#!/usr/bin/env python3
"""Textual checkbox selector for customizing Nihil image tools."""

from __future__ import annotations

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Input, Static


class ToolSearchInput(Input):
    """Search input that accepts Tab as an alternative to Enter."""

    BINDINGS = [Binding("tab", "confirm_search", "Confirm", show=False)]

    def action_confirm_search(self) -> None:
        app = self.app
        app._set_search_query(self.value)
        app._close_search(clear=False)


class ToolSelectorApp(App[set[str] | None]):
    """Interactive tool selector with Vim-style search and visual ranges."""

    CSS = """
    Screen { layout: vertical; }
    #title { height: 1; padding-left: 1; }
    #status { height: 1; padding-left: 1; color: $text-muted; }
    #search { display: none; height: 3; border: solid $accent; }
    #tools { height: 1fr; }
    """

    BINDINGS = [
        Binding("q", "cancel", "Cancel"),
        Binding("escape", "escape_mode", "Escape"),
        Binding("enter", "save", "Save", priority=True),
        Binding("space", "toggle", "Toggle"),
        Binding("v", "visual_toggle", "Visual"),
        Binding("/", "search_open", "Search", show=False),
        Binding("j", "move_down", "↓", show=False),
        Binding("k", "move_up", "↑", show=False),
        Binding("g", "move_top", "Top", show=False),
        Binding("G", "move_bottom", "Bottom", show=False),
    ]

    def __init__(self, tools: list[dict], disabled: set[str], title: str) -> None:
        super().__init__()
        self.tools = tools
        self.disabled = set(disabled)
        self.title_text = title
        self.search_query = ""
        self.visible_indices: list[int] = []
        self.visual_mode = False
        self.visual_anchor = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container():
            yield Static(self.title_text, id="title")
            yield Static(
                "↑/↓ or j/k: move | /: search | Space: toggle | v: select range | Enter: save | q: cancel",
                id="status",
            )
            yield ToolSearchInput(placeholder="/search...", id="search")
            yield DataTable(id="tools", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self._render_table()
        self.query_one("#tools", DataTable).focus()

    def _table(self) -> DataTable:
        return self.query_one("#tools", DataTable)

    def _cursor_row(self) -> int:
        return max(0, self._table().cursor_row or 0)

    def _tool_index(self, row: int | None = None) -> int:
        row = self._cursor_row() if row is None else row
        return self.visible_indices[min(row, len(self.visible_indices) - 1)]

    def _visual_rows(self) -> range:
        current = self._cursor_row()
        return range(min(self.visual_anchor, current), max(self.visual_anchor, current) + 1)

    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def _matches_search(self, tool: dict) -> bool:
        if not self.search_query:
            return True
        return any(
            self.search_query in str(tool.get(field, "")).lower()
            for field in ("name", "category", "cmd")
        )

    def _render_table(self) -> None:
        table = self._table()
        cursor = self._cursor_row() if self.tools else 0
        self.visible_indices = [
            index for index, tool in enumerate(self.tools)
            if self._matches_search(tool)
        ]
        cursor = min(cursor, max(len(self.visible_indices) - 1, 0))
        visual_rows = (
            range(min(self.visual_anchor, cursor), max(self.visual_anchor, cursor) + 1)
            if self.visual_mode
            else range(0)
        )
        table.clear(columns=True)
        table.add_column("", width=3)
        table.add_column("STATE", width=6)
        table.add_column("TOOL")
        table.add_column("CATEGORY")
        table.add_column("COMMAND")
        for row, index in enumerate(self.visible_indices):
            tool = self.tools[index]
            enabled = tool["mandatory"] or tool["name"] not in self.disabled
            marker = "▶" if row in visual_rows else " "
            state = "REQ" if tool["mandatory"] else ("ON" if enabled else "OFF")
            table.add_row(
                marker, state, tool["name"], tool["category"], tool.get("cmd", "-"), key=str(index)
            )
        if self.visible_indices:
            table.move_cursor(row=cursor, column=0)

    def _refresh_visual_markers(self) -> None:
        """Update range markers without rebuilding the table or its scroll state."""
        table = self._table()
        selected = self._visual_rows()
        for row in range(table.row_count):
            table.update_cell_at(Coordinate(row, 0), "▶" if row in selected else " ")

    def action_move_down(self) -> None:
        table = self._table()
        table.move_cursor(row=min(self._cursor_row() + 1, max(table.row_count - 1, 0)))
        if self.visual_mode:
            self._refresh_visual_markers()
            self._set_status(self._visual_status())

    def action_move_up(self) -> None:
        self._table().move_cursor(row=max(self._cursor_row() - 1, 0))
        if self.visual_mode:
            self._refresh_visual_markers()
            self._set_status(self._visual_status())

    def action_move_top(self) -> None:
        self._table().move_cursor(row=0)
        if self.visual_mode:
            self._refresh_visual_markers()
            self._set_status(self._visual_status())

    def action_move_bottom(self) -> None:
        table = self._table()
        table.move_cursor(row=max(table.row_count - 1, 0))
        if self.visual_mode:
            self._refresh_visual_markers()
            self._set_status(self._visual_status())

    def action_visual_toggle(self) -> None:
        if not self.visible_indices:
            return
        self.visual_mode = not self.visual_mode
        if self.visual_mode:
            self.visual_anchor = self._cursor_row()
            self._set_status(self._visual_status())
        else:
            self._set_status("Normal mode")
        self._render_table()

    def _visual_status(self) -> str:
        return f"VISUAL | {len(self._visual_rows())} row(s) selected | Space: toggle range | v: exit visual mode"

    def action_toggle(self) -> None:
        rows = self._visual_rows() if self.visual_mode else range(self._cursor_row(), self._cursor_row() + 1)
        indexes = [self._tool_index(row) for row in rows if row < len(self.visible_indices)]
        mutable = [index for index in indexes if not self.tools[index]["mandatory"]]
        if not mutable:
            self.visual_mode = False
            self._render_table()
            self._set_status("Core tools are required and cannot be disabled")
            return
        disable = any(self.tools[index]["name"] not in self.disabled for index in mutable)
        for index in mutable:
            name = self.tools[index]["name"]
            (self.disabled.add if disable else self.disabled.discard)(name)
        was_visual = self.visual_mode
        self.visual_mode = False
        self._render_table()
        suffix = "; visual mode ended" if was_visual else ""
        self._set_status(f"{'Disabled' if disable else 'Enabled'} {len(mutable)} tool(s){suffix}")

    def action_search_open(self) -> None:
        search = self.query_one("#search", ToolSearchInput)
        search.display = True
        search.focus()

    def action_escape_mode(self) -> None:
        search = self.query_one("#search", ToolSearchInput)
        if search.display and search.has_focus:
            self._close_search()
            return
        if self.visual_mode:
            self.visual_mode = False
            self._render_table()
            self._set_status("Normal mode")

    def _set_search_query(self, value: str) -> None:
        self.search_query = value.strip().lower()
        self._render_table()
        self._set_status(f"Search: {self.search_query or 'all tools'} | {len(self.visible_indices)} result(s)")

    def _close_search(self, *, clear: bool = True) -> None:
        search = self.query_one("#search", ToolSearchInput)
        search.display = False
        if clear:
            search.value = ""
            self._set_search_query("")
        self._table().focus()

    @on(Input.Changed, "#search")
    def _on_search_changed(self, event: Input.Changed) -> None:
        self._set_search_query(event.value)

    @on(Input.Submitted, "#search")
    def _on_search_submitted(self, event: Input.Submitted) -> None:
        self._set_search_query(event.value)
        self._close_search(clear=False)

    def on_key(self, event) -> None:
        search = self.query_one("#search", ToolSearchInput)
        if event.key == "enter" and search.display and search.has_focus:
            self._set_search_query(search.value)
            self._close_search(clear=False)
            event.stop()
            return
        if event.key == "escape" and search.display and search.has_focus:
            self._close_search()
            event.stop()

    def action_save(self) -> None:
        search = self.query_one("#search", ToolSearchInput)
        if search.display and search.has_focus:
            self._set_search_query(search.value)
            self._close_search(clear=False)
            return
        self.exit(result=self.disabled)

    def action_cancel(self) -> None:
        self.exit(result=None)
