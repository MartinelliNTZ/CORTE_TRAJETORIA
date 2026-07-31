#!/usr/bin/env python3
"""
core/styles.py
─────────────────────────────────────────────────────────────────────────────
Centraliza a identidade visual da aplicação: paleta de cores, fontes e o
stylesheet (QSS) usado em toda a interface PySide6.

Tema: "Dark Premium" — preto profundo + dourado, inspirado em painéis de
controle de drones/aeronaves (HUD escuro, detalhes metálicos dourados).

Qualquer outra classe/widget da aplicação pode reaproveitar este módulo:

    from core.styles import Styles, Colors

    self.setStyleSheet(Styles.get_stylesheet())
    label.setStyleSheet(f"color: {Colors.GOLD};")
"""


class Colors:
    """Paleta de cores centralizada do tema Dark Premium (Preto & Dourado)."""

    # Fundo / superfícies
    BLACK = "#07070a"
    BLACK_SOFT = "#0d0d12"
    PANEL = "#121218"
    PANEL_ALT = "#181820"
    ELEVATED = "#1e1e28"
    BORDER = "#2a2a35"
    BORDER_LIGHT = "#3a3a48"

    # Dourado (acentos, destaques, foco)
    GOLD = "#d4af37"
    GOLD_LIGHT = "#f4d76a"
    GOLD_SOFT = "#e6c766"
    GOLD_DARK = "#9c7c22"
    GOLD_DIM = "#4a3d1a"

    # Texto
    TEXT = "#eae7dd"
    TEXT_MUTED = "#9a9aa4"
    TEXT_FAINT = "#5f5f6b"

    # Status
    SUCCESS = "#4fd67a"
    ERROR = "#e0575a"
    WARNING = "#e0a952"
    INFO = "#5aa9e0"

    # Console (terminal estilo HUD)
    CONSOLE_BG = "#08090a"
    CONSOLE_TEXT = "#e0c878"
    CONSOLE_BORDER = "#3a3122"


