#!/usr/bin/env python3
"""
main.py
─────────────────────────────────────────────────────────────────────────────
Aplicação PySide6 — "CORTE DE TRAJETÓRIA"
Tema visual: Dark Premium (Preto & Dourado), inspirado em painéis de
controle de drones.

Responsabilidades desta versão:
  • Selecionar um ou mais arquivos .las/.laz
  • Selecionar a pasta de trajetórias
  • Editar as constantes de processamento (CHUNK_SIZE, TIME_MARGIN)
  • Processar em uma QThread separada (usando LasManager/TrajectoryManager)
  • Exibir um console de saída (captura os prints do sistema), reutilizável
    pelas demais classes.
"""

import sys
import os
import math
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QRectF, QThread
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, QIcon, QPixmap,
    QTextCursor
)
import traceback

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QPlainTextEdit, QSpinBox, QDoubleSpinBox, QFileDialog, QFrame, QSplitter,
    QStatusBar, QSizePolicy, QAbstractItemView, QProgressBar
)

from core.styles import Styles, Colors
from core.las_manager import LasManager
from core.trajectory_manager import TrajectoryManager


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
            payload = str(text)
            if not payload.endswith("\n"):
                payload += "\n"
            self.text_written.emit(payload)

    def flush(self):
        pass


class ConsoleBridge(QObject):
    """Canal seguro para encaminhar mensagens de log da thread de trabalho para a UI."""
    message_written = Signal(str)

    def write(self, text: str):
        if text:
            payload = str(text)
            if not payload.endswith("\n"):
                payload += "\n"
            self.message_written.emit(payload)

    def flush(self):
        pass


