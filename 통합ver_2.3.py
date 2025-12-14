# ============================================================
# Quantum Circuit Composer — DRAG & DROP FIXED FINAL VERSION
# + TutorialTab merged from tutorial_first.py
# ============================================================

from __future__ import annotations
import sys
import math
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List, Callable

from PyQt6.QtWidgets import (
    QApplication,QProgressBar, QWidget, QHBoxLayout, QVBoxLayout,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem,
    QGraphicsTextItem, QLabel, QPushButton, QMessageBox,
    QTabWidget, QDialog, QTextEdit, QInputDialog, QGraphicsDropShadowEffect,
    QSplitter, QScrollArea, QSizePolicy,QListWidget,QStackedWidget, QRadioButton, QGroupBox, QGridLayout, QCheckBox      # tutorial용 import
)
from PyQt6.QtGui import QColor, QPen, QPainter, QFont, QBrush, QLinearGradient, QCursor, QDrag
from PyQt6.QtCore import Qt, QRectF, QPointF, QMimeData

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from qiskit.visualization import plot_bloch_multivector
from qiskit.quantum_info import Statevector, partial_trace, Operator
import numpy as np

# ============================================================
# CONFIG
# ============================================================
N_QUBITS = 3
MAX_QUBITS = 8

CELL_WIDTH = 55
ROW_HEIGHT = 85
X_OFFSET = 80
Y_OFFSET = 90
MAX_COLS = 17



# ============================================================
# DATA CLASS
# ============================================================
@dataclass
class GateInfo:
    gate_type: str
    row: int
    col: int
    angle: Optional[float] = None

# ------------------------------------------------------------
# TutorialStep Model
# ------------------------------------------------------------
@dataclass
class TutorialStep:
    title: str
    instruction: str
    expected: Callable[[list], bool]
    hint: str
    auto_setup: Callable[[object], None] | None = None

# ------------------------------------------------------------
# Tutorial Definition (Meta Level)
# ------------------------------------------------------------
@dataclass
class Tutorial:
    name: str
    theory_key: str
    steps: List["TutorialStep"]


# ============================================
# [신규 추가] Bloch Sphere Visualization Canvas
# (얽힘 상태일 때 강제로 화살표를 보여주는 로직이 포함됨)
# ============================================
class BlochCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(10, 10, 10, 10)
        
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_box.addWidget(self.title_label)

        self.status_label = QLabel()
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_box.addWidget(self.status_label)
        
        self.current_canvas = None
        # 화면 잘림 방지를 위한 최소 높이 설정
        self.setMinimumHeight(550) 
        self.hide() 

    def update_bloch(self, density_matrix, qubit_index):
        if self.current_canvas is not None:
            self.layout_box.removeWidget(self.current_canvas)
            self.current_canvas.setParent(None)
            self.current_canvas = None

        # --- [핵심] 얽힘 상태 강제 보정 로직 ---
        # 1. 현재 상태의 벡터 길이 계산
        X = Operator.from_label('X')
        Y = Operator.from_label('Y')
        Z = Operator.from_label('Z')
        
        vx = np.real(density_matrix.expectation_value(X))
        vy = np.real(density_matrix.expectation_value(Y))
        vz = np.real(density_matrix.expectation_value(Z))
        
        vector_length = np.sqrt(vx**2 + vy**2 + vz**2)
        
        final_rho = density_matrix
        is_forced = False
        
        # 2. 벡터 길이가 1보다 작으면(얽힘 상태) 강제로 늘림
        if vector_length < 0.99:
            is_forced = True
            if vector_length < 0.01:
                # 길이가 0인 경우 (예: 벨 상태) -> X축 방향 (|+>) 으로 강제 설정
                nx, ny, nz = 1.0, 0.0, 0.0
            else:
                # 방향은 유지하되 길이만 1로 정규화
                nx, ny, nz = vx / vector_length, vy / vector_length, vz / vector_length
            
            # 정규화된 벡터로 밀도 행렬 재구성
            I = Operator.from_label('I')
            final_rho = 0.5 * (I + nx * X + ny * Y + nz * Z)
        # --------------------------------

        # 3. 그래프 그리기
        new_fig = plot_bloch_multivector(final_rho) 
        new_fig.set_size_inches(5, 5)
        new_fig.tight_layout(pad=3.0)
        plt.close(new_fig)

        self.current_canvas = FigureCanvasQTAgg(new_fig)
        self.current_canvas.setMinimumSize(450, 450)
        self.current_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.title_label.setText(f"Bloch Sphere: Qubit {qubit_index}")
        
        if is_forced:
            self.status_label.setText("★ Forced Pure State (강제 보정됨)\n얽힘 상태를 순수 상태로 변환하여 표시 중")
            self.status_label.setStyleSheet("color: blue; font-weight: bold;")
        else:
            self.status_label.setText("Pure State (Length = 1.0)")
            self.status_label.setStyleSheet("color: green;")

        self.layout_box.addWidget(self.current_canvas)
        self.show()


# ============================================
# [신규 추가] 와이어 끝에 달릴 버튼 아이템
# ============================================
class BlochButtonItem(QGraphicsRectItem):
    WIDTH = 45
    HEIGHT = 25
    def __init__(self, qubit_index, callback, x, y):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)
        self.qubit_index = qubit_index
        self.callback = callback
        self.setPos(x, y)
        self.setBrush(QBrush(QColor("#FF9933"))) 
        self.setPen(QPen(Qt.GlobalColor.black))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptHoverEvents(True)

        self.text = QGraphicsTextItem("Bloch", self)
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        self.text.setFont(font)
        r = self.rect()
        b = self.text.boundingRect()
        self.text.setPos((r.width() - b.width()) / 2, (r.height() - b.height()) / 2)

    def mousePressEvent(self, event):
        if self.callback: self.callback(self.qubit_index)



# ============================================================
# GATE ITEM
# ============================================================
class GateItem(QGraphicsRectItem):
    WIDTH = 46
    HEIGHT = 34
    RADIUS = 8
    
    def __init__(self, label, gate_type, view=None, palette_mode=False):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)

        self.label = label
        self.gate_type = gate_type
        self.palette_mode = palette_mode
        self.view = view

        self.row = None
        self.col = None
        self.angle: Optional[float] = None
        self.drag_started = False
        self.clone = None

        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
        if not palette_mode:
            self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)

        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.text = QGraphicsTextItem(self)
        self.text.setFont(font)
        self.text.setDefaultTextColor(Qt.GlobalColor.black)
        # 수동으로 paint()에서 텍스트를 그리므로, 자식 텍스트는 숨김 처리하여 겹침 방지
        self.text.setVisible(False)
        self.text.setPos(0, 0)  # ★ 위치 초기화

        self.hovering = False
        self.update_text()
        self._center()
        self.shadow = None
        

    def format_pi_fraction(self, angle):
        if angle is None:
            return ""
        coef = angle / math.pi
        best_num, best_den, best_err = None, None, 999
        for den in range(1, 9):
            num = round(coef * den)
            err = abs(num / den - coef)
            if err < best_err:
                best_err, best_num, best_den = err, num, den
        if best_err < 1e-3:
            if best_num == 0:
                return "0"
            if best_den == 1:
                return "π" if best_num == 1 else f"{best_num}π"
            return f"{'' if best_num == 1 else best_num}π/{best_den}"
        return f"{coef:.2f}π"

    def update_text(self):
        if self.gate_type not in ("RX","RY","RZ"):
            self.text.setPlainText(self.label)
        else:
            if self.angle is None:
                self.text.setPlainText(self.label)
            else:
                frac = self.format_pi_fraction(self.angle)
                self.text.setPlainText(f"{self.label}\n{frac}")
        self._center()

    def _center(self):
        r = self.rect()
        t = self.text.boundingRect()
        self.text.setPos((r.width() - t.width())/2,
                         (r.height() - t.height())/2)

    def open_angle_dialog(self):
        cur = (self.angle / math.pi) if self.angle is not None else 0.5
        val, ok = QInputDialog.getDouble(
            None, f"Set angle for {self.label}",
            "Enter 0 < x < 2 (xπ rad):",
            cur, 0.0001, 1.9999, 4
        )
        if ok:
            self.angle = val * math.pi
            self.update_text()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            if not self.palette_mode and self.gate_type in ("RX","RY","RZ"):
                self.open_angle_dialog()
            return
        e.accept()
        if self.palette_mode:
            self.drag_started = False
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        # 더블클릭으로도 각도 편집 가능 (회로에 놓인 RX/RY/RZ만)
        if not self.palette_mode and self.gate_type in ("RX","RY","RZ"):
            self.open_angle_dialog()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def mouseMoveEvent(self, e):
        if self.palette_mode:
            if not self.drag_started:
                self.drag_started = True
                self.clone = GateItem(self.label, self.gate_type,
                                      self.view, palette_mode=False)
                self.clone.angle = self.angle
                if self.view:
                    self.view.scene.addItem(self.clone)
                    self.clone.setZValue(1000)

            if self.clone:
                global_pos = QCursor.pos()
                circuit_view_pos = self.view.mapFromGlobal(global_pos)
                circuit_scene_pos = self.view.mapToScene(circuit_view_pos)
                self.clone.setPos(
                    circuit_scene_pos.x() - self.clone.WIDTH/2,
                    circuit_scene_pos.y() - self.clone.HEIGHT/2
                )
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self.palette_mode:
            if self.clone:
                self.view.snap_gate(self.clone)
                self.clone = None
            self.drag_started = False
        else:
            super().mouseReleaseEvent(e)
            if self.view:
                self.view.snap_gate(self)
        e.accept()

    def hoverEnterEvent(self, e):
        self.hovering = True
        if self.shadow is None:
            self.shadow = QGraphicsDropShadowEffect()
            self.shadow.setOffset(0,0)
            self.shadow.setBlurRadius(18)
            self.shadow.setColor(QColor(60,60,60,130))
        self.setGraphicsEffect(self.shadow)

    def hoverLeaveEvent(self, e):
        self.hovering = False
        self.setGraphicsEffect(None)
        self.shadow = None

    def paint(self, p, opt, widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0,0,0,self.HEIGHT)
        grad.setColorAt(0, QColor("#C7ECFF") if self.hovering else QColor("#93D5F5"))
        grad.setColorAt(1, QColor("#9EDBFF") if self.hovering else QColor("#6FBDE5"))
        p.setBrush(QBrush(grad))
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        p.setPen(pen)
        p.drawRoundedRect(self.rect(), self.RADIUS, self.RADIUS)
        
        # ★ 텍스트 그리기
        if hasattr(self, 'text') and self.text is not None:
            font = self.text.font()
            # CTRL, X_T, Z_T 게이트는 폰트 크기를 크게
            if self.gate_type in ("CTRL", "X_T", "Z_T"):
                font.setPointSize(16)  # 기본 10pt에서 16pt로 확대
            p.setFont(font)
            p.setPen(QPen(Qt.GlobalColor.black))
            text_str = self.text.toPlainText()
            rect = self.rect()
            p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text_str)

