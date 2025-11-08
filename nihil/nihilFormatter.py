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
    
    def table_row(self, items: list, widths: list = None) -> str:
        """Format a table row
        
        Args:
            items: List of items to display
            widths: List of column widths (auto-calculated if None)
        """
        if widths is None:
            widths = [30, 10, 15, 15]  # Default widths
        
        row = "  • "
        for i, item in enumerate(items):
            width = widths[i] if i < len(widths) else 20
            row += f"{str(item):<{width}} "
        return row