class ConsoleWidget(QPlainTextEdit):
    """
    Console de saída reutilizável (estilo terminal/HUD).

    Correções importantes desta versão:
      • Usa `appendPlainText`, que SEMPRE escreve no final do documento —
        não importa onde o usuário clicou/posicionou o cursor. Isso resolve
        o bug de "clicar no console muda o local onde o texto é inserido".
      • Faz *buffer* do texto recebido e só materializa uma linha quando um
        "\\n" completo chega. Isso resolve a quebra de linha incorreta,
        já que `print()` dispara `write()` uma vez para o conteúdo e outra
        só para o "\\n" final — se cada `write()` virasse um parágrafo novo
        teríamos linhas quebradas/duplicadas no meio do texto.
    """

    MAX_BLOCKS = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("consoleWidget")
        self.setReadOnly(True)
        self.setMaximumBlockCount(self.MAX_BLOCKS)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._pending = ""

    def append_line(self, text: str):
        """Recebe um pedaço (chunk) de texto vindo do stdout/print e só
        materializa linhas completas no documento, mantendo o restante em
        buffer até que o próximo '\\n' chegue."""
        self._pending += text
        if "\n" not in self._pending:
            return
        *complete_lines, self._pending = self._pending.split("\n")
        for line in complete_lines:
            self.appendPlainText(line)
        self._move_cursor_to_end()

    def flush_pending(self):
        """Força a exibição de um texto parcial que ainda não recebeu \\n."""
        if self._pending:
            self.appendPlainText(self._pending)
            self._pending = ""
            self._move_cursor_to_end()

    def _move_cursor_to_end(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def write_stream(self, text: str):
        """Slot conectado ao StreamRedirector/ConsoleBridge."""
        self.append_line(text)

    def clear(self):
        super().clear()
        self._pending = ""

    def copy_all_to_clipboard(self):
        """Copia todo o conteúdo atual do console para a área de transferência."""
        self.flush_pending()
        QApplication.clipboard().setText(self.toPlainText())


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


class ProcessingWorker(QObject):
    started = Signal()
    finished = Signal(bool, str)
    # IMPORTANTE: "processed" e "total" usam `object` (não `int`) porque um
    # sinal Qt tipado como `int` é um C++ int de 32 bits (máx. ~2,1 bilhões).
    # Nuvens de pontos LAS/LAZ grandes podem facilmente ultrapassar esse
    # limite, o que disparava "OverflowError" ao emitir o sinal. Com
    # `object`, o valor Python (int de precisão arbitrária) trafega sem
    # conversão para C++, então não há mais estouro.
    progress = Signal(str, object, object, float)
    file_completed = Signal(str, bool)

    def __init__(self, files, traj_dir, chunk_size, time_margin, log_callback=None):
        super().__init__()
        self.files = files
        self.traj_dir = traj_dir
        self.chunk_size = chunk_size
        self.time_margin = time_margin
        self.log_callback = log_callback
        self._stop_requested = False
        self._overall_total = 0
        self._overall_processed = 0
        self._current_file_processed = 0

    def request_stop(self):
        self._stop_requested = True

    def _print(self, message: str):
        if self.log_callback is not None:
            self.log_callback(str(message) + "\n")
        else:
            print(message)

    def _print_progress(self, file_path: str, processed: int, total: int, elapsed: float):
        delta = max(0, int(processed) - self._current_file_processed)
        self._current_file_processed = int(processed)
        self._overall_processed += delta
        self.progress.emit(file_path, int(self._overall_processed), int(self._overall_total), float(elapsed))

    def run(self):
        self.started.emit()
        try:
            self._overall_total = 0
            self._overall_processed = 0
            self._current_file_processed = 0
            for file_path in self.files:
                worker_manager = LasManager(file_path, chunk_size=self.chunk_size)
                try:
                    self._overall_total += int(worker_manager.total_points)
                finally:
                    worker_manager.close()

            trajectory_manager = TrajectoryManager(
                self.traj_dir,
                time_margin=self.time_margin,
                log_callback=self.log_callback,
            )
            trajectory_manager.load_all_trajectories()
            if not trajectory_manager.trajectories:
                raise RuntimeError("Nenhuma trajetória válida foi carregada.")

            for file_path in self.files:
                if self._stop_requested:
                    self._print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏹️ Processamento interrompido pelo usuário.")
                    self.finished.emit(False, "Interrompido")
                    return

                self._print(f"[{datetime.now().strftime('%H:%M:%S')}] 📂 Iniciando arquivo: {os.path.basename(file_path)}")
                self._current_file_processed = 0
                worker_manager = LasManager(
                    file_path,
                    chunk_size=self.chunk_size,
                    log_callback=self.log_callback,
                )
                try:
                    self._print(f"[{datetime.now().strftime('%H:%M:%S')}]   Total de pontos: {worker_manager.total_points:,}")
                    stats, trajectory_paths, orphan_path, elapsed = worker_manager.process_with_statistics(
                        trajectory_manager,
                        output_prefix=os.path.splitext(os.path.basename(file_path))[0],
                        output_dir=os.path.dirname(file_path),
                        progress_callback=lambda processed, total, elapsed: self._print_progress(file_path, processed, total, elapsed)
                    )
                    self._print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Concluído: {os.path.basename(file_path)}")
                    self._print(f"[{datetime.now().strftime('%H:%M:%S')}]   Duração: {elapsed:.1f}s")
                    for idx, (path, count) in enumerate(zip(trajectory_paths, worker_manager.get_trajectory_counts()), start=1):
                        self._print(f"[{datetime.now().strftime('%H:%M:%S')}]   Trajetória #{idx}: {os.path.basename(path)} -> {count:,} pontos")
                    self._print(f"[{datetime.now().strftime('%H:%M:%S')}]   Órfãos: {os.path.basename(orphan_path)} -> {worker_manager.get_orphan_count():,} pontos")
                    self.file_completed.emit(file_path, True)
                except Exception as exc:
                    self._print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Erro ao processar {os.path.basename(file_path)}: {exc}")
                    self._print(traceback.format_exc())
                    self.file_completed.emit(file_path, False)
                finally:
                    worker_manager.finalize_writers()
                    worker_manager.close()

            self.finished.emit(True, "Concluído")
        except Exception as exc:
            self._print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Falha durante o processamento: {exc}")
            self._print(traceback.format_exc())
            self.finished.emit(False, str(exc))


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

        self._progress_last_update = 0
        self._worker_thread = None
        self._worker = None
        self._overall_total = 0
        self._overall_processed = 0
        self._progress_bar = None

        # Corpo: splitter esquerda (configurações) / direita (console)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 16)
        root.addWidget(body)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        self._progress_bar.setFormat("Progresso: %p%")
        body_layout.addWidget(self._progress_bar)

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
        btn_copy_console = QPushButton("📋 Copiar console")
        btn_test_console = QPushButton("🧪 Testar console")
        btn_clear_console.clicked.connect(self.console.clear)
        btn_copy_console.clicked.connect(self._copy_console)
        btn_test_console.clicked.connect(self._test_console)
        console_btn_row.addWidget(btn_clear_console)
        console_btn_row.addWidget(btn_copy_console)
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
        self._console_bridge = ConsoleBridge()
        self._stdout_redirector = StreamRedirector()
        self._stderr_redirector = StreamRedirector()
        # Qt.QueuedConnection garante que, mesmo vindo de outra thread
        # (ProcessingWorker), a atualização do widget só acontece na
        # thread principal da UI.
        self._console_bridge.message_written.connect(self.console.write_stream, Qt.QueuedConnection)
        self._stdout_redirector.text_written.connect(self._console_bridge.write)
        self._stderr_redirector.text_written.connect(self._console_bridge.write)

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

    def _copy_console(self):
        self.console.copy_all_to_clipboard()
        self.status_bar.showMessage("Conteúdo do console copiado para a área de transferência.", 3000)

    def _on_worker_started(self):
        self.btn_process.setEnabled(False)
        self.header.set_status("PROCESSANDO", Colors.WARNING)
        self.status_bar.showMessage("Processando...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Iniciando...")

    def _format_time_hms(self, seconds: float) -> str:
        total_seconds = int(round(max(0.0, seconds)))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _on_worker_progress(self, file_path: str, processed: int, total: int, elapsed: float):
        if total <= 0:
            return
        percent = min(100.0, max(0.0, (processed * 100.0) / total))
        elapsed_text = self._format_time_hms(elapsed)

        remaining_text = "--:--:--"
        eta_text = "--:--:--"
        if processed > 0 and processed < total:
            remaining = elapsed * (total - processed) / processed
            remaining_text = self._format_time_hms(remaining)
            eta_dt = datetime.now() + timedelta(seconds=remaining)
            eta_text = eta_dt.strftime("%H:%M:%S")
        elif processed >= total:
            remaining_text = "00:00:00"
            eta_text = datetime.now().strftime("%H:%M:%S")

        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(int(percent))
        self._progress_bar.setFormat(
            f"Tempo decorrido: {elapsed_text}  Restante: {remaining_text}  ETA {eta_text}"
        )
        self.status_bar.showMessage(f"Processando {os.path.basename(file_path)}...", 1000)
        if processed == total or processed - self._progress_last_update >= max(1_000_000, total // 20):
            self._progress_last_update = processed
            print(
                f"[{self._timestamp()}] ⏳ Processado {processed:,}/{total:,} pontos de "
                f"{os.path.basename(file_path)} (tempo decorrido={elapsed_text}, restante={remaining_text}, ETA={eta_text})"
            )

    def _on_worker_file_completed(self, file_path: str, success: bool):
        if not success:
            self.header.set_status("ERRO", Colors.ERROR)

    def _on_worker_finished(self, success: bool, message: str):
        self.btn_process.setEnabled(True)
        if success:
            self.header.set_status("CONCLUÍDO", Colors.SUCCESS)
            self.status_bar.showMessage("Pronto.")
            self._progress_bar.setValue(100)
            self._progress_bar.setFormat("Concluído")
            print(f"[{self._timestamp()}] ✅ TODO processamento concluído.")
        else:
            self.header.set_status("ERRO", Colors.ERROR)
            self.status_bar.showMessage("Erro.")
            self._progress_bar.setValue(0)
            self._progress_bar.setFormat("Falha")
            print(f"[{self._timestamp()}] ❌ Processamento finalizado com falha: {message}")

        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
            self._worker = None

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

        if self._worker_thread is not None:
            print(f"[{self._timestamp()}] ⚠️  Processamento já em andamento.")
            return

        self._progress_last_update = 0

        print(f"[{self._timestamp()}] ╔══════════════════════════════════════════╗")
        print(f"[{self._timestamp()}] ║  INICIANDO PROCESSAMENTO                  ║")
        print(f"[{self._timestamp()}] ╚══════════════════════════════════════════╝")
        print(f"[{self._timestamp()}] ⚙️  CHUNK_SIZE: {constants['CHUNK_SIZE']:,}")
        print(f"[{self._timestamp()}] ⚙️  TIME_MARGIN: {constants['TIME_MARGIN']}s")
        print(f"[{self._timestamp()}] 🧭 Pasta de trajetórias: {traj_dir}")
        for i, f in enumerate(files, 1):
            print(f"[{self._timestamp()}]    {i:2d}. {os.path.basename(f)}")

        self._worker = ProcessingWorker(
            files=files,
            traj_dir=traj_dir,
            chunk_size=constants['CHUNK_SIZE'],
            time_margin=constants['TIME_MARGIN'],
            log_callback=self._console_bridge.write,
        )
        self._worker_thread = QThread(self)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.started.connect(self._on_worker_started)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.file_completed.connect(self._on_worker_file_completed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.start()

    def closeEvent(self, event):
        # Request stop if background processing is active
        if self._worker is not None:
            self._worker.request_stop()
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()

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
