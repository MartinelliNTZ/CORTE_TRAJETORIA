#!/usr/bin/env python3
"""
main.py
─────────────────────────────────────────────────────────────────────────────
Aplicação PySide6 — "CORTE DE TRAJETÓRIA"
Tema visual: Dark Premium (Preto & Dourado), inspirado em painéis de
controle de drones.

Responsabilidades desta primeira versão:
  • Selecionar um ou mais arquivos .las/.laz
  • Selecionar a pasta de trajetórias
  • Editar as constantes de processamento (CHUNK_SIZE, TIME_MARGIN)
  • Exibir um console de saída (captura os prints do sistema) que poderá
    ser reutilizado pelas próximas classes (LasManager, TrajectoryManager...)

As demais classes de negócio (core.las_manager, core.trajectory_manager)
serão plugadas depois. Basta que elas usem `print(...)` normalmente — o
console desta janela já captura toda a stdout/stderr da aplicação.
"""

import sys
import os
import math
from datetime import datetime

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, QIcon, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QPlainTextEdit, QSpinBox, QDoubleSpinBox, QFileDialog, QFrame, QSplitter,
    QStatusBar, QSizePolicy, QAbstractItemView
)

from core.styles import Styles, Colors


# ═══════════════════════════════════════════════════════════════════════
# REDIRECIONAMENTO DE STDOUT/STDERR -> CONSOLE DA INTERFACE
# ═══════════════════════════════════════════════════════════════════════
class StreamRedirector(QObject):
    """
    Objeto "file-like" que substitui sys.stdout / sys.stderr.
    Qualquer print() feito por qualquer classe da aplicação passa a ser
    emitido como sinal Qt e exibido no ConsoleWidget.
    """
    text_written = Signal(str)

    def write(self, text: str):
        if text:
            self.text_written.emit(str(text))

    def flush(self):
        pass


class ConsoleWidget(QPlainTextEdit):
    """
    Console de saída reutilizável (estilo terminal/HUD).
    Outras classes podem simplesmente continuar usando print(...) — não
    precisam conhecer este widget. Caso queiram escrever diretamente nele,
    basta chamar `console.append_line(texto)`.
    """

    MAX_BLOCKS = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("consoleWidget")
        self.setReadOnly(True)
        self.setMaximumBlockCount(self.MAX_BLOCKS)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._buffer = ""

    def append_line(self, text: str):
        self.insertPlainText(text)
        # Auto-scroll para o final
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def write_stream(self, text: str):
        """Slot conectado ao StreamRedirector.text_written."""
        self.append_line(text)


# ═══════════════════════════════════════════════════════════════════════
# WIDGET DECORATIVO ANIMADO: "DRONE SPINNER"
# ═══════════════════════════════════════════════════════════════════════
class DroneSpinner(QWidget):
    """
    Pequeno widget decorativo: desenha um drone estilizado (corpo em X com
    4 rotores) cujos rotores giram continuamente. Puramente estético —
    reforça a identidade visual "drone" do header.
    """

    def __init__(self, parent=None, size: int = 40):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)  # ~33 fps

    def _tick(self):
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        arm = w * 0.34
        rotor_r = w * 0.11

        gold = QColor(Colors.GOLD)
        gold_light = QColor(Colors.GOLD_LIGHT)
        dim = QColor(Colors.GOLD_DIM)

        # Braços do drone (X)
        pen = QPen(QColor(Colors.BORDER_LIGHT))
        pen.setWidthF(2.2)
        painter.setPen(pen)
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            painter.drawLine(
                cx, cy,
                cx + dx * arm * 0.7, cy + dy * arm * 0.7
            )

        # Rotores (giram)
        for i, (dx, dy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
            rx = cx + dx * arm * 0.7
            ry = cy + dy * arm * 0.7
            grad = QLinearGradient(rx - rotor_r, ry - rotor_r, rx + rotor_r, ry + rotor_r)
            grad.setColorAt(0, gold_light)
            grad.setColorAt(1, dim)
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)

            painter.save()
            painter.translate(rx, ry)
            painter.rotate(self._angle * (1 if i % 2 == 0 else -1))
            # "pás" do rotor — duas linhas cruzadas simulando giro (blur look)
            blade_pen = QPen(gold_light)
            blade_pen.setWidthF(1.6)
            painter.setPen(blade_pen)
            painter.drawLine(-rotor_r, 0, rotor_r, 0)
            painter.drawLine(0, -rotor_r * 0.4, 0, rotor_r * 0.4)
            painter.restore()

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(gold))
            painter.drawEllipse(QRectF(rx - 2.5, ry - 2.5, 5, 5))

        # Corpo central
        body_grad = QLinearGradient(cx - 6, cy - 6, cx + 6, cy + 6)
        body_grad.setColorAt(0, gold_light)
        body_grad.setColorAt(1, gold)
        painter.setBrush(QBrush(body_grad))
        painter.setPen(QPen(QColor(Colors.BLACK_SOFT), 1))
        painter.drawEllipse(QRectF(cx - 7, cy - 7, 14, 14))

        painter.end()