class Styles:
    """Fornece o stylesheet global (QSS) e helpers de tipografia."""

    FONT_FAMILY = "Segoe UI, Roboto, Arial"
    FONT_FAMILY_MONO = "Cascadia Code, Consolas, 'Courier New', monospace"

    @staticmethod
    def font_family() -> str:
        return Styles.FONT_FAMILY

    @staticmethod
    def font_family_mono() -> str:
        return Styles.FONT_FAMILY_MONO

    @staticmethod
    def get_stylesheet() -> str:
        c = Colors
        return f"""
        /* ─────────────────────────── BASE ─────────────────────────── */
        QMainWindow, QWidget {{
            background-color: {c.BLACK};
            color: {c.TEXT};
            font-family: {Styles.FONT_FAMILY};
            font-size: 13px;
        }}

        QWidget#centralWidget {{
            background-color: {c.BLACK};
        }}

        /* ───────────────────────── HEADER BAR ─────────────────────── */
        QFrame#headerBar {{
            background-color: {c.BLACK_SOFT};
            border-bottom: 2px solid {c.GOLD_DIM};
        }}

        QLabel#titleLabel {{
            color: {c.GOLD_LIGHT};
            font-size: 20px;
            font-weight: 700;
            letter-spacing: 2px;
        }}

        QLabel#subtitleLabel {{
            color: {c.TEXT_MUTED};
            font-size: 11px;
            letter-spacing: 1px;
        }}

        /* ─────────────────────────── GROUPBOX ─────────────────────── */
        QGroupBox {{
            background-color: {c.PANEL};
            border: 1px solid {c.BORDER};
            border-radius: 8px;
            margin-top: 14px;
            padding: 14px 10px 10px 10px;
            font-weight: 600;
            color: {c.GOLD_SOFT};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            top: 2px;
            padding: 0 6px;
            color: {c.GOLD_LIGHT};
            font-size: 12px;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}

        /* ─────────────────────────── LABELS ───────────────────────── */
        QLabel {{
            color: {c.TEXT};
        }}

        QLabel[role="hint"] {{
            color: {c.TEXT_FAINT};
            font-size: 11px;
            font-style: italic;
        }}

        QLabel[role="value"] {{
            color: {c.GOLD};
            font-weight: 600;
        }}

        /* ─────────────────────────── BUTTONS ──────────────────────── */
        QPushButton {{
            background-color: {c.PANEL_ALT};
            color: {c.TEXT};
            border: 1px solid {c.BORDER_LIGHT};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 600;
        }}

        QPushButton:hover {{
            background-color: {c.ELEVATED};
            border: 1px solid {c.GOLD_DARK};
            color: {c.GOLD_LIGHT};
        }}

        QPushButton:pressed {{
            background-color: {c.BLACK_SOFT};
            border: 1px solid {c.GOLD};
        }}

        QPushButton:disabled {{
            background-color: {c.PANEL};
            color: {c.TEXT_FAINT};
            border: 1px solid {c.BORDER};
        }}

        QPushButton#primaryButton {{
            background-color: {c.GOLD_DIM};
            color: {c.GOLD_LIGHT};
            border: 1px solid {c.GOLD_DARK};
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 1px;
        }}

        QPushButton#primaryButton:hover {{
            background-color: {c.GOLD_DARK};
            color: {c.BLACK};
            border: 1px solid {c.GOLD_LIGHT};
        }}

        QPushButton#primaryButton:pressed {{
            background-color: {c.GOLD};
            color: {c.BLACK};
        }}

        QPushButton#dangerButton {{
            border: 1px solid #5a2a2a;
            color: {c.ERROR};
        }}

        QPushButton#dangerButton:hover {{
            background-color: #2a1414;
            border: 1px solid {c.ERROR};
        }}

        /* ───────────────────────── INPUTS ─────────────────────────── */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {c.BLACK_SOFT};
            color: {c.TEXT};
            border: 1px solid {c.BORDER};
            border-radius: 5px;
            padding: 6px 8px;
            selection-background-color: {c.GOLD_DIM};
            selection-color: {c.GOLD_LIGHT};
        }}

        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid {c.GOLD};
        }}

        QLineEdit:read-only {{
            color: {c.TEXT_MUTED};
            background-color: {c.PANEL};
        }}

        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background-color: {c.PANEL_ALT};
            border: none;
            width: 16px;
        }}

        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            image: none;
            border-bottom: 4px solid {c.GOLD};
            width: 0; height: 0;
        }}

        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            image: none;
            border-top: 4px solid {c.GOLD};
            width: 0; height: 0;
        }}

        /* ─────────────────────────── LISTS ────────────────────────── */
        QListWidget {{
            background-color: {c.BLACK_SOFT};
            border: 1px solid {c.BORDER};
            border-radius: 6px;
            padding: 4px;
            outline: none;
        }}

        QListWidget::item {{
            padding: 6px 8px;
            border-radius: 4px;
            color: {c.TEXT};
        }}

        QListWidget::item:selected {{
            background-color: {c.GOLD_DIM};
            color: {c.GOLD_LIGHT};
        }}

        QListWidget::item:hover {{
            background-color: {c.PANEL_ALT};
        }}

        /* ─────────────────────────── CONSOLE ──────────────────────── */
        QPlainTextEdit#consoleWidget {{
            background-color: {c.CONSOLE_BG};
            color: {c.CONSOLE_TEXT};
            border: 1px solid {c.CONSOLE_BORDER};
            border-radius: 6px;
            font-family: {Styles.FONT_FAMILY_MONO};
            font-size: 12px;
            padding: 8px;
            selection-background-color: {c.GOLD_DIM};
        }}

        /* ───────────────────────── PROGRESS BAR ───────────────────── */
        QProgressBar {{
            background-color: {c.BLACK_SOFT};
            border: 1px solid {c.BORDER};
            border-radius: 5px;
            text-align: center;
            color: {c.TEXT};
            height: 16px;
        }}

        QProgressBar::chunk {{
            background-color: {c.GOLD};
            border-radius: 4px;
        }}

        /* ───────────────────────── SCROLLBARS ─────────────────────── */
        QScrollBar:vertical {{
            background: {c.BLACK_SOFT};
            width: 10px;
            margin: 0;
            border-radius: 5px;
        }}

        QScrollBar::handle:vertical {{
            background: {c.GOLD_DIM};
            border-radius: 5px;
            min-height: 24px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {c.GOLD_DARK};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}

        QScrollBar:horizontal {{
            background: {c.BLACK_SOFT};
            height: 10px;
            border-radius: 5px;
        }}

        QScrollBar::handle:horizontal {{
            background: {c.GOLD_DIM};
            border-radius: 5px;
            min-width: 24px;
        }}

        /* ─────────────────────────── SPLITTER ─────────────────────── */
        QSplitter::handle {{
            background-color: {c.BORDER};
        }}

        QSplitter::handle:hover {{
            background-color: {c.GOLD_DIM};
        }}

        /* ───────────────────────── STATUS BAR ─────────────────────── */
        QStatusBar {{
            background-color: {c.BLACK_SOFT};
            color: {c.TEXT_MUTED};
            border-top: 1px solid {c.BORDER};
        }}

        /* ───────────────────────── TOOLTIPS ───────────────────────── */
        QToolTip {{
            background-color: {c.ELEVATED};
            color: {c.GOLD_LIGHT};
            border: 1px solid {c.GOLD_DARK};
            padding: 4px 6px;
        }}

        /* ─────────────────────────── CHECKBOX ─────────────────────── */
        QCheckBox {{
            color: {c.TEXT};
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {c.BORDER_LIGHT};
            border-radius: 3px;
            background-color: {c.BLACK_SOFT};
        }}

        QCheckBox::indicator:checked {{
            background-color: {c.GOLD};
            border: 1px solid {c.GOLD_LIGHT};
        }}

        /* ───────────────────────── SEPARATOR LINE ─────────────────── */
        QFrame[frameShape="4"], QFrame#hLine {{
            color: {c.BORDER};
            background-color: {c.BORDER};
            max-height: 1px;
        }}
        """
