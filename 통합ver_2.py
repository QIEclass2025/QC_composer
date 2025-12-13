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
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QLabel, QPushButton, QMessageBox,
    QTabWidget, QDialog, QTextEdit, QInputDialog, QGraphicsDropShadowEffect,
    QSplitter, QScrollArea, QSizePolicy    # tutorial용 import
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

        self.hovering = False
        self.update_text()
        self._center()

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
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(60,60,60,130))
        self.setGraphicsEffect(shadow)

    def hoverLeaveEvent(self, e):
        self.hovering = False
        self.setGraphicsEffect(None)

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
        """UI 전체 다시 그리기 / 격자 재배치 / 선 재그리기"""
        
        
        for it in list(self.scene.items()):
            if isinstance(it, (GateItem, QGraphicsTextItem, BlochButtonItem)):
                continue
            if isinstance(getattr(it, "parentItem", lambda: None)(), GateItem):
                continue
            # 🔥 FIX: 실제로 이 scene에 속해 있는 아이템만 제거
            if it.scene() != self.scene:
                continue
            self.scene.removeItem(it)



        # 1. Palette Gate 제거
        if self.palette_gate is not None:
            self.scene.removeItem(self.palette_gate)
            self.palette_gate = None

        # 2. GateItem / Text / 버튼 등 제외하고 싹 지움
        for it in list(self.scene.items()):
            if isinstance(it, (GateItem, QGraphicsTextItem, BlochButtonItem)):
                continue
            if isinstance(getattr(it, "parentItem", lambda: None)(), GateItem):
                continue
            self.scene.removeItem(it)

        # 3. 기존 연결선 삭제
        for l in self.connection_lines:
            self.scene.removeItem(l)
        self.connection_lines.clear()

        # 4. 와이어 및 텍스트 다시 그림
        self._draw_wires()

        # 5. 쓰레기통 다시 그림
        self._draw_trash()

        # 6. 기존 GateItem 재배치
        for (r, c), g in list(self.circuit.items()):
            if r >= self.n_qubits:
                # 해당 큐비트 삭제됨 → 제거
                self.scene.removeItem(g)
                del self.circuit[(r, c)]
            else:
                x = X_OFFSET + c * CELL_WIDTH - g.WIDTH / 2
                y = Y_OFFSET + r * ROW_HEIGHT - g.HEIGHT / 2
                g.setPos(x, y)

        # 7. Control ↔ Target 연결선
        self._draw_connections()

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
        center = self.mapToScene(self.viewport().rect().center())
        g.setPos(center.x() - g.WIDTH / 2, Y_OFFSET - 40 - g.HEIGHT / 2)

        self.palette_gate = g
        self.scene.addItem(g)
        g.setZValue(1000)

    # ----------------------------------------------------------
    # SNAP LOGIC (핵심)
    # ----------------------------------------------------------
    def snap_gate(self, g: GateItem):
        """
        격자 스냅 / 삭제 / 스왑 / 다중 타겟 검사 포함
        """
        cx = g.pos().x() + g.WIDTH / 2
        cy = g.pos().y() + g.HEIGHT / 2

        # (1) 쓰레기통 → 삭제
        if self.trash_rect.contains(cx, cy):
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

        col = max(0, min(col, MAX_COLS - 1))
        row = max(0, min(row, self.n_qubits - 1))

        new = (row, col)
        old = (g.row, g.col) if g.row is not None else None

        # (4) 다중 타겟 방지
        other_targets = [
            gg for (rr, cc), gg in self.circuit.items()
            if cc == col and gg.gate_type in ("X_T", "Z_T") and gg is not g
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

        side_panel.addWidget(btn_add)
        side_panel.addWidget(btn_del)
        side_panel.addWidget(self.btn_export)
        side_panel.addWidget(self.btn_measure)
        side_panel.addStretch()
        
        # 상단 영역을 루트 레이아웃에 추가
        layout_root.addWidget(top_widget, stretch=3) # 회로 영역에 더 많은 공간 할당

        # 2. 하단 블로흐 캔버스 추가
        layout_root.addSpacing(15)
        # BlochCanvas는 외부에서 정의되어야 함
        self.bloch_canvas = BlochCanvas(self) 
        layout_root.addWidget(self.bloch_canvas, stretch=2) # Bloch 구 영역 할당

        # [추가] 뷰에 Bloch 구 콜백 연결
        self.view.set_bloch_callback(self.update_single_bloch)

        # 시그널 연결
        btn_add.clicked.connect(self.add_q)
        btn_del.clicked.connect(self.del_q)
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
            self.bloch_canvas.update_bloch(rho, target_qubit_idx)

        except Exception as e:
            QMessageBox.warning(self, "Bloch Error", f"Calculation Failed: {e}")
            self.bloch_canvas.hide()

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
                # 회전 게이트: g.angle을 사용 (None인 경우 0으로 처리되어야 함)
                elif g.gate_type=="RX": qc.rx(g.angle, g.row)
                elif g.gate_type=="RY": qc.ry(g.angle, g.row)
                elif g.gate_type=="RZ": qc.rz(g.angle, g.row)
            
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
                elif g.gate_type=="RX": code.append(f"qc.rx({g.angle}, {g.row})\n")
                elif g.gate_type=="RY": code.append(f"qc.ry({g.angle}, {g.row})\n")
                elif g.gate_type=="RZ": code.append(f"qc.rz({g.angle}, {g.row})\n")
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
            qc = self.build_qiskit_circuit()
        except Exception as e:
            QMessageBox.warning(self,"Circuit Build Error",f"{e}")
            return

        # 측정 게이트가 없으면 모든 큐비트를 측정
        has_measure = any(inst.operation.name=="measure" for inst in qc.data)
        if not has_measure:
            qc.measure_all()

        try:
            # AerSimulator는 Qiskit Aer에서 import 되어야 함
            sim = AerSimulator()
            res = sim.run(qc, shots=1024).result()
            counts = res.get_counts()
        except Exception as e:
            QMessageBox.warning(self,"Simulator Error",f"{e}")
            return

        QMessageBox.information(self,"Measurement Result",str(counts))


# ============================================================
# TUTORIAL TAB  (Imported from tutorial_first.py)
# ============================================================
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
            "👉 하나의 큐비트 전송으로 2비트 정보가 전달되는 것을 직접 확인해 보세요!"

    }

    def __init__(self):
        super().__init__()

        self.steps: List[TutorialStep] = self.build_steps()
        self.current_step_index = 0

        root = QVBoxLayout(self)

        # ---- Title ----
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        root.addWidget(self.title_label)


        # ---- Circuit Area ----
        circuit_box = QHBoxLayout()

        self.view = CircuitView()
        self.palette = PaletteView(self.view)

        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.palette.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        circuit_box.addWidget(self.palette)
        circuit_box.addWidget(self.view, stretch=1)

        root.addLayout(circuit_box, stretch=5)

        # ---- Instruction ----
        self.instruction_box = QTextEdit()
        self.instruction_box.setReadOnly(True)
        self.instruction_box.setMaximumHeight(180)
        self.instruction_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        root.addWidget(self.instruction_box)


        # ---- Control Buttons ----
        btns = QHBoxLayout()
        self.btn_check = QPushButton("Check")
        self.btn_hint = QPushButton("Hint")
        self.btn_next = QPushButton("Next")
        self.btn_reset = QPushButton("Reset Step")

        btns.addWidget(self.btn_check)
        btns.addWidget(self.btn_hint)
        btns.addWidget(self.btn_reset)
        btns.addStretch()
        btns.addWidget(self.btn_next)
        root.addLayout(btns)

        # ---- Signals ----
        self.btn_check.clicked.connect(self.check_step)
        self.btn_hint.clicked.connect(self.show_hint)
        self.btn_next.clicked.connect(self.next_step)
        self.btn_reset.clicked.connect(self.reset_step)

        self.load_step(0)

    # --------------------------------------------------------
    # Tutorial Step Definitions
    # --------------------------------------------------------
    def build_steps(self) -> List[TutorialStep]:
        return [
            TutorialStep(
                title="Step 1: Hadamard Gate",
                instruction="Qubit 0에 Hadamard (H) 게이트를 배치하세요.",
                expected=lambda infos: (
                    len(infos) == 1 and
                    infos[0].gate_type == "H" and infos[0].row == 0
                ),
                hint="왼쪽 팔레트에서 H를 드래그하여 q[0]에 놓으세요.",
            ),
            TutorialStep(
                title="Step 2: Bell State",
                instruction=(
                    "Bell 상태를 만드세요:\n"
                    "1) q[0]에 H\n"
                    "2) q[0] → q[1] CNOT"
                ),
                expected=lambda infos: (
                    any(g.gate_type == 'H' and g.row == 0 for g in infos) and
                    any(g.gate_type == 'CTRL' and g.row == 0 for g in infos) and
                    any(g.gate_type == 'X_T' and g.row == 1 for g in infos)
                ),
                hint="첫 열에 H, 다음 열에 ●(q0) + ⊕(q1)을 배치하세요.",
            ),
            TutorialStep(
                title="Step 3: Superdense Coding – Alice",
                instruction=(
                    "Alice의 인코딩 단계입니다.\n"
                    "q[0]에 X 또는 Z 게이트 중 하나를 추가하세요."
                ),
                expected=lambda infos: any(
                    g.row == 0 and g.gate_type in ('X', 'Z') for g in infos
                ),
                hint="Alice는 자신의 큐비트(q0)에 X 또는 Z를 적용합니다.",
            ),
        ]

    # --------------------------------------------------------
    # Step Control Logic
    # --------------------------------------------------------
    def load_step(self, index: int):
        self.current_step_index = index
        step = self.steps[index]

        self.title_label.setText(step.title)
        self.instruction_box.setText(step.instruction)

        self.view.circuit.clear()
        self.view.scene.clear()
        self.view._update_scene_rect()
        self.view.draw_all()

        if step.auto_setup:
            step.auto_setup(self.view)

    def check_step(self):
        infos = self.view.export_gate_infos()
        step = self.steps[self.current_step_index]

        if step.expected(infos):
            QMessageBox.information(self, "Success", "정확합니다! 다음 단계로 이동하세요.")
        else:
            QMessageBox.warning(self, "Not yet", "아직 요구 조건을 만족하지 않습니다.")

    def show_hint(self):
        step = self.steps[self.current_step_index]
        QMessageBox.information(self, "Hint", step.hint)

    def next_step(self):
        if self.current_step_index + 1 >= len(self.steps):
            QMessageBox.information(self, "Tutorial", "모든 튜토리얼을 완료했습니다 🎉")
            return
        self.load_step(self.current_step_index + 1)

    def reset_step(self):
        self.load_step(self.current_step_index)


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


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1450, 800)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()