class OracleGateItem(QGraphicsRectItem):
    
    WIDTH = 40
    
    def __init__(self, wire_spacing):
        super().__init__()

        self.gate_type = "ORACLE"
        self.locked = True

        
        height = wire_spacing * 2 + 60   # 세 행(q0~q2) 관통

        self.setRect(0, 0, self.WIDTH, height)

        self.setBrush(QColor("#E6F0FF"))
        self.setPen(QPen(Qt.GlobalColor.black, 2))

        label = QGraphicsTextItem("Uf", self)
        label.setPos(self.WIDTH/2 - 10, height/2 - 10)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

        self.setZValue(10)
    
    
    


class CircuitView(QGraphicsView):

    def __init__(self):
        super().__init__()

        # 기본 Scene
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # 고정 UI 설정
        self.WIRE_SHIFT = -30
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 패널 상태
        self.n_qubits = N_QUBITS
        self.circuit: Dict[Tuple[int, int], GateItem] = {}
        self.palette_gate: Optional[GateItem] = None
        self.connection_lines: List = []
        self.bloch_callback = None

        # Scene 크기 계산
        self._update_scene_rect()

        # 최초 그리기
        self.draw_all()

        self.reserved_columns: set = set()

    def get_oracle_column(self):
        return MAX_COLS // 2

    def has_oracle_gate(self):
        return any(
            getattr(item, "gate_type", None) == "ORACLE"
            for item in self.scene.items()
        )


    def insert_oracle_gate(self):
        if self.has_oracle_gate():
            return

        col = self.get_oracle_column()

        gate = OracleGateItem(wire_spacing=ROW_HEIGHT)

        x = X_OFFSET + col * CELL_WIDTH - gate.WIDTH / 2
        # 중앙을 q[1]에 두어 q0~q2를 모두 덮도록 배치
        y = (Y_OFFSET + ROW_HEIGHT) - gate.rect().height()/2

        gate.setPos(x, y)
        self.scene.addItem(gate)

        self.reserved_columns.add(col)

    # ----------------------------------------------------------
    # PUBLIC: Bloch Callback 설정
    # ----------------------------------------------------------
    def set_bloch_callback(self, func):
        self.bloch_callback = func
        self.draw_all()

    # ----------------------------------------------------------
    # Scene 크기 계산
    # ----------------------------------------------------------
    def get_right_end(self):
        return X_OFFSET + CELL_WIDTH * MAX_COLS

    def _compute_scene_height(self):
        return Y_OFFSET + (self.n_qubits + 1) * ROW_HEIGHT + 200

    def _update_scene_rect(self):
        right = self.get_right_end()
        height = self._compute_scene_height()
        self.setSceneRect(0, 0, right + 200, height)

        # 쓰레기통 위치
        self.trash_rect = QRectF(right - 90, 10, 70, 60)

        # View 최소 높이
        self.setMinimumHeight(int(height) + 40)

    # ----------------------------------------------------------
    # 전체 다시 그리기
    # ----------------------------------------------------------
    def draw_all(self):
        """전체 화면 다시 그리기"""
        if not self.isVisible():
            return
            
        self.setUpdatesEnabled(False)
        
        try:
            items_list = list(self.scene.items())

            # 1) 배경만 제거 (와이어, 라벨, 연결선, 쓰레기통) - 게이트와 게이트 자식은 건드리지 않음
            for it in items_list:
                if isinstance(it, (GateItem, OracleGateItem, QGraphicsTextItem)):
                    continue
                # 게이트의 자식도 건드리지 않음
                parent = it.parentItem() if hasattr(it, 'parentItem') else None
                if isinstance(parent, (GateItem, OracleGateItem)):
                    continue
                if it.scene() is self.scene:
                    try:
                        self.scene.removeItem(it)
                    except:
                        pass

            # 2) 연결선 제거
            for l in list(self.connection_lines):
                try:
                    if l.scene() is self.scene:
                        self.scene.removeItem(l)
                except:
                    pass
            self.connection_lines.clear()

            # 3) 배경 재구성
            self._draw_wires()
            self._draw_trash()

            # 4) 게이트 위치 수정 (이미 scene에 있는 게이트들)
            for (r, c), g in list(self.circuit.items()):
                # 범위 벗어난 게이트 제거
                if r < 0 or r >= self.n_qubits or c < 0 or c >= MAX_COLS:
                    try:
                        if g.scene() is self.scene:
                            self.scene.removeItem(g)
                    except:
                        pass
                    try:
                        del self.circuit[(r, c)]
                    except:
                        pass
                else:
                    # 유효한 범위 내 게이트 위치 업데이트
                    try:
                        if g.scene() is not self.scene:
                            self.scene.addItem(g)
                        x = X_OFFSET + c * CELL_WIDTH - g.WIDTH / 2
                        y = Y_OFFSET + r * ROW_HEIGHT - g.HEIGHT / 2
                        g.setPos(x, y)
                        # ★ 텍스트 업데이트 및 표시
                        if hasattr(g, 'text') and g.text is not None:
                            g.update_text()
                            g.text.show()
                    except:
                        pass

            # 5) 연결선 재구성
            self._draw_connections()
            
        finally:
            self.setUpdatesEnabled(True)

    def _compute_scene_height(self):
        return Y_OFFSET + (self.n_qubits + 1) * ROW_HEIGHT + 200

    def _update_scene_rect(self):
        right = self.get_right_end()
        height = self._compute_scene_height()
        self.setSceneRect(0, 0, right + 200, height)

        # 쓰레기통 위치
        self.trash_rect = QRectF(right - 90, 10, 70, 60)

        # View 최소 높이
        self.setMinimumHeight(int(height) + 40)

    # ----------------------------------------------------------
    # 전체 다시 그리기
    # ----------------------------------------------------------
    def draw_all(self):
        """전체 화면 다시 그리기"""
        self.setUpdatesEnabled(False)
        
        items = list(self.scene.items())

        # 1) 배경 제거 (와이어, 라벨, 연결선, 쓰레기통)
        for it in items:
            if isinstance(it, (GateItem, OracleGateItem)):
                continue
            if it.scene() is self.scene:
                self.scene.removeItem(it)

        # 2) circuit에 없는 GateItem 제거
        for it in items:
            if isinstance(it, GateItem):
                key = (it.row, it.col)
                if key not in self.circuit:
                    it.setGraphicsEffect(None)
                    it.shadow = None
                    if it.scene() is self.scene:
                        self.scene.removeItem(it)

        # 3) palette_gate 제거
        if self.palette_gate is not None:
            if self.palette_gate.scene() is self.scene:
                self.scene.removeItem(self.palette_gate)
            self.palette_gate = None

        # 4) 연결선 제거
        for l in list(self.connection_lines):
            if l.scene() is self.scene:
                self.scene.removeItem(l)
        self.connection_lines.clear()

        # 5) 배경 재구성
        self._draw_wires()
        self._draw_trash()

        # 6) 게이트 위치 업데이트 및 재추가
        for (r, c), g in list(self.circuit.items()):
            if r >= self.n_qubits:
                del self.circuit[(r, c)]
            else:
                if g not in self.scene.items():
                    self.scene.addItem(g)
                x = X_OFFSET + c * CELL_WIDTH - g.WIDTH / 2
                y = Y_OFFSET + r * ROW_HEIGHT - g.HEIGHT / 2
                g.setPos(x, y)

        # 7) 연결선 재구성
        self._draw_connections()
        
        self.setUpdatesEnabled(True)


    # ----------------------------------------------------------
    # 와이어 + 라벨 + Bloch 버튼
    # ----------------------------------------------------------
    def _draw_wires(self):
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        right = self.get_right_end()

        for i in range(self.n_qubits):
            y = Y_OFFSET + i * ROW_HEIGHT

            # 와이어
            self.scene.addLine(
                X_OFFSET + self.WIRE_SHIFT, y,
                right + self.WIRE_SHIFT, y, pen
            )

            # 라벨
            lbl = QGraphicsTextItem(f"q[{i}]")
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setDefaultTextColor(Qt.GlobalColor.black)
            lbl.setPos(X_OFFSET + self.WIRE_SHIFT - 40, y - 10)
            self.scene.addItem(lbl)

            # Bloch 버튼
            if self.bloch_callback:
                bx = right + self.WIRE_SHIFT + 10
                by = y - BlochButtonItem.HEIGHT / 2
                btn = BlochButtonItem(i, self.bloch_callback, bx, by)
                self.scene.addItem(btn)

        # classical bit line
        y2 = Y_OFFSET + self.n_qubits * ROW_HEIGHT
        self.scene.addLine(
            X_OFFSET + self.WIRE_SHIFT, y2,
            right + self.WIRE_SHIFT, y2, pen
        )
        txt = QGraphicsTextItem(f"c({self.n_qubits})")
        txt.setFont(QFont("Segoe UI", 12))
        txt.setDefaultTextColor(Qt.GlobalColor.black)
        txt.setPos(X_OFFSET + self.WIRE_SHIFT - 40, y2 - 10)
        self.scene.addItem(txt)

    # ----------------------------------------------------------
    def _draw_trash(self):
        pen = QPen(Qt.GlobalColor.black)
        brush = QBrush(QColor("#FFDDDD"))
        self.scene.addRect(self.trash_rect, pen, brush)

        t = QGraphicsTextItem("🗑")
        t.setFont(QFont("Segoe UI", 20))
        t.setDefaultTextColor(Qt.GlobalColor.black)
        t.setPos(self.trash_rect.x() + 18, self.trash_rect.y() + 8)
        self.scene.addItem(t)

    # ----------------------------------------------------------
    def _draw_connections(self):
        """CTRL ↔ TARGET 연결선 그리기"""
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)

        bycol: Dict[int, List[GateItem]] = {}
        for (r, c), g in self.circuit.items():
            bycol.setdefault(c, []).append(g)

        for col, ops in bycol.items():
            ctrl = [g.row for g in ops if g.gate_type == "CTRL"]
            tgt = [g for g in ops if g.gate_type in ("X_T", "Z_T")]

            if not ctrl and not tgt:
                continue

            rows = ctrl + [g.row for g in tgt]
            if len(rows) <= 1:
                continue

            top = min(rows)
            bot = max(rows)

            xmid = X_OFFSET + col * CELL_WIDTH
            ytop = Y_OFFSET + top * ROW_HEIGHT
            ybot = Y_OFFSET + bot * ROW_HEIGHT

            # 세로 연결선
            line = self.scene.addLine(xmid, ytop, xmid, ybot, pen)
            line.setZValue(-1)
            self.connection_lines.append(line)

            # 각 노드에 짧은 수평선
            for r in rows:
                cy = Y_OFFSET + r * ROW_HEIGHT
                h = self.scene.addLine(xmid - 6, cy, xmid + 6, cy, pen)
                h.setZValue(-1)
                self.connection_lines.append(h)

    # ----------------------------------------------------------
    # PALETTE → 드래그 상태 설정
    # ----------------------------------------------------------
    def set_palette_gate(self, gate_type, label):
        """팔레트가 GateItem을 드래그 시작할 때 호출"""
        if self.palette_gate:
            self.scene.removeItem(self.palette_gate)

        g = GateItem(label, gate_type, self)
        g.update_text()  # ★ 텍스트 초기화
        center = self.mapToScene(self.viewport().rect().center())
        g.setPos(center.x() - g.WIDTH / 2, Y_OFFSET - 40 - g.HEIGHT / 2)

        self.palette_gate = g
        self.scene.addItem(g)
        g.setZValue(1000)

    # ----------------------------------------------------------
    # SNAP LOGIC (핵심)
    # ----------------------------------------------------------
    def snap_gate(self, g: GateItem):
        
        if getattr(g, "gate_type", None) == "ORACLE":
            return

        """
        격자 스냅 / 삭제 / 스왑 / 다중 타겟 검사 포함
        """
        cx = g.pos().x() + g.WIDTH / 2
        cy = g.pos().y() + g.HEIGHT / 2

        # (1) 쓰레기통 → 삭제 [수정됨]
        trash_x = self.trash_rect.x()
        trash_y = self.trash_rect.y()
        trash_w = self.trash_rect.width()
        trash_h = self.trash_rect.height()
        
        if (trash_x <= cx <= trash_x + trash_w and 
            trash_y <= cy <= trash_y + trash_h):
            if g.row is not None:
                self.circuit.pop((g.row, g.col), None)
            self.scene.removeItem(g)
            if g is self.palette_gate:
                self.palette_gate = None
            self.draw_all()
            return

        # (2) 팔레트 영역 → 스냅 취소
        if cy < Y_OFFSET - 40:
            if g.row is not None:
                self.circuit.pop((g.row, g.col), None)
                g.row = g.col = None
            self.scene.removeItem(g)
            if g is self.palette_gate:
                self.palette_gate = None
            self.draw_all()
            return

        # (3) 그리드 위치 계산
        col = round((cx - X_OFFSET) / CELL_WIDTH)
        row = round((cy - Y_OFFSET) / ROW_HEIGHT)

        # ★ 먼저 이전 위치 저장
        old = (g.row, g.col) if g.row is not None else None

        # ★ classical bit 영역 확인 (n_qubits 이상이면 팔레트로 복구)
        if row < 0 or row >= self.n_qubits or col < 0 or col >= MAX_COLS:
            # 유효하지 않은 영역 - 이전 위치로 돌아가기
            if old is not None:
                # 이전에 circuit에 있었으면 그 위치로 복구
                self.circuit[old] = g
                g.row, g.col = old
                g.setPos(
                    X_OFFSET + old[1] * CELL_WIDTH - g.WIDTH / 2,
                    Y_OFFSET + old[0] * ROW_HEIGHT - g.HEIGHT / 2
                )
            else:
                # 새로운 게이트면 scene에서 제거
                if g.scene() is self.scene:
                    self.scene.removeItem(g)
                if g is self.palette_gate:
                    self.palette_gate = None
            return

        # 안전한 범위로 제한
        col = max(0, min(col, MAX_COLS - 1))
        row = max(0, min(row, self.n_qubits - 1))

        new = (row, col)

        # (4) 다중 타겟/측정 게이트 방지
        other_targets = [
            gg for (rr, cc), gg in self.circuit.items()
            if cc == col and gg.gate_type in ("X_T", "Z_T") and gg is not g
        ]
        # 같은 행(row)에 M 게이트가 이미 있으면 배치 거절
        other_measures = [
            gg for (rr, cc), gg in self.circuit.items()
            if rr == row and gg.gate_type == "MEASURE" and gg is not g
        ]
        
        if g.gate_type in ("X_T", "Z_T") and other_targets:
            if old is None:
                self.scene.removeItem(g)
                if g is self.palette_gate:
                    self.palette_gate = None
                self.draw_all()
                return
            else:
                g.setPos(
                    X_OFFSET + old[1] * CELL_WIDTH - g.WIDTH / 2,
                    Y_OFFSET + old[0] * ROW_HEIGHT - g.HEIGHT / 2
                )
                return

        # 같은 행에 M 게이트가 이미 있으면 배치 거절
        if g.gate_type == "MEASURE" and other_measures:
            if old is None:
                self.scene.removeItem(g)
                if g is self.palette_gate:
                    self.palette_gate = None
                self.draw_all()
                return
            else:
                g.setPos(
                    X_OFFSET + old[1] * CELL_WIDTH - g.WIDTH / 2,
                    Y_OFFSET + old[0] * ROW_HEIGHT - g.HEIGHT / 2
                )
                return

        # (5) 기존 위치 제거
        if old in self.circuit:
            del self.circuit[old]

        # (6) 새 위치에 Gate가 있으면 스왑
        existing = self.circuit.get(new)
        if existing is not None and existing is not g:
            if old is None:
                del self.circuit[new]
                self.scene.removeItem(existing)
            else:
                self.circuit[old] = existing
                existing.row, existing.col = old
                existing.setPos(
                    X_OFFSET + old[1] * CELL_WIDTH - existing.WIDTH / 2,
                    Y_OFFSET + old[0] * ROW_HEIGHT - existing.HEIGHT / 2
                )

        if not self._is_valid_column(col):
            if old is not None:
                self.circuit[old] = g
                g.row, g.col = old
                g.setPos(
                    X_OFFSET + old[1]* CELL_WIDTH - g.WIDTH / 2,
                    Y_OFFSET + old[0] * ROW_HEIGHT - g.HEIGHT / 2
                )
            else:
                self.scene.removeItem(g)
            if existing is not None:
                self.circuit[new] = existing
            return
        
        if col in self.reserved_columns:
            if hasattr(g, "row") and g.row is not None:
                g.setPos(
                    X_OFFSET + g.col * CELL_WIDTH - g.WIDTH / 2,
                    Y_OFFSET + g.row * ROW_HEIGHT - g.HEIGHT / 2
                )
            else:
                self.scene.removeItem(g)
            return
        

        # (7) 새 위치 등록
        self.circuit[new] = g
        g.row, g.col = row, col
        g.setPos(
            X_OFFSET + col * CELL_WIDTH - g.WIDTH / 2,
            Y_OFFSET + row * ROW_HEIGHT - g.HEIGHT / 2
        )

        # 텍스트 업데이트
        g.update_text()

        # 팔레트 게이트 초기화
        if g is self.palette_gate:
            self.palette_gate = None

        # (8) 전체 다시 그리기
        self.draw_all()

    def remove_oracle_gate(self):
        """Oracle 게이트 제거"""
        try:
            oracle_items = [
                item for item in self.scene.items()
                if getattr(item, "gate_type", None) == "ORACLE"
            ]
            for item in oracle_items:
                try:
                    if item.scene() is self.scene:
                        self.scene.removeItem(item)
                except:
                    pass
            self.reserved_columns.clear()
        except:
            pass

    def clear_circuit(self, *, remove_oracle: bool = True):
        """회로의 모든 게이트 제거 - 최소한의 작업"""
        try:
            # 1) 모든 업데이트 비활성화
            self.setUpdatesEnabled(False)
            self.scene.blockSignals(True)
            
            # 2) circuit 딕셔너리 초기화
            self.circuit.clear()
            
            # 3) palette_gate 초기화
            self.palette_gate = None
            
            # 4) 연결선 초기화
            self.connection_lines.clear()
            
            # 5) Scene의 모든 아이템 제거
            self.scene.clear()
            
        except Exception as e:
            print(f"clear_circuit error: {e}")
        finally:
            try:
                self.scene.blockSignals(False)
                self.setUpdatesEnabled(True)
            except:
                pass
        
        # 6) 배경 재구성
        try:
            self._draw_wires()
            self._draw_trash()
        except Exception as e:
            print(f"draw background error: {e}")


    # ----------------------------------------------------------
    # Delete 키 처리
    # ----------------------------------------------------------
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Delete:
            for it in list(self.scene.selectedItems()):
                if isinstance(it, GateItem):
                    if it.row is not None:
                        self.circuit.pop((it.row, it.col), None)
                    if it is self.palette_gate:
                        self.palette_gate = None
                    self.scene.removeItem(it)
            self.draw_all()
        else:
            super().keyPressEvent(e)

    # ----------------------------------------------------------
    # Gate Export for Qiskit
    # ----------------------------------------------------------
    def export_gate_infos(self) -> List[GateInfo]:
        out = []
        for (r, c), g in self.circuit.items():
            ang = (
                g.angle
                if g.gate_type in ("RX", "RY", "RZ") and g.angle is not None
                else 0
            )
            out.append(GateInfo(g.gate_type, r, c, ang))
        return sorted(out, key=lambda x: (x.col, x.row))

    # 한 열에 타겟 게이트 여러개인지 체크
    def _is_valid_column(self, col):
        targets = [
            g for (r, c), g in self.circuit.items()
            if c == col and g.gate_type in ("X_T", "Z_T")
        ]
        return len(targets) <= 1

