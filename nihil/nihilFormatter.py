#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formatter module for Nihil - Handles output formatting"""


class NihilFormatter:
    """Formats output for Nihil commands"""
    
    # ANSI color codes
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
    
    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled"""
        if self.use_colors:
            return f"{color}{text}{self.RESET}"
        return text
    
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
        return f"\n{self._colorize(header, self.BOLD)}\n{self._colorize('─' * 60, self.CYAN)}"
    
    def print_table(self, columns: list, rows: list, widths: list = None) -> None:
        """Print a nicely formatted table using box-drawing characters
        
        Args:
            columns: List of column headers
            rows: List of rows (each row is a list of cell data or tuples (data, color))
            widths: Optional fixed widths, otherwise auto-calculated
        """
        # Auto-calculate widths if not provided
        if widths is None:
            widths = [len(str(c)) + 2 for c in columns]
            for row in rows:
                for i, cell in enumerate(row):
                    # Handle cell being a tuple (text, color)
                    text = str(cell[0]) if isinstance(cell, tuple) else str(cell)
                    if i < len(widths):
                        widths[i] = max(widths[i], len(text) + 2)
            # Add padding
            widths = [w + 2 for w in widths]

        # Border characters
        h, v = "─", "│"
        tl, tr, bl, br = "┌", "┐", "└", "┘"
        tm, bm, lm, rm = "┬", "┴", "├", "┤"
        c = "┼"
        
        def print_sep(left, mid, right, char):
            line = left
            for i, w in enumerate(widths):
                line += char * w
                if i < len(widths) - 1:
                    line += mid
            line += right
            print(self._colorize(line, self.CYAN))

        # Top border
        print_sep(tl, tm, tr, h)
        
        # Headers
        header_row = v
        for i, col in enumerate(columns):
            header_row += f" {self._colorize(str(col).center(widths[i]-2), self.BOLD)} {self._colorize(v, self.CYAN)}"
        print(self._colorize(header_row, self.CYAN).replace(self.CYAN + " " + self.BOLD, " " + self.BOLD)) # Fix coloring artifact
        
        # Header separator
        print_sep(lm, c, rm, h)
        
        # Rows
        for row in rows:
            line = self._colorize(v, self.CYAN)
            for i, cell in enumerate(row):
                if i >= len(widths): break
                
                text = str(cell)
                color = None
                
                if isinstance(cell, tuple):
                    text = str(cell[0])
                    color = cell[1]
                
                # Truncate
                max_w = widths[i] - 2
                if len(text) > max_w:
                    text = text[:max_w-1] + "…"
                    
                formatted_text = f" {text:<{max_w}} "
                if color:
                    formatted_text = self._colorize(formatted_text, color)
                
                line += f"{formatted_text}{self._colorize(v, self.CYAN)}"
            print(line)
            
        # Bottom border
        print_sep(bl, bm, br, h)