# ═══════════════════════════════════════════════════════════════════════
# HEADER (título + subtítulo + spinner animado + pulso no título)
# ═══════════════════════════════════════════════════════════════════════
class HeaderBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("headerBar")
        self.setFixedHeight(78)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)

        self.spinner = DroneSpinner(size=48)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = QLabel("CORTE DE TRAJETÓRIA")
        self.title_label.setObjectName("titleLabel")
        self.subtitle_label = QLabel("SISTEMA DE PROCESSAMENTO DE NUVEM DE PONTOS · LAS/LAZ")
        self.subtitle_label.setObjectName("subtitleLabel")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)

        layout.addWidget(self.spinner)
        layout.addSpacing(14)
        layout.addLayout(title_box)
        layout.addStretch(1)

        self.status_dot = QLabel("● PRONTO")
        self.status_dot.setStyleSheet(f"color: {Colors.SUCCESS}; font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(self.status_dot, alignment=Qt.AlignRight | Qt.AlignVCenter)

        # Pulso sutil de brilho no título, sem dependências externas de animação
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_phase = 0.0
        self._pulse_timer.start(60)

    def _pulse(self):
        self._pulse_phase += 0.08
        factor = (math.sin(self._pulse_phase) + 1) / 2  # 0..1
        base = QColor(Colors.GOLD)
        light = QColor(Colors.GOLD_LIGHT)
        r = int(base.red() + (light.red() - base.red()) * factor)
        g = int(base.green() + (light.green() - base.green()) * factor)
        b = int(base.blue() + (light.blue() - base.blue()) * factor)
        self.title_label.setStyleSheet(
            f"color: rgb({r},{g},{b}); font-size: 20px; font-weight: 700; letter-spacing: 2px;"
        )

    def set_status(self, text: str, color: str):
        self.status_dot.setText(f"● {text}")
        self.status_dot.setStyleSheet(f"color: {color}; font-weight: 700; letter-spacing: 1px;")


# ═══════════════════════════════════════════════════════════════════════
# PAINEL: CONSTANTES DE PROCESSAMENTO
# ═══════════════════════════════════════════════════════════════════════
class ConstantsPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Constantes de Processamento", parent)
        grid = QGridLayout(self)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(QLabel("CHUNK_SIZE (pontos por bloco):"), 0, 0)
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(1_000, 50_000_000)
        self.chunk_size_spin.setSingleStep(100_000)
        self.chunk_size_spin.setValue(1_000_000)
        self.chunk_size_spin.setGroupSeparatorShown(True)
        grid.addWidget(self.chunk_size_spin, 0, 1)

        grid.addWidget(QLabel("TIME_MARGIN (segundos):"), 1, 0)
        self.time_margin_spin = QDoubleSpinBox()
        self.time_margin_spin.setRange(0.0, 3600.0)
        self.time_margin_spin.setSingleStep(0.5)
        self.time_margin_spin.setDecimals(2)
        self.time_margin_spin.setValue(3.0)
        grid.addWidget(self.time_margin_spin, 1, 1)

        hint = QLabel("Estes valores substituem os padrões definidos no script original.")
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        grid.addWidget(hint, 2, 0, 1, 2)

    def get_constants(self) -> dict:
        return {
            "CHUNK_SIZE": self.chunk_size_spin.value(),
            "TIME_MARGIN": self.time_margin_spin.value(),
        }


# ═══════════════════════════════════════════════════════════════════════
# PAINEL: SELEÇÃO DE ARQUIVOS .LAS / .LAZ
# ═══════════════════════════════════════════════════════════════════════
class FilesPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Arquivos LAS / LAZ", parent)
        layout = QVBoxLayout(self)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setMinimumHeight(90)
        layout.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("➕ Adicionar arquivo(s)")
        self.btn_remove = QPushButton("➖ Remover selecionado(s)")
        self.btn_remove.setObjectName("dangerButton")
        self.btn_clear = QPushButton("🗑️ Limpar tudo")
        self.btn_clear.setObjectName("dangerButton")

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear)
        layout.addLayout(btn_row)

        self.btn_add.clicked.connect(self._add_files)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self.file_list.clear)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Selecionar arquivo(s) LAS/LAZ",
            "",
            "Nuvem de pontos (*.las *.laz);;Todos os arquivos (*)"
        )
        existing = self.get_files()
        for f in files:
            if f not in existing:
                self.file_list.addItem(QListWidgetItem(f))

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def get_files(self) -> list:
        return [self.file_list.item(i).text() for i in range(self.file_list.count())]