# ============================================================
# PALETTE VIEW
# ============================================================
class PaletteView(QGraphicsView):
    def __init__(self, circuit_view):
        super().__init__()

        self.circuit_view = circuit_view
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.setFixedWidth(160)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self.init_palette()

    def init_palette(self):
        gates = [
            ("CTRL","●"), ("X_T","⊕"), ("Z_T","⊙"),
            ("H","H"), ("X","X"), ("Y","Y"), ("Z","Z"),
            ("RX","Rx"), ("RY","Ry"), ("RZ","Rz"),
            ("MEASURE","M"),
        ]

        x_pos = [20,80]
        col,row = 0,0
        spacing=70

        for gt,lb in gates:
            item = GateItem(lb, gt, view=self.circuit_view, palette_mode=True)
            item.setPos(x_pos[col], 20+row*spacing)
            self.scene.addItem(item)

            col += 1
            TutorialStep(
                title="오라클 뒤 입력 큐비트에 Hadamard 적용",
                instruction=(
                    "Oracle을 적용한 뒤 입력 큐비트 q[0]에 Hadamard 게이트를 배치하세요."
                ),
                expected=lambda infos: any(g.gate_type == "H" and g.row == 0 for g in infos),
                hint="입력 큐비트(q[0])에 H를 한 번 더 적용합니다."
            ),
            TutorialStep(
                title="입력 큐비트 측정 및 판별",
                instruction=(
                    "입력 큐비트 q[0]을 측정하고 결과를 oracle 유형과 비교하세요.\n"
                    "• constant → 측정 결과 q[0] = 0\n"
                    "• balanced → 측정 결과 q[0] = 1"
                ),
                expected=lambda infos: True,  # 체크 버튼에서 시뮬레이션으로 판별
                hint="Run Measurement로 측정 후 Check를 누르세요."
            ),
            if col>=2:
                col = 0
                row+=1



