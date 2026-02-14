#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires pour nihilFormatter.py"""

import pytest
from unittest.mock import patch, MagicMock

from nihil.nihilFormatter import NihilFormatter


class TestNihilFormatter:
    """Tests pour la classe NihilFormatter"""
    
    def test_strip_ansi_removes_codes(self):
        """Test _strip_ansi enlève les codes ANSI"""
        formatter = NihilFormatter(use_colors=False)
        
        text_with_ansi = "\033[1;31mRed text\033[0m"
        stripped = formatter._strip_ansi(text_with_ansi)
        
        assert stripped == "Red text"
        assert "\033" not in stripped
    
    def test_strip_ansi_preserves_text(self):
        """Test _strip_ansi préserve le texte normal"""
        formatter = NihilFormatter(use_colors=False)
        
        text = "Normal text without codes"
        stripped = formatter._strip_ansi(text)
        
        assert stripped == text
    
    def test_real_len_ignores_ansi(self):
        """Test _real_len ignore les codes ANSI"""
        formatter = NihilFormatter(use_colors=False)
        
        text_with_ansi = "\033[1;31mHello\033[0m"
        length = formatter._real_len(text_with_ansi)
        
        assert length == 5  # "Hello" fait 5 caractères
    
    def test_success_with_colors(self):
        """Test success() avec couleurs activées"""
        formatter = NihilFormatter(use_colors=True)
        
        result = formatter.success("Operation succeeded")
        
        assert "[✓]" in result
        assert "Operation succeeded" in result
        assert formatter.GREEN in result
        assert formatter.RESET in result
    
    def test_success_without_colors(self):
        """Test success() sans couleurs"""
        formatter = NihilFormatter(use_colors=False)
        
        result = formatter.success("Operation succeeded")
        
        assert "[✓]" in result
        assert "Operation succeeded" in result
        assert formatter.GREEN not in result
        assert formatter.RESET not in result
    
    def test_error_with_colors(self):
        """Test error() avec couleurs"""
        formatter = NihilFormatter(use_colors=True)
        
        result = formatter.error("Operation failed")
        
        assert "[✗]" in result
        assert formatter.RED in result
    
    def test_info_with_colors(self):
        """Test info() avec couleurs"""
        formatter = NihilFormatter(use_colors=True)
        
        result = formatter.info("Information")
        
        assert "[*]" in result
        assert formatter.BLUE in result
    
    def test_warning_with_colors(self):
        """Test warning() avec couleurs"""
        formatter = NihilFormatter(use_colors=True)
        
        result = formatter.warning("Warning message")
        
        assert "[!]" in result
        assert formatter.YELLOW in result
    
    def test_colorize_respects_use_colors(self):
        """Test _colorize respecte use_colors"""
        formatter_colors = NihilFormatter(use_colors=True)
        formatter_no_colors = NihilFormatter(use_colors=False)
        
        colored = formatter_colors._colorize("text", formatter_colors.RED)
        plain = formatter_no_colors._colorize("text", formatter_no_colors.RED)
        
        assert formatter_colors.RED in colored
        assert formatter_colors.RESET in colored
        assert plain == "text"