# ═══════════════════════════════════════════════════════════════════════
# PAINEL: PASTA DE TRAJETÓRIAS
# ═══════════════════════════════════════════════════════════════════════
class TrajectoryPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Pasta de Trajetórias", parent)
        layout = QHBoxLayout(self)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Nenhuma pasta selecionada...")

        self.btn_browse = QPushButton("📂 Escolher pasta")
        self.btn_browse.clicked.connect(self._browse)

        layout.addWidget(self.path_edit, 1)
        layout.addWidget(self.btn_browse)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta de trajetórias")
        if folder:
            self.path_edit.setText(folder)

    def get_path(self) -> str:
        return self.path_edit.text().strip()


# ═══════════════════════════════════════════════════════════════════════
# JANELA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Corte de Trajetória — Processamento de Nuvem de Pontos")
        self.resize(1180, 720)
        self.setMinimumSize(980, 600)

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self.header = HeaderBar()
        root.addWidget(self.header)

        # Corpo: splitter esquerda (configurações) / direita (console)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        root.addWidget(body)

        splitter = QSplitter(Qt.Horizontal)
        body_layout.addWidget(splitter)

        # ── Coluna esquerda: painéis de configuração ──
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.constants_panel = ConstantsPanel()
        self.files_panel = FilesPanel()
        self.trajectory_panel = TrajectoryPanel()

        left_layout.addWidget(self.constants_panel)
        left_layout.addWidget(self.files_panel, 1)
        left_layout.addWidget(self.trajectory_panel)

        action_row = QHBoxLayout()
        self.btn_process = QPushButton("🚀 PROCESSAR")
        self.btn_process.setObjectName("primaryButton")
        self.btn_process.setMinimumHeight(40)
        self.btn_process.clicked.connect(self._on_process_clicked)
        action_row.addWidget(self.btn_process)
        left_layout.addLayout(action_row)

        left_layout.addStretch(0)

        # ── Coluna direita: console ──
        right_col = QGroupBox("Console")
        right_layout = QVBoxLayout(right_col)
        self.console = ConsoleWidget()
        right_layout.addWidget(self.console)

        console_btn_row = QHBoxLayout()
        btn_clear_console = QPushButton("🧹 Limpar console")
        btn_test_console = QPushButton("🧪 Testar console")
        btn_clear_console.clicked.connect(self.console.clear)
        btn_test_console.clicked.connect(self._test_console)
        console_btn_row.addWidget(btn_clear_console)
        console_btn_row.addWidget(btn_test_console)
        console_btn_row.addStretch(1)
        right_layout.addLayout(console_btn_row)

        splitter.addWidget(left_col)
        splitter.addWidget(right_col)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 760])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Aguardando configuração...")

        self._setup_stdout_redirect()

    # ─────────────────────────────────────────────────────────────
    def _setup_stdout_redirect(self):
        """
        Redireciona sys.stdout e sys.stderr para o console da interface.
        A partir daqui, QUALQUER classe da aplicação (LasManager,
        TrajectoryManager, etc.) que usar print(...) terá sua saída
        exibida automaticamente aqui, sem precisar conhecer este widget.
        """
        self._stdout_redirector = StreamRedirector()
        self._stderr_redirector = StreamRedirector()
        self._stdout_redirector.text_written.connect(self.console.write_stream)
        self._stderr_redirector.text_written.connect(self.console.write_stream)

        sys.stdout = self._stdout_redirector
        sys.stderr = self._stderr_redirector

        print(f"[{self._timestamp()}] ✅ Console inicializado. Pronto para uso por outras classes.")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _test_console(self):
        print(f"[{self._timestamp()}] 🧪 Mensagem de teste do console.")
        print(f"[{self._timestamp()}] ⚙️  Constantes atuais: {self.constants_panel.get_constants()}")
        print(f"[{self._timestamp()}] 📂 Arquivos selecionados: {len(self.files_panel.get_files())}")
        print(f"[{self._timestamp()}] 🧭 Pasta de trajetórias: {self.trajectory_panel.get_path() or '(nenhuma)'}")

    def _on_process_clicked(self):
        files = self.files_panel.get_files()
        traj_dir = self.trajectory_panel.get_path()
        constants = self.constants_panel.get_constants()

        if not files:
            print(f"[{self._timestamp()}] ❌ Nenhum arquivo LAS/LAZ selecionado.")
            self.header.set_status("ERRO", Colors.ERROR)
            return
        if not traj_dir or not os.path.isdir(traj_dir):
            print(f"[{self._timestamp()}] ❌ Pasta de trajetórias inválida ou não selecionada.")
            self.header.set_status("ERRO", Colors.ERROR)
            return

        self.header.set_status("PROCESSANDO", Colors.WARNING)
        self.status_bar.showMessage("Processando...")

        print(f"[{self._timestamp()}] ╔══════════════════════════════════════════╗")
        print(f"[{self._timestamp()}] ║  INICIANDO PROCESSAMENTO                  ║")
        print(f"[{self._timestamp()}] ╚══════════════════════════════════════════╝")
        print(f"[{self._timestamp()}] ⚙️  CHUNK_SIZE: {constants['CHUNK_SIZE']:,}")
        print(f"[{self._timestamp()}] ⚙️  TIME_MARGIN: {constants['TIME_MARGIN']}s")
        print(f"[{self._timestamp()}] 🧭 Pasta de trajetórias: {traj_dir}")
        for i, f in enumerate(files, 1):
            print(f"[{self._timestamp()}]    {i:2d}. {os.path.basename(f)}")

        # TODO: aqui entrará a integração real com
        # core.las_manager.LasManager e core.trajectory_manager.TrajectoryManager,
        # reaproveitando este mesmo console (via print) para o log de progresso.
        print(f"[{self._timestamp()}] ⚠️  Lógica de processamento ainda não conectada "
              f"(placeholder). Próxima etapa: integrar LasManager/TrajectoryManager.")

        self.header.set_status("CONCLUÍDO", Colors.SUCCESS)
        self.status_bar.showMessage("Pronto.")

    def closeEvent(self, event):
        # Restaura stdout/stderr originais ao fechar
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(Styles.get_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