# ============================================================
# COMPOSER TAB (unchanged)
# ============================================================
class ComposerTab(QWidget):
    def __init__(self):
        super().__init__()
        
        # [통합] 메인 레이아웃을 VBox로 변경 (상단: 회로, 하단: Bloch 구)
        layout_root = QVBoxLayout(self)

        # 1. 상단 회로 영역 (Circuit + Palette + Side Controls)
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # [통합] PaletteView (첫 번째 정의의 드래그 앤 드롭 방식)
        self.view = CircuitView()
        self.palette = PaletteView(self.view)
        
        top_layout.addWidget(self.palette)
        top_layout.addWidget(self.view, stretch=1)

        # 사이드 컨트롤 패널
        side_panel = QVBoxLayout()
        top_layout.addLayout(side_panel)

        # 제어 버튼 추가
        btn_add = QPushButton("Add Qubit")
        btn_del = QPushButton("Delete Qubit")
        self.btn_export = QPushButton("Export Qiskit Code")
        self.btn_measure = QPushButton("Run Measurement")
        btn_clear = QPushButton("Clear Circuit")
        

        side_panel.addWidget(btn_add)
        side_panel.addWidget(btn_del)
        side_panel.addWidget(self.btn_export)
        side_panel.addWidget(self.btn_measure)
        side_panel.addWidget(btn_clear)
        side_panel.addStretch()
        
        # 상단 영역을 루트 레이아웃에 추가
        layout_root.addWidget(top_widget, stretch=3) # 회로 영역에 더 많은 공간 할당

        #Bloch 전용 창
        self.bloch_window = BlochWindow(self)

        #CircuitView에 Bloch 콜백 설정
        self.view.set_bloch_callback(self.update_single_bloch)

        # 시그널 연결
        btn_add.clicked.connect(self.add_q)
        btn_del.clicked.connect(self.del_q)
        btn_clear.clicked.connect(lambda: self.view.clear_circuit(remove_oracle=True))
        self.btn_export.clicked.connect(self.export_qiskit)
        self.btn_measure.clicked.connect(self.run_measurement)

    # -----------------------------------------------------
    # Qubit Management
    # -----------------------------------------------------

    def add_q(self):
        if self.view.n_qubits >= MAX_QUBITS:
            QMessageBox.warning(self,"Limit","Max 8 qubits")
            return
        self.view.n_qubits +=1
        # CircuitView의 메서드 이름 통일: _update_scene_rect, draw_all
        self.view._update_scene_rect()
        self.view.draw_all()

    def del_q(self):
        if self.view.n_qubits <=1:
            QMessageBox.warning(self,"Limit","At least 1 qubit")
            return
        
        remove_row = self.view.n_qubits-1
        # 게이트 제거 로직: 큐비트 삭제 시 해당 라인의 게이트도 제거
        for (row,col), g in list(self.view.circuit.items()):
            if row == remove_row:
                self.view.scene.removeItem(g)
                del self.view.circuit[(row,col)]

        self.view.n_qubits -=1
        self.view._update_scene_rect()
        self.view.draw_all()

    # -----------------------------------------------------
    # Bloch Sphere Visualization (추가된 핵심 기능)
    # -----------------------------------------------------
    
    def update_single_bloch(self, target_qubit_idx):
        """
        특정 큐비트의 상태를 계산하고 Bloch Canvas를 업데이트합니다.
        """
        try:
            # 1. 회로 빌드
            qc = self.build_qiskit_circuit()
            
            # 2. 상태 벡터 계산 (Statevector는 Qiskit에서 import 되어야 함)
            # 
            full_state = Statevector.from_instruction(qc)
            
            # 3. Partial Trace (관심 없는 큐빗 날리기)
            all_qubits = list(range(self.view.n_qubits))
            trace_out_qubits = [q for q in all_qubits if q != target_qubit_idx]
            
            # partial_trace는 Qiskit 또는 외부 유틸리티 함수여야 함
            rho = partial_trace(full_state, trace_out_qubits)
            
            # 4. 캔버스 업데이트
            self.bloch_window.update_bloch(rho, target_qubit_idx)

        except Exception as e:
            QMessageBox.warning(self, "Bloch Error", f"Calculation Failed: \n{e}")

    # -----------------------------------------------------
    # Qiskit Circuit Builder
    # -----------------------------------------------------

    def build_qiskit_circuit(self):
        """
        디자이너의 게이트 배치를 기반으로 Qiskit QuantumCircuit 객체를 생성합니다.
        """
        infos = self.view.export_gate_infos()
        # 고전 비트 레지스터도 큐비트 수와 동일하게 생성
        qc = QuantumCircuit(self.view.n_qubits, self.view.n_qubits) 

        # 열(Column)별로 게이트를 그룹화하여 순차적으로 적용
        bycol = {}
        for g in infos:
            bycol.setdefault(g.col,[]).append(g)

        for col in sorted(bycol):
            ops = bycol[col]
            
            # A. 단일 큐비트 게이트 및 측정 적용 (제어/타겟이 아닌 게이트)
            for g in ops:
                if g.gate_type=="H": qc.h(g.row)
                elif g.gate_type=="X": qc.x(g.row)
                elif g.gate_type=="Y": qc.y(g.row)
                elif g.gate_type=="Z": qc.z(g.row)
                # 회전 게이트: g.angle을 사용 (None인 경우 0으로 처리)
                elif g.gate_type=="RX": qc.rx(g.angle if g.angle is not None else 0, g.row)
                elif g.gate_type=="RY": qc.ry(g.angle if g.angle is not None else 0, g.row)
                elif g.gate_type=="RZ": qc.rz(g.angle if g.angle is not None else 0, g.row)
            
            # B. 다중 큐비트 게이트 (Control, Target)
            ctrls = [g.row for g in ops if g.gate_type=="CTRL"]
            xt = [g.row for g in ops if g.gate_type=="X_T"]
            zt = [g.row for g in ops if g.gate_type=="Z_T"]

            # CNOT / MCX
            if len(xt)==1:
                t = xt[0]
                if len(ctrls)==0: qc.x(t)      # T-gate가 단독이면 X 게이트
                elif len(ctrls)==1: qc.cx(ctrls[0], t) # CNOT
                else: qc.mcx(ctrls, t)         # Toffoli / MCX

            # CZ / MCZ
            if len(zt)==1:
                t = zt[0]
                if len(ctrls)==0: qc.z(t)      # T-gate가 단독이면 Z 게이트
                elif len(ctrls)==1: qc.cz(ctrls[0], t) # CZ
                else: qc.mcz(ctrls, t)         # MCZ
            
            # C. 측정 게이트
            for g in ops:
                if g.gate_type=="MEASURE":
                    qc.measure(g.row, g.row)

        return qc

    # -----------------------------------------------------
    # Export QISKIT CODE
    # -----------------------------------------------------
    
    def export_qiskit(self):
        try:
            infos = self.view.export_gate_infos()
        except Exception as e:
            QMessageBox.warning(self,"Export Error",f"Failed to get gate info: {e}")
            return

        code = []
        code.append("from qiskit import QuantumCircuit\n")
        code.append(f"qc = QuantumCircuit({self.view.n_qubits}, {self.view.n_qubits})\n\n")

        # 게이트 정보가 이미 정렬되어 있으므로, build_qiskit_circuit 로직을 코드 출력에 적용
        bycol = {}
        for g in infos:
            bycol.setdefault(g.col,[]).append(g)

        for col in sorted(bycol):
            ops = bycol[col]
            code.append(f"\n# Column {col}\n")
            
            # 단일 큐비트
            for g in ops:
                if g.gate_type=="H": code.append(f"qc.h({g.row})\n")
                elif g.gate_type=="X": code.append(f"qc.x({g.row})\n")
                elif g.gate_type=="Y": code.append(f"qc.y({g.row})\n")
                elif g.gate_type=="Z": code.append(f"qc.z({g.row})\n")
                elif g.gate_type=="RX": code.append(f"qc.rx({g.angle if g.angle is not None else 0}, {g.row})\n")
                elif g.gate_type=="RY": code.append(f"qc.ry({g.angle if g.angle is not None else 0}, {g.row})\n")
                elif g.gate_type=="RZ": code.append(f"qc.rz({g.angle if g.angle is not None else 0}, {g.row})\n")
                elif g.gate_type=="MEASURE": code.append(f"qc.measure({g.row}, {g.row})\n")
            
            # 다중 큐비트
            ctrls = [g.row for g in ops if g.gate_type=="CTRL"]
            xt = [g.row for g in ops if g.gate_type=="X_T"]
            zt = [g.row for g in ops if g.gate_type=="Z_T"]

            if len(xt)==1:
                t = xt[0]
                if len(ctrls)==0: code.append(f"qc.x({t}) # T-gate without controls\n")
                elif len(ctrls)==1: code.append(f"qc.cx({ctrls[0]}, {t})\n")
                else: code.append(f"qc.mcx({ctrls}, {t})\n")

            if len(zt)==1:
                t = zt[0]
                if len(ctrls)==0: code.append(f"qc.z({t}) # T-gate without controls\n")
                elif len(ctrls)==1: code.append(f"qc.cz({ctrls[0]}, {t})\n")
                else: code.append(f"qc.mcz({ctrls}, {t})\n")

        code_str = "".join(code)

        dlg = QDialog(self)
        dlg.setWindowTitle("Qiskit Code")
        lay = QVBoxLayout(dlg)
        box = QTextEdit()
        box.setReadOnly(True)
        box.setText(code_str)
        lay.addWidget(box)

        btn = QPushButton("Copy to Clipboard")
        lay.addWidget(btn)
        btn.clicked.connect(lambda: QApplication.clipboard().setText(code_str))
        dlg.resize(600,450)
        dlg.exec()

    # -----------------------------------------------------
    # Run Measurement
    # -----------------------------------------------------

    def run_measurement(self):
        """
        회로를 빌드하고 AerSimulator를 사용하여 측정을 실행합니다.
        """
        try:
            infos = self.view.export_gate_infos()
        except Exception as e:
            QMessageBox.warning(self,"Circuit Build Error",f"{e}")
            return

        # 실제로 측정할 큐비트 찾기
        measured_qubits = set()
        for g in infos:
            if g.gate_type == "MEASURE":
                measured_qubits.add(g.row)
        
        # 측정 게이트가 없으면 경고
        if not measured_qubits:
            QMessageBox.warning(self, "No Measurement Gate", "측정(M)게이트가 없습니다!")
            return
        
        n_measured = len(measured_qubits)
        
        try:
            qc = self.build_qiskit_circuit()
        except Exception as e:
            QMessageBox.warning(self,"Circuit Build Error",f"{e}")
            return

        try:
            # AerSimulator는 Qiskit Aer에서 import 되어야 함
            sim = AerSimulator()
            shots = 1024
            res = sim.run(qc, shots=shots).result()
            counts = res.get_counts()
        except Exception as e:
            QMessageBox.warning(self,"Simulator Error",f"{e}")
            return

        # 측정된 비트 개수가 전체보다 적으면 결과 필터링
        if n_measured < self.view.n_qubits:
            filtered_counts = {}
            for bitstring, count in counts.items():
                clean = bitstring.replace(" ", "")
                # 오른쪽 n_measured 비트만 추출
                truncated = clean[-n_measured:] if n_measured > 0 else ""
                filtered_counts[truncated] = filtered_counts.get(truncated, 0) + count
            counts = filtered_counts

        # 측정 결과를 보기 좋게 포맷팅
        result_lines = [
            "═" * 60,
            "📊 양자 측정 결과",
            "═" * 60,
            f"\n총 시행 횟수: {shots}번\n",
            "주의: 결과는 리틀엔디언(Little Endian) 형식으로 표시됩니다.",
            "      (오른쪽이 q[0], 왼쪽이 q[n-1]입니다)\n",
            "측정 결과:",
            "─" * 60
        ]
        
        # 결과를 확률 순서로 정렬
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        for bitstring, count in sorted_counts:
            # bitstring에서 공백 제거
            clean_bitstring = bitstring.replace(" ", "")
            percentage = (count / shots) * 100
            result_lines.append(f"|{clean_bitstring}⟩: {count:4d}회 ({percentage:6.2f}%)")
        
        result_lines.append("═" * 60)
        result_text = "\n".join(result_lines)

        QMessageBox.information(self, "Measurement Result", result_text)



