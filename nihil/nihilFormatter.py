#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formatter module for Nihil - Handles output formatting"""


class NihilFormatter:
    """Formats output for Nihil commands"""
    
    RED = '\033[1;31m'
    GREEN = '\033[1;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[1;34m'
    MAGENTA = '\033[1;35m'
    CYAN = '\033[1;36m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def __init__(self, use_colors: bool = True):
        """Initialize formatter
        
        Args:
            use_colors: Whether to use ANSI color codes
        """
        self.use_colors = use_colors
        try:
            from rich.console import Console
            self.console = Console()
        except ImportError:
            self.console = None
    
    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled"""
        if self.use_colors:
            return f"{color}{text}{self.RESET}"
        return text
    
    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI color codes from text to get real length"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def _real_len(self, text: str) -> int:
        """Get the real display length of text (without ANSI codes)"""
        return len(self._strip_ansi(text))
    
    def success(self, message: str) -> str:
        """Format success message"""
        return self._colorize(f"[✓] {message}", self.GREEN)
    
    def error(self, message: str) -> str:
        """Format error message"""
        return self._colorize(f"[✗] {message}", self.RED)
    
    def info(self, message: str) -> str:
        """Format info message"""
        return self._colorize(f"[*] {message}", self.BLUE)
    
    def warning(self, message: str) -> str:
        """Format warning message"""
        return self._colorize(f"[!] {message}", self.YELLOW)
    
    def section_header(self, title: str, icon: str = "") -> str:
        """Format section header"""
        header = f"{icon} {title}" if icon else title
        # Removed the dashed line as requested by user
        return f"\n{self._colorize(header, self.BOLD)}"
    
    def print_table(self, columns: list, rows: list, widths: list = None) -> None:
        """Print a nicely formatted table using rich
        
        Args:
            columns: List of column headers
            rows: List of rows (each row is a list of cell data or tuples (data, color))
            widths: Optional fixed widths, otherwise (ignored when using rich)
        """
        if self.console:
            from rich.table import Table
            from rich import box
            from rich.text import Text
            
            table = Table(show_header=True, header_style="bold blue", border_style="bold #d2ac7e",
                          box=box.SQUARE, title_justify="left")
            
            for col in columns:
                table.add_column(str(col))
            
            for row in rows:
                formatted_row = []
                for cell in row:
                    if isinstance(cell, tuple):
                        text = str(cell[0])
                        color = cell[1]
                        # Use Text.from_ansi to let Rich handle the length calculation correctly
                        # ignoring invisible escape codes for width but keeping styling
                        ansi_string = f"{color}{text}{self.RESET}"
                        formatted_row.append(Text.from_ansi(ansi_string))
                    else:
                        # Even plain strings might contain ANSI codes if pre-formatted
                        formatted_row.append(Text.from_ansi(str(cell)))
                table.add_row(*formatted_row)
                
            self.console.print(table)
        else:
            # Fallback if rich is not installed (should not happen with new setup)
            import shutil
            
            try:
                terminal_width = shutil.get_terminal_size().columns
            except (OSError, AttributeError):
                terminal_width = 80
            
            min_widths = [len(str(c)) + 2 for c in columns]
            
            if widths is None:
                widths = min_widths.copy()
                for row in rows:
                    for i, cell in enumerate(row):
                        text = str(cell[0]) if isinstance(cell, tuple) else str(cell)
                        if i < len(widths):
                            widths[i] = max(widths[i], len(text) + 2)
            else:
                for i in range(len(widths)):
                    if widths[i] < min_widths[i]:
                        widths[i] = min_widths[i]
            
            h, v = "─", "│"
            tl, tr, bl, br = "┌", "┐", "└", "┘"
            tm, bm, lm, rm = "┬", "┴", "├", "┤"
            c = "┼"
            
            def print_sep(left, mid, right, char):
                line_parts = []
                for i, w in enumerate(widths):
                    line_parts.append(char * w)
                line = left + mid.join(line_parts) + right
                print(self._colorize(line, self.CYAN))

            print_sep(tl, tm, tr, h)
            
            header_row = self._colorize(v, self.CYAN)
            for i, col in enumerate(columns):
                max_w = widths[i] - 2
                col_text = str(col).ljust(max_w)
                header_row += f" {self._colorize(col_text, self.BOLD)} {self._colorize(v, self.CYAN)}"
            print(header_row)
            
            print_sep(lm, c, rm, h)
            
            for row in rows:
                line = self._colorize(v, self.CYAN)
                for i, cell in enumerate(row):
                    if i >= len(widths): break
                    
                    text = str(cell)
                    color = None
                    
                    if isinstance(cell, tuple):
                        text = str(cell[0])
                        color = cell[1]
                    
                    max_w = widths[i] - 2
                    text_formatted = text.ljust(max_w)
                    
                    if color:
                        text_colored = self._colorize(text_formatted, color)
                    else:
                        text_colored = text_formatted
                    
                    line += f" {text_colored} {self._colorize(v, self.CYAN)}"
                print(line)
                
            print_sep(bl, bm, br, h)