# ============================================================
# TUTORIAL TAB  (Imported from tutorial_first.py)
# ============================================================

#Deutsch -Josza 용 함수
def is_balanced_truth_table(truth_table: dict[str, int]) -> bool:
    values = list(truth_table.values())
    return values.count(0) == 2 and values.count(1) == 2


class TutorialTab(QWidget):

    TUTORIAL_DATA = {
        "1. Qubit과 Hadamard Gate": 
            "## Qubit과 Hadamard Gate\n\n"
            "**1. Qubit (양자 비트):** 고전적인 비트(0 또는 1)와 달리, 큐비트는 $\\left|0\\right\\rangle$과 $\\left|1\\right\\rangle$ 상태의 **중첩(Superposition)** 상태를 가질 수 있습니다. 이는 동시에 여러 값을 나타낼 수 있음을 의미하며, 계산의 병렬성을 부여합니다.\n\n"
            "**2. Hadamard (H) Gate:** 이 게이트는 큐비트를 순수한 $\\left|0\\right\\rangle$ 또는 $\\left|1\\right\\rangle$ 상태에서 완벽한 중첩 상태로 만듭니다. 회로에 H 게이트를 추가하고 Run Measurement를 실행하여 결과를 확인해 보세요.",
        
        "2. CNOT과 Entanglement": 
            "## CNOT과 Entanglement (얽힘)\n\n"
            "**1. CNOT (Controlled-X):** 이 게이트는 두 큐비트에 작용합니다. 제어 큐비트(Control, '●')가 $\\left|1\\right\\rangle$일 때만 대상 큐비트(Target, '⊕')에 X(NOT) 연산을 적용합니다. 만약 제어 큐비트가 $\\left|0\\right\\rangle$이면 아무 일도 하지 않습니다.\n\n"
            "**2. Entanglement (얽힘):** Qubit 0에 H 게이트를 적용한 다음, Qubit 0을 제어 큐비트로, Qubit 1을 대상 큐비트로 하는 CNOT 게이트를 적용해 보세요. 이 상태에서 두 큐비트는 **얽힘 상태(Bell State)**가 됩니다. 이 상태에서는 한 큐비트를 측정하면 다른 큐비트의 상태가 즉시 결정됩니다.",
            
        "3. 양자 푸리에 변환 (QFT) 기초": 
            "## 양자 푸리에 변환 (QFT) 기초\n\n"
            "QFT는 Shor의 알고리즘과 같은 복잡한 양자 알고리즘의 핵심 구성 요소입니다. 이는 고전적인 이산 푸리에 변환(DFT)의 양자 버전이며, 중첩된 양자 상태에서 주파수 정보를 추출하는 데 사용됩니다.\n\n"
            "QFT는 주로 Hadamard 게이트와 조건부 위상 이동 게이트(Controlled Phase Shift Gate, Rz 게이트의 특정 형태)의 조합으로 구현됩니다. 3큐비트 QFT를 구성하여 그 효과를 실험해 보세요.",
    
          "4. 초고밀도 코딩 (Superdense Coding)": 
            "## 초고밀도 코딩 (Superdense Coding)\n\n"
            "**초고밀도 코딩(Superdense Coding)**은 하나의 큐비트 전송만으로 "
            "**2비트의 고전 정보**를 전달할 수 있음을 보여주는 양자 통신 프로토콜입니다.\n\n"
            "---\n"
            "### 🔹 개념 요약\n"
            "1. **사전 공유된 얽힘 (Bell State)**\n"
            "   Alice와 Bob은 미리 Bell 상태를 공유합니다.\n\n"
            "2. **Alice의 인코딩**\n"
            "   Alice는 자신의 큐비트에 다음 연산 중 하나를 적용합니다:\n\n"
            "   | 전송 비트 | 적용 게이트 |\n"
            "   |----------|-------------|\n"
            "   | 00 | I (아무 것도 안 함) |\n"
            "   | 01 | X |\n"
            "   | 10 | Z |\n"
            "   | 11 | X + Z |\n\n"
            "3. **큐비트 전송**\n"
            "   Alice는 자신의 큐비트를 Bob에게 보냅니다.\n\n"
            "4. **Bob의 디코딩**\n"
            "   Bob은 CNOT과 Hadamard 게이트를 사용하여 두 큐비트를 분리한 뒤 측정합니다.\n\n"
            "---\n"
            "### 🔬 실습 가이드\n"
            "- 먼저 Qubit 0과 Qubit 1에 Bell State를 만드세요 (H + CNOT)\n"
            "- Alice의 큐비트(Qubit 0)에 X 또는 Z 게이트를 적용해 보세요\n"
            "- Bob 디코딩 회로를 구성한 뒤 측정을 실행하고 결과를 확인하세요\n\n"
            "👉 하나의 큐비트 전송으로 2비트 정보가 전달되는 것을 직접 확인해 보세요!",

        "5. Deutsch Jozsa Algorithm":
        "## Deutsch Jozsa Algorithm\n\n"
        "숨겨진 함수 f(x)가 **constant** 인지 **balanced** 인지를\n"
        "단 한 번의 oracle 호출로 판별하는 양자 알고리즘입니다.\n\n"
        "이 튜토리얼에서는:\n"
        "• Hadamard를 이용한 양자 병렬성\n"
        "• Oracle을 블랙박스로 사용하는 이유\n"
        "• 측정 결과가 의미하는 바\n\n"
        "를 직접 회로를 구성하며 체험합니다."    

    }

    def __init__(self):
        super().__init__()

        root = QHBoxLayout(self)

        self.tutorials: List[Tutorial] = self.build_tutorials()
        self.current_tutorial: Tutorial | None = None
        self.current_step_index: int = 0

        self.tutorials_started = False  # ★ 추가: 스타트 버튼 누름 여부

        # ======================================================
        # LEFT : Tutorial List (1/4)
        # ======================================================
        self.list_widget = QListWidget()
        for t in self.tutorials:
            self.list_widget.addItem(t.name)
        self.list_widget.setMaximumWidth(260)
        root.addWidget(self.list_widget, stretch=1)

        # ======================================================
        # RIGHT : Content Area (3/4)
        # ======================================================
        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=3)

        # ---- Page 0 : Theory / Guide ----
        self.page_intro = QWidget()
        intro_layout = QVBoxLayout(self.page_intro)

        self.intro_title = QLabel("튜토리얼을 선택하세요")
        self.intro_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))

        self.intro_text = QTextEdit()
        self.intro_text.setReadOnly(True)
        self.intro_text.setText(
            "왼쪽에서 튜토리얼을 선택한 뒤,\n"
            "Next 버튼을 눌러 실습을 시작하세요.\n\n"
            "이 영역에서는 기본 이론, 회로 구조, 학습 목표가 제공됩니다."
        )

        self.btn_start = QPushButton("Start Tutorial")

        intro_layout.addWidget(self.intro_title)
        intro_layout.addWidget(self.intro_text, stretch=1)
        intro_layout.addWidget(self.btn_start, alignment=Qt.AlignmentFlag.AlignRight)

        self.stack.addWidget(self.page_intro)

        # ---- Page 1 : Interactive Step ----
        self.page_step = QWidget()
        step_layout = QVBoxLayout(self.page_step)
        # 레이아웃 여백 설정으로 중앙 정렬 및 짤림 방지
        step_layout.setContentsMargins(10, 10, 10, 10)
        step_layout.setSpacing(8)

        title_layout = QHBoxLayout()

        self.step_title = QLabel()
        self.step_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        # 제목 위치 개선: 좌측 정렬 + 세로 중앙, 좌우 여백 추가
        self.step_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(20)  # 높이 조절 가능

        # 소제목과 진행바를 같은 줄에 배치
        # 좌우 여백으로 모서리 붙는 느낌 완화
        title_layout.setContentsMargins(12, 0, 12, 0)
        title_layout.addWidget(self.step_title, stretch=2)
        title_layout.addWidget(self.progress, stretch=1)  # 필요시 stretch 조정

        step_layout.addLayout(title_layout)
        # 제목과 회로 사이 여백 추가
        step_layout.addSpacing(10)

        circuit_box = QHBoxLayout()
        self.view = CircuitView()
        self.palette = PaletteView(self.view)
        # 스크롤 없이도 모두 보이도록 고정 높이로 조정 (튜토리얼 전용)
        CIRCUIT_HEIGHT = 500

        self.view.setFixedHeight(CIRCUIT_HEIGHT)
        self.palette.setFixedHeight(CIRCUIT_HEIGHT)
        # 튜토리얼에서는 scene 크기도 고정하여 큐비트 수와 무관하게 일관된 높이 유지
        self.view.setSceneRect(0, 0, self.view.get_right_end() + 200, CIRCUIT_HEIGHT)

        from PyQt6.QtWidgets import QSizePolicy
        # 수직 확장을 막아 과도한 높이 점유 방지
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.palette.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 위쪽 정렬로 고정, stretch 제거로 가운데 정렬 방지
        circuit_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        circuit_box.addWidget(self.palette)
        circuit_box.addWidget(self.view)

        self.step_instruction = QTextEdit()
        self.step_instruction.setReadOnly(True)
        # 설명 영역 높이를 모든 튜토리얼에서 동일하게 고정
        self.step_instruction.setFixedHeight(130)

        # -----------------------------
        # Buttons
        # -----------------------------

        #오라클 생성 버튼
        self.btn_define_oracle = QPushButton("Define Oracle")
        self.btn_define_oracle.clicked.connect(self.open_oracle_dialog)
        self.btn_define_oracle.hide()


        self.btn_measure_tutorial = QPushButton("Run Measurement")
        self.btn_check = QPushButton("Check")
        self.btn_hint = QPushButton("Hint")
        self.btn_reset = QPushButton("Reset")
        self.btn_next = QPushButton("Next")
        self.btn_back_intro = QPushButton("Back to Intro")
        

        # --- Check / Hint / Reset (윗줄)
        upper_btns = QHBoxLayout()
        upper_btns.addWidget(self.btn_measure_tutorial)
        upper_btns.addWidget(self.btn_check)
        upper_btns.addWidget(self.btn_hint)
        upper_btns.addWidget(self.btn_reset)
        upper_btns.addWidget(self.btn_define_oracle)


        # --- Next (아랫줄, 오른쪽 정렬)
        lower_btns = QHBoxLayout()
        lower_btns.addWidget(self.btn_back_intro)
        lower_btns.addStretch()
        lower_btns.addWidget(self.btn_next)

        # --- 오른쪽 버튼 묶음 (세로)
        right_btns = QVBoxLayout()
        right_btns.addLayout(upper_btns)
        right_btns.addLayout(lower_btns)

        # --- 전체 하단 레이아웃
        footer = QHBoxLayout()
        footer.addStretch()      # 왼쪽 비우기
        footer.addLayout(right_btns)

        # --- 전체 페이지 레이아웃
        # 스크롤 제거: 제목/회로/설명을 모두 고정 배치 (위쪽 정렬)
        step_layout.addLayout(circuit_box, 0)
        step_layout.addWidget(self.step_instruction)
        step_layout.addLayout(footer)

        self.stack.addWidget(self.page_step)

        # ======================================================
        # Signals
        # ======================================================
        self.btn_start.clicked.connect(self.start_tutorial)
        self.btn_measure_tutorial.clicked.connect(self.run_measurement_tutorial)
        self.btn_check.clicked.connect(self.check_step)
        self.btn_hint.clicked.connect(self.show_hint)
        self.btn_next.clicked.connect(self.next_step)
        self.btn_back_intro.clicked.connect(self.go_to_intro)
        self.btn_reset.clicked.connect(self.reset_step)
        self.list_widget.currentRowChanged.connect(self.on_tutorial_selected)

        self.stack.setCurrentIndex(0)

        #Deutsch-Josza 용 오라클 함수 저장 변수
        self.oracle_truth_table: dict[str, int] | None = None
        self.oracle_type : str | None = None  # "constant" or "balanced"


        

        # When selecting tutorial, update description

    def on_tutorial_selected(self, row: int):
        if row < 0:
            return

        selected_tutorial = self.tutorials[row]

        if self.tutorials_started:
            # 진행 중인 튜토리얼이 있고 아직 완료되지 않은 경우
            if self.current_tutorial and self.current_step_index < len(self.current_tutorial.steps):
                ret = QMessageBox.warning(
                    self,
                    "진행 중인 튜토리얼 종료",
                    "진행 중인 튜토리얼을 종료하고 새로운 튜토리얼을 시작하시겠습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if ret == QMessageBox.StandardButton.No:
                    # 선택 복원
                    self.list_widget.blockSignals(True)
                    self.list_widget.setCurrentRow(self.tutorials.index(self.current_tutorial))
                    self.list_widget.blockSignals(False)
                    return

        # 선택된 튜토리얼 설정
        self.current_tutorial = selected_tutorial
        self.current_step_index = 0

        # 진행률 초기화
        self.progress.setValue(0)
            # NEXT 버튼 활성화
        self.btn_next.setEnabled(True)

        if not self.tutorials_started:
            # ★ 튜토리얼 시작 전: Intro 페이지 표시
            theory_key = self.current_tutorial.theory_key
            self.intro_title.setText(self.current_tutorial.name)
            self.intro_text.setText(self.TUTORIAL_DATA.get(theory_key, "이 튜토리얼에 대한 정보가 없습니다."))
            self.stack.setCurrentIndex(0)
        else:
            # ★ 튜토리얼 시작 후: Step 페이지 바로 로드
            self.start_tutorial()

    def open_oracle_dialog(self):
        dialog = QDialog(self.window())
        dialog.setWindowTitle("Define Oracle f(x)")
        layout = QVBoxLayout(dialog)

        # --- oracle type 선택 ---
        rb_constant = QRadioButton("Constant")
        rb_balanced = QRadioButton("Balanced")
        rb_constant.setChecked(True)

        layout.addWidget(rb_constant)
        layout.addWidget(rb_balanced)

        # --- constant 옵션 ---
        const_group = QGroupBox("Constant Output")
        const_layout = QVBoxLayout(const_group)
        rb_zero = QRadioButton("Always 0")
        rb_one = QRadioButton("Always 1")
        rb_zero.setChecked(True)
        const_layout.addWidget(rb_zero)
        const_layout.addWidget(rb_one)

        # --- balanced 옵션 ---
        bal_group = QGroupBox("Balanced Output (choose two 1s)")
        bal_layout = QGridLayout(bal_group)
        checkboxes = {}
        for i, key in enumerate(["00","01","10","11"]):
            cb = QCheckBox(f"{key} → 1")
            checkboxes[key] = cb
            bal_layout.addWidget(cb, i//2, i%2)

        layout.addWidget(const_group)
        layout.addWidget(bal_group)

        # --- OK 버튼 ---
        btn_ok = QPushButton("OK")
        layout.addWidget(btn_ok)

        def on_ok():
            if rb_constant.isChecked():
                self.oracle_type = "constant"
                value = 1 if rb_one.isChecked() else 0
                self.oracle_truth_table = {
                    k: value for k in ["00","01","10","11"]
                }
                self.view.insert_oracle_gate()
                dialog.accept()
                return

            # balanced
            truth = {
                k: 1 if cb.isChecked() else 0
                for k, cb in checkboxes.items()
            }
            if not is_balanced_truth_table(truth):
                QMessageBox.warning(
                    self,
                    "Invalid Balanced Function",
                    "balanced 조건을 만족하지 않습니다.\n"
                    "출력 중 2개는 0, 나머지 2개는 1 이어야 합니다."
                )
                return

            self.oracle_type = "balanced"
            self.oracle_truth_table = truth
            self.view.insert_oracle_gate()
            dialog.accept()


        def update_ui():
            const_group.setEnabled(rb_constant.isChecked())
            bal_group.setEnabled(rb_balanced.isChecked())

        rb_constant.toggled.connect(update_ui)
        rb_balanced.toggled.connect(update_ui)
        update_ui()


        btn_ok.clicked.connect(on_ok)
        result = dialog.exec()

        if result != QDialog.accepted:
            self.oracle_truth_table = None
            self.oracle_type = None




    # --------------------------------------------------------
    # Tutorial Construction
    # --------------------------------------------------------
    def build_tutorials(self) -> List[Tutorial]:
        # -----------------------------
        # Hadamard Gate Tutorial
        # -----------------------------
        hadamard_steps = [
            TutorialStep(
                title="기본 상태 |0⟩",
                instruction="아무 게이트도 배치하지 말고 측정해 보세요.",
                expected=lambda infos: len(infos) == 0,
                hint="이번 단계에서는 게이트를 두지 않습니다."
            ),

            TutorialStep(
                title="Hadamard로 중첩 만들기",
                instruction="q[0]에 Hadamard 게이트를 배치하세요.",
                expected=lambda infos: (
                    len(infos) == 1 and infos[0].gate_type == 'H'
                ),
                hint="H 게이트를 q[0]에 하나만 배치하세요."
            ),

            TutorialStep(
                title="Hadamard는 가역적이다",
                instruction="q[0]에 Hadamard 게이트를 두 번 배치하세요.",
                expected=lambda infos: (
                    len(infos) == 2 and
                    all(g.gate_type == 'H' for g in infos)
                ),
                hint="같은 큐비트에 H를 두 번 연속 배치하세요."
            )
    
        ]

        # -----------------------------
        # CNOT Tutorial
        # -----------------------------
        cnot_steps = [
                TutorialStep(
                    title="고전적 상관관계",
                    instruction="q[0]에 X 게이트를 적용한 뒤 CNOT을 구성하세요.",
                    expected=lambda infos: (
                        any(g.gate_type == 'X' for g in infos) and
                        any(g.gate_type == 'CTRL' for g in infos)
                    ),
                    hint="X(q0) → CNOT(q0→q1) 순서입니다."
                ),

                TutorialStep(
                    title="Bell State 만들기",
                    instruction="Hadamard와 CNOT으로 Bell 상태를 만드세요.",
                    expected=lambda infos: (
                        any(g.gate_type == 'H' for g in infos) and
                        any(g.gate_type == 'CTRL' for g in infos)
                    ),
                    hint="H(q0) 다음 CNOT(q0→q1) 입니다."
                ),

                TutorialStep(
                    title="얽힘은 단순한 복사가 아니다",
                    instruction="Bell 상태를 유지한 채 회로를 확인하세요.",
                    expected=lambda infos: (
                        any(g.gate_type == 'H' for g in infos) and
                        any(g.gate_type == 'CTRL' for g in infos)
                    ),
                    hint="얽힘 상태에서는 두 큐비트를 독립적으로 설명할 수 없습니다."
                )
        ]

        # -----------------------------
        # QFT Tutorial (Skeleton)
        # -----------------------------
        qft_steps = [
            TutorialStep(
                title="QFT의 핵심 구성요소",
                instruction="Hadamard 게이트를 사용해 QFT 구조를 시작하세요.",
                expected=lambda infos: any(g.gate_type == 'H' for g in infos),
                hint="QFT는 Hadamard로 시작합니다."
            ),

            TutorialStep(
                title="제어 위상 게이트",
                instruction="제어 게이트를 추가해 위상 관계를 만드세요.",
                expected=lambda infos: any(g.gate_type == 'CTRL' for g in infos),
                hint="QFT에는 제어 연산이 반드시 포함됩니다."
            ),

            TutorialStep(
                title="QFT는 가역적이다",
                instruction="QFT 뒤에 역연산을 구성한다고 상상해 보세요.",
                expected=lambda infos: len(infos) >= 2,
                hint="모든 양자 게이트는 되돌릴 수 있습니다."
            )
        ]

        # -----------------------------
        # Superdense Coding Tutorial
        # -----------------------------
        superdense_steps = [
            TutorialStep(
                title="Bell Pair 준비",
                instruction="Alice와 Bob이 공유할 Bell 상태를 준비하세요.",
                expected=lambda infos: (
                    any(g.gate_type == 'H' for g in infos) and
                    any(g.gate_type == 'CTRL' for g in infos)
                ),
                hint="H(q0) → CNOT(q0→q1)"
            ),

            TutorialStep(
                title="Alice의 인코딩",
                instruction="Alice가 자신의 큐비트에 X 또는 Z를 적용하세요.",
                expected=lambda infos: any(
                    g.gate_type in ('X', 'Z') for g in infos
                ),
                hint="보낼 비트에 따라 X 또는 Z를 선택하세요."
            ),

            TutorialStep(
                title="Bob의 디코딩",
                instruction="Bob의 디코딩 회로를 완성하세요.",
                expected=lambda infos: (
                    any(g.gate_type == 'CTRL' for g in infos) and
                    any(g.gate_type == 'H' for g in infos)
                ),
                hint="CNOT 후 Hadamard가 필요합니다."
            )

        
        ]

        deutsch_jozsa_steps = [
            TutorialStep(
                title="초기 상태 |0⟩|1⟩ 만들기",
                instruction=(
                    "Deutsch–Jozsa 알고리즘은 |0⟩|1⟩ 상태에서 시작합니다.\n"
                    "두 번째 큐비트 q[1]에 X 게이트를 배치하세요."
                ),
                expected=lambda infos: (
                    len(infos) == 1 and
                    infos[0].gate_type == "X" and
                    infos[0].row == 1
                ),
                hint="q[1]에 X 게이트 하나만 놓으면 됩니다."
            ),

            TutorialStep(
                title="입력 큐비트 중첩 만들기",
                instruction=(
                    "이제 입력 큐비트에 Hadamard 게이트를 적용합니다.\n"
                    "q[0]에 Hadamard 게이트를 배치하세요."
                ),
                expected=lambda infos: (
                    len(infos) == 2 and
                    any(g.gate_type == "X" and g.row == 1 for g in infos) and
                    any(g.gate_type == "H" and g.row == 0 for g in infos)
                ),
                hint="출력 큐비트(q[1])에는 아무것도 하지 않습니다."
            ),

            TutorialStep(
                title="Oracle 정의하기",
                instruction=(
                    "숨겨진 함수 f(x)를 정의합니다.\n\n"
                    "• constant / balanced 중 선택\n"
                    "• constant: 출력이 항상 0 또는 1\n"
                    "• balanced: 00,01,10,11 중 두 개만 1"
                ),
                expected=lambda infos: self.oracle_truth_table is not None,
                hint="oracle은 회로로 직접 만들지 않습니다.",
                #auto_setup=lambda view: self.open_oracle_dialog()
            ),
            TutorialStep(
                title="오라클 뒤 입력 큐비트에 Hadamard 적용",
                instruction=(
                    "Oracle을 적용한 뒤 입력 큐비트 q[0]에 Hadamard 게이트를 배치하세요."
                ),
                expected=lambda infos: any(g.gate_type == "H" and g.row == 0 for g in infos),
                hint="입력 큐비트(q[0])에 H를 한 번 더 적용합니다."
            ),
            TutorialStep(
                title="입력 큐비트 측정 및 판별",
                instruction=(
                    "입력 큐비트 q[0]을 측정하고 결과를 oracle 유형과 비교하세요.\n"
                    "• constant → 측정 결과 q[0] = 0\n"
                    "• balanced → 측정 결과 q[0] = 1"
                ),
                expected=lambda infos: True,  # 체크 버튼에서 시뮬레이션으로 판별
                hint="Run Measurement로 측정 후 Check를 누르세요."
            ),




        ]

        return [
            Tutorial(
                name="Hadamard Gate",
                theory_key="1. Qubit과 Hadamard Gate",
                steps=hadamard_steps
            ),
            Tutorial(
                name="CNOT Gate",
                theory_key="2. CNOT과 Entanglement",
                steps=cnot_steps
            ),
            Tutorial(
                name="Quantum Fourier Transform",
                theory_key="3. 양자 푸리에 변환 (QFT) 기초",
                steps=qft_steps
            ),
            Tutorial(
                name="Superdense Coding",
                theory_key="4. 초고밀도 코딩 (Superdense Coding)",
                steps=superdense_steps
            ),
            Tutorial(
                name = "Deutsch Jozsa Algorithm",
                theory_key = "5. Deutsch Jozsa Algorithm",
                steps=deutsch_jozsa_steps
            )
        ]
    # --------------------------------------------------------
    # Flow Control
    # --------------------------------------------------------
    def start_tutorial(self):
        if not self.current_tutorial:
            QMessageBox.warning(self, "Select", "튜토리얼을 선택하세요.")
            return

        # 튜토리얼 시작 플래그 설정
        self.tutorials_started = True

        # 튜토리얼에 맞는 큐비트 수로 초기화
        required = self.get_required_qubits(self.current_tutorial)
        if required is not None:
            self.view.n_qubits = max(1, min(required, MAX_QUBITS))
            # 튜토리얼에서는 scene rect를 고정값으로 유지 (일관된 레이아웃)
            self.view.setSceneRect(0, 0, self.view.get_right_end() + 200, 500)
            self.view.clear_circuit(remove_oracle=True)
            self.view.draw_all()

        # 첫 단계 로드
        self.current_step_index = 0
        self.load_step(0)
        self.stack.setCurrentIndex(1)  # Step 페이지 표시
        self.oracle_truth_table = None
        self.oracle_type = None


    def load_step(self, index: int):
        step = self.current_tutorial.steps[index]

        self.step_title.setText(step.title)
        self.step_instruction.setText(step.instruction)

        # 안전한 리셋 (잠시 기능 비활성화)
        """for (r, c), g in list(self.view.circuit.items()):
            self.view.scene.removeItem(g)
        self.view.circuit.clear()

        self.view.draw_all()"""

        if step.auto_setup:
            step.auto_setup(self.view)

        # 오라클 정의 버튼: DJ 튜토리얼의 3~5단계(0-index 2,3,4)에서 표시
        if self.current_tutorial.name == "Deutsch Jozsa Algorithm":
            if self.current_step_index in (2, 3, 4):
                self.btn_define_oracle.show()
            else:
                self.btn_define_oracle.hide()
        
    def check_step(self):
        infos = self.view.export_gate_infos()
        step = self.current_tutorial.steps[self.current_step_index]

        # Deutsch–Jozsa 튜토리얼의 최종 판별 단계는 실제 시뮬레이션으로 확인
        if (
            self.current_tutorial and
            self.current_tutorial.name == "Deutsch Jozsa Algorithm" and
            self.current_step_index == 4  # 0-based: 5번째 단계
        ):
            try:
                qc = QuantumCircuit(self.view.n_qubits, self.view.n_qubits)
                bycol = {}
                for g in infos:
                    bycol.setdefault(g.col, []).append(g)

                for col in sorted(bycol):
                    ops = bycol[col]
                    for g in ops:
                        if g.gate_type=="H": qc.h(g.row)
                        elif g.gate_type=="X": qc.x(g.row)
                        elif g.gate_type=="Y": qc.y(g.row)
                        elif g.gate_type=="Z": qc.z(g.row)
                        elif g.gate_type=="RX": qc.rx(g.angle if g.angle is not None else 0, g.row)
                        elif g.gate_type=="RY": qc.ry(g.angle if g.angle is not None else 0, g.row)
                        elif g.gate_type=="RZ": qc.rz(g.angle if g.angle is not None else 0, g.row)

                    ctrls = [g.row for g in ops if g.gate_type=="CTRL"]
                    xt = [g.row for g in ops if g.gate_type=="X_T"]
                    zt = [g.row for g in ops if g.gate_type=="Z_T"]

                    if len(xt)==1:
                        t = xt[0]
                        if len(ctrls)==0: qc.x(t)
                        elif len(ctrls)==1: qc.cx(ctrls[0], t)
                        else: qc.mcx(ctrls, t)

                    if len(zt)==1:
                        t = zt[0]
                        if len(ctrls)==0: qc.z(t)
                        elif len(ctrls)==1: qc.cz(ctrls[0], t)
                        else: qc.mcz(ctrls, t)

                # 오라클 적용 (Deutsch–Jozsa 전용)
                self.apply_oracle_to_qc(qc)

                # 입력 큐비트(q[0]) 측정 보장
                has_measure = any(inst.operation.name=="measure" for inst in qc.data)
                if not has_measure:
                    qc.measure(0, 0)

                shots = 512
                sim = AerSimulator()
                res = sim.run(qc, shots=shots).result()
                counts = res.get_counts()

                # 리틀엔디언: bitstring의 마지막 문자가 q[0]
                total = sum(counts.values()) or 1
                ones = 0
                for bitstr, c in counts.items():
                    b = bitstr.replace(" ", "")
                    q0 = b[-1]
                    if q0 == '1':
                        ones += c
                prob_one = ones / total

                expected_one = (self.oracle_type == "balanced")
                # 허용 기준: 0.8 이상 일치
                if (expected_one and prob_one >= 0.8) or ((not expected_one) and prob_one <= 0.2):
                    QMessageBox.information(self, "Success", "정확합니다! (DJ 판별 성공)")
                else:
                    QMessageBox.warning(self, "Try again", f"DJ 판별 실패\n예상: q[0]={'1' if expected_one else '0'}\n관측: P(q[0]=1)={prob_one:.2f}")
            except Exception as e:
                QMessageBox.warning(self, "Simulation Error", f"{e}")
            return

        # 일반 단계 검증
        if step.expected(infos):
            QMessageBox.information(self, "Success", "정확합니다!")
        else:
            QMessageBox.warning(self, "Try again", "조건을 만족하지 않습니다.")

    def apply_oracle_to_qc(self, qc: "QuantumCircuit"):
        """현재 설정된 오라클을 Qiskit 회로에 반영 (3-qubit DJ: 2입력 + 1출력)
        입력: q[0], q[1]  출력(y): q[2]
        y <- y XOR f(q[0], q[1]) 형태로 구현.

        - constant 0: 아무 것도 하지 않음
        - constant 1: X(y)
        - balanced (6가지 조합): truth_table에서 1인 입력 패턴들에 대해
          해당 패턴을 만족할 때만 동작하는 다중 제어 X를 y에 적용한다.
          제어-0을 구현하기 위해 해당 입력 비트가 0인 경우 앞뒤로 X를 가한다.
        """
        try:
            if self.oracle_type is None:
                return
            # 2입력(q0,q1) + 출력(y=q2)
            x0, x1, yq = 0, 1, 2
            if self.oracle_type == "constant":
                # constant 1 → y에 X, constant 0 → no-op
                if self.oracle_truth_table and all(v == 1 for v in self.oracle_truth_table.values()):
                    qc.x(yq)
                return
            # balanced: truth table의 1 패턴 각각에 대해 조건부로 y에 X를 적용
            ones_patterns = [k for k, v in (self.oracle_truth_table or {}).items() if v == 1]
            # 안전장치: 2개만 1이어야 함
            if len(ones_patterns) != 2:
                return

            for pat in ones_patterns:
                # pat는 "00","01","10","11" 중 하나
                b0 = pat[0]  # q0 기대값
                b1 = pat[1]  # q1 기대값
                # 제어-0 구현 위해 해당 비트가 '0'이면 앞뒤로 X
                pre = []
                if b0 == '0':
                    qc.x(x0); pre.append(x0)
                if b1 == '0':
                    qc.x(x1); pre.append(x1)

                # 이제 두 제어가 모두 '1'일 때만 동작하는 mcx
                qc.mcx([x0, x1], yq)

                # 원복
                for q in reversed(pre):
                    qc.x(q)
        except Exception:
            # 오라클 미설정 또는 환경 오류는 무시
            pass

    def get_required_qubits(self, tutorial: Tutorial | None) -> int | None:
        """튜토리얼별 최소 필요 큐비트 수를 반환"""
        if tutorial is None:
            return None
        name = tutorial.name
        if name == "Hadamard Gate":
            return 1
        if name == "CNOT Gate":
            return 2
        if name == "Quantum Fourier Transform":
            return 3
        if name == "Superdense Coding":
            return 2
        if name == "Deutsch Jozsa Algorithm":
            # 2비트 입력 + 1비트 출력(y)로 총 3 큐비트 필요
            return 3
        return None

    def run_measurement_tutorial(self):
        """TutorialTab에서 현재 회로로 측정 실행"""
        try:
            # ComposerTab과 동일 로직: 회로 빌드
            infos = self.view.export_gate_infos()
            # 클래식 레지스터는 아직 n_qubits로 초기화
            qc = QuantumCircuit(self.view.n_qubits, self.view.n_qubits)

            bycol = {}
            for g in infos:
                bycol.setdefault(g.col, []).append(g)

            measured_qubits = set()  # 측정된 큐비트 추적
            for col in sorted(bycol):
                ops = bycol[col]
                for g in ops:
                    if g.gate_type=="H": qc.h(g.row)
                    elif g.gate_type=="X": qc.x(g.row)
                    elif g.gate_type=="Y": qc.y(g.row)
                    elif g.gate_type=="Z": qc.z(g.row)
                    elif g.gate_type=="RX": qc.rx(g.angle if g.angle is not None else 0, g.row)
                    elif g.gate_type=="RY": qc.ry(g.angle if g.angle is not None else 0, g.row)
                    elif g.gate_type=="RZ": qc.rz(g.angle if g.angle is not None else 0, g.row)

                ctrls = [g.row for g in ops if g.gate_type=="CTRL"]
                xt = [g.row for g in ops if g.gate_type=="X_T"]
                zt = [g.row for g in ops if g.gate_type=="Z_T"]

                if len(xt)==1:
                    t = xt[0]
                    if len(ctrls)==0: qc.x(t)
                    elif len(ctrls)==1: qc.cx(ctrls[0], t)
                    else: qc.mcx(ctrls, t)

                if len(zt)==1:
                    t = zt[0]
                    if len(ctrls)==0: qc.z(t)
                    elif len(ctrls)==1: qc.cz(ctrls[0], t)
                    else: qc.mcz(ctrls, t)

                # 측정 게이트 처리: 해당 큐비트만 측정
                for g in ops:
                    if g.gate_type == "MEASURE":
                        measured_qubits.add(g.row)
                        qc.measure(g.row, g.row)

            # 오라클 적용 (Deutsch–Jozsa 전용)
            self.apply_oracle_to_qc(qc)

            # 측정 게이트가 없으면 경고
            if not measured_qubits:
                QMessageBox.warning(self, "No Measurement Gate", "측정(M)게이트가 없습니다!")
                return
            
            # 측정된 큐비트 개수만큼만 결과를 자른다
            n_measured = len(measured_qubits)

            sim = AerSimulator()
            shots = 1024
            res = sim.run(qc, shots=shots).result()
            counts = res.get_counts()

            # 측정된 큐비트만 추출: 오른쪽 n_measured 비트만
            if n_measured < self.view.n_qubits:
                filtered_counts = {}
                for bitstring, count in counts.items():
                    # 클래식 비트 문자열의 맨 오른쪽 n_measured 비트만 추출
                    clean = bitstring.replace(" ", "")
                    truncated = clean[-n_measured:] if n_measured > 0 else ""
                    filtered_counts[truncated] = filtered_counts.get(truncated, 0) + count
                counts = filtered_counts

            # 결과 포맷 (Composer와 동일)
            result_lines = [
                "═" * 60,
                "📊 양자 측정 결과",
                "═" * 60,
                f"\n총 시행 횟수: {shots}번\n",
                "주의: 결과는 리틀엔디언(Little Endian) 형식으로 표시됩니다.",
                "      (오른쪽이 q[0], 왼쪽이 q[n-1]입니다)\n",
                "측정 결과:",
                "─" * 60
            ]
            sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            for bitstring, count in sorted_counts:
                clean = bitstring.replace(" ", "")
                pct = (count / shots) * 100
                result_lines.append(f"|{clean}⟩: {count:4d}회 ({pct:6.2f}%)")
            result_lines.append("═" * 60)
            QMessageBox.information(self, "Measurement Result", "\n".join(result_lines))

        except Exception as e:
            QMessageBox.warning(self, "Measurement Error", f"{e}")

    def show_hint(self):
        step = self.current_tutorial.steps[self.current_step_index]
        QMessageBox.information(self, "Hint", step.hint)

    def go_to_intro(self):
        """튜토리얼 소개 페이지로 돌아가기"""
        self.stack.setCurrentIndex(0)
        self.tutorials_started = False
        if self.current_tutorial:
            theory_key = self.current_tutorial.theory_key
            self.intro_title.setText(self.current_tutorial.name)
            self.intro_text.setText(self.TUTORIAL_DATA.get(theory_key, "이 튜토리얼에 대한 정보가 없습니다."))

    def next_step(self):
        if not self.current_tutorial:
            return

        if self.current_step_index + 1 >= len(self.current_tutorial.steps):
            self.progress.setValue(100)  # 진행률 100%
            # ✔ 표시 추가
            row = self.tutorials.index(self.current_tutorial)
            item = self.list_widget.item(row)
            item.setText(f"{self.current_tutorial.name} ✔")
            
            
            QMessageBox.information(
                self,
                "Tutorial Complete",
                "튜토리얼을 완료했습니다 🎉"
            )
            self.btn_next.setEnabled(False)
            return

        self.current_step_index += 1
        self.load_step(self.current_step_index)
        progress_percent = int((self.current_step_index / len(self.current_tutorial.steps)) * 100)
        self.progress.setValue(progress_percent)

            

    def reset_step(self):
        """현재 스텝 리셋 - 회로 초기화"""
        self.view.clear_circuit(remove_oracle=False)
        self.load_step(self.current_step_index)


def load_step(self, index: int):
    if index >= len(self.current_tutorial.steps):
        QMessageBox.warning(self, "Error", "Invalid tutorial step index")
        return

# ============================================================
# MAIN WINDOW (ComposerTab + TutorialTab)
# ============================================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(TutorialTab(), "Tutorial")
        tabs.addTab(ComposerTab(), "Circuit Composer")

        self.setWindowTitle("Quantum Circuit Composer — With Tutorial")
        
class BlochWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bloch Sphere Visualization")
        self.resize(520,620)

        layout = QVBoxLayout(self)
        self.canvas = BlochCanvas(self)
        layout.addWidget(self.canvas)

    def update_bloch(self, rho, qubit_index):
        self.canvas.update_bloch(rho, qubit_index)
        self.show()
        self.raise_()
        self.activateWindow()

def main():
    app = QApplication(sys.argv)
    # Windows 한글 가독성 향상을 위해 기본 폰트를 맑은 고딕으로 설정
    try:
        from PyQt6.QtGui import QFont
        app.setFont(QFont("Malgun Gothic", 10))
    except Exception:
        pass
    w = MainWindow()
    w.resize(1450, 800)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
