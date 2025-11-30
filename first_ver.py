from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QMessageBox,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QLabel,
    QTabWidget,
    QDialog,
    QTextEdit,
)
from PyQt6.QtGui import (
    QColor,
    QPen,
    QPainter,
    QFont,
    QBrush,
)
from PyQt6.QtCore import Qt, QPointF, QRectF


# ====== 회로 설정 ======
N_QUBITS = 3           # 초기 큐빗 수
MAX_QUBITS = 8         # 최대 8개까지
CELL_WIDTH = 80
ROW_HEIGHT = 100
X_OFFSET = 80
Y_OFFSET = 90
PALETTE_OFFSET = 60


@dataclass
class GateInfo:
    gate_type: str
    row: int
    col: int
    angle: Optional[float] = None  # RX/RY/RZ용 파라미터(라디안)


# ============================================================================
#  GateItem (UI + Snap + Hover + Selection)
# ============================================================================
class GateItem(QGraphicsRectItem):
    WIDTH = 60
    HEIGHT = 42
    RADIUS = 8

    def __init__(self, label: str, gate_type: str, circuit_view: "CircuitView"):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)

        self.label = label
        self.gate_type = gate_type
        self.circuit_view = circuit_view

        self.row: Optional[int] = None  # 회로에 스냅되면 0..n-1
        self.col: Optional[int] = None  # 회로에 스냅되면 0..T

        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self.color_normal = QColor("#7EC8E3")
        self.color_hover = QColor("#9EDBFF")
        self.color_selected = QColor("#5EAAD5")

        # 항상 와이어 위에 보이도록 z값 설정
        self.setZValue(10)

        # 텍스트
        self.text_item = QGraphicsTextItem(self)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(Qt.GlobalColor.black)
        self.text_item.setPlainText(self.label)
        self._center_text()

    def _center_text(self):
        rect = self.rect()
        t = self.text_item.boundingRect()
        self.text_item.setPos(
            (rect.width() - t.width()) / 2,
            (rect.height() - t.height()) / 2,
        )

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        if self.isSelected():
            painter.setBrush(self.color_selected)
        else:
            painter.setBrush(self.color_normal)

        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(r, self.RADIUS, self.RADIUS)

    def hoverEnterEvent(self, event):
        self.color_normal = self.color_hover
        self.update()

    def hoverLeaveEvent(self, event):
        self.color_normal = QColor("#7EC8E3")
        self.update()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.circuit_view.snap_gate(self)
        self._center_text()


# ============================================================================
#  CircuitView
# ============================================================================
class CircuitView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setSceneRect(0, 0, 1200, 1000)

        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        # 동적 큐빗 수
        self.n_qubits = N_QUBITS

        # (row, col) -> GateItem (회로에 스냅된 게이트만)
        self.circuit: Dict[Tuple[int, int], GateItem] = {}

        # 팔레트에서 현재 선택된 게이트 (회로 위쪽에 떠있는 상태)
        self.palette_gate: Optional[GateItem] = None

        # 쓰레기통 영역(오른쪽 위)
        self.trash_rect = QRectF(1020, 10, 140, 80)

        self._draw_wires()

    # ------------------------------------------------------------------
    # 와이어 + classical register + 쓰레기통 재그리기
    # ------------------------------------------------------------------
    def _draw_wires(self):
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)

        # 게이트(Rect)와 GateItem 내부 텍스트를 제외하고 모두 제거
        for item in list(self.scene.items()):
            if isinstance(item, GateItem):
                continue
            if isinstance(item, QGraphicsTextItem) and item.parentItem() is not None:
                # GateItem 안의 텍스트
                continue
            self.scene.removeItem(item)

        # Quantum wires + q[i] 레이블
        for i in range(self.n_qubits):
            y = Y_OFFSET + i * ROW_HEIGHT
            line = self.scene.addLine(X_OFFSET, y, 1000, y, pen)
            line.setZValue(0)

            q_label = QGraphicsTextItem(f"q[{i}]")
            font = QFont()
            font.setPointSize(12)
            q_label.setFont(font)
            q_label.setDefaultTextColor(Qt.GlobalColor.black)
            q_label.setPos(X_OFFSET - 60, y - 10)
            q_label.setZValue(0)
            self.scene.addItem(q_label)

        # Classical wire (맨 아래)
        classical_y = Y_OFFSET + self.n_qubits * ROW_HEIGHT
        c_line = self.scene.addLine(X_OFFSET, classical_y, 1000, classical_y, pen)
        c_line.setZValue(0)

        # Classical 레지스터 라벨: c(n)
        c_label = QGraphicsTextItem(f"c({self.n_qubits})")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        c_label.setFont(font)
        c_label.setDefaultTextColor(Qt.GlobalColor.black)
        c_label.setPos(X_OFFSET - 60, classical_y - 10)
        c_label.setZValue(0)
        self.scene.addItem(c_label)

        # 쓰레기통 아이콘
        self._draw_trash()

        # 기존 회로 게이트 재배치 / 범위 밖 게이트 제거
        for (r, c), gate in list(self.circuit.items()):
            if r >= self.n_qubits:
                self.scene.removeItem(gate)
                self.circuit.pop((r, c))
            else:
                nx = X_OFFSET + c * CELL_WIDTH - gate.WIDTH / 2
                ny = Y_OFFSET + r * ROW_HEIGHT - gate.HEIGHT / 2
                gate.setPos(nx, ny)

    def _draw_trash(self):
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        brush = QBrush(QColor("#FFEEEE"))
        rect_item = self.scene.addRect(self.trash_rect, pen, brush)
        rect_item.setZValue(0)

        t_label = QGraphicsTextItem("🗑")
        font = QFont()
        font.setPointSize(24)
        t_label.setFont(font)
        t_label.setDefaultTextColor(Qt.GlobalColor.black)
        t_label.setPos(
            self.trash_rect.x() + self.trash_rect.width() / 2 - 14,
            self.trash_rect.y() + self.trash_rect.height() / 2 - 20,
        )
        t_label.setZValue(0)
        self.scene.addItem(t_label)

        text = QGraphicsTextItem("Trash")
        font2 = QFont()
        font2.setPointSize(10)
        text.setFont(font2)
        text.setDefaultTextColor(Qt.GlobalColor.black)
        text.setPos(self.trash_rect.x() + 10, self.trash_rect.y() + 5)
        text.setZValue(0)
        self.scene.addItem(text)

    # ------------------------------------------------------------------
    # 팔레트에 새 게이트 하나만 생성
    # ------------------------------------------------------------------
    def set_palette_gate(self, gate_type: str, label: str):
        # 기존 팔레트 게이트 제거
        if self.palette_gate is not None:
            self.scene.removeItem(self.palette_gate)
            self.palette_gate = None

        gate = GateItem(label, gate_type, self)
        # 회로 위쪽 팔레트 영역에 위치
        gate.setPos(
            QPointF(
                X_OFFSET + CELL_WIDTH * 0.2,
                Y_OFFSET - PALETTE_OFFSET,
            )
        )
        self.scene.addItem(gate)
        self.palette_gate = gate

    # ------------------------------------------------------------------
    # 게이트를 격자에 snap + 쓰레기통 처리
    # ------------------------------------------------------------------
    def snap_gate(self, gate: GateItem):
        cx = gate.pos().x() + gate.WIDTH / 2
        cy = gate.pos().y() + gate.HEIGHT / 2

        # 1) 쓰레기통 영역이면 삭제
        if self.trash_rect.contains(cx, cy):
            if gate.row is not None:
                self.circuit.pop((gate.row, gate.col), None)
            if gate is self.palette_gate:
                self.palette_gate = None
            self.scene.removeItem(gate)
            return

        # 2) 팔레트 영역(와이어 위쪽) → 스냅 X
        if cy < Y_OFFSET - ROW_HEIGHT * 0.5:
            # 회로에 있던 게이트를 다시 올려놓으면 circuit에서 제거
            if gate.row is not None:
                self.circuit.pop((gate.row, gate.col), None)
                gate.row, gate.col = None, None
            return

        # 3) 회로 격자에 스냅
        col = round((cx - X_OFFSET) / CELL_WIDTH)
        row = round((cy - Y_OFFSET) / ROW_HEIGHT)

        col = max(0, col)
        row = max(0, min(self.n_qubits - 1, row))  # classical 줄에는 못 가게

        nx = X_OFFSET + col * CELL_WIDTH - gate.WIDTH / 2
        ny = Y_OFFSET + row * ROW_HEIGHT - gate.HEIGHT / 2

        key_new = (row, col)
        key_old = (gate.row, gate.col) if gate.row is not None and gate.col is not None else None

        # 예전 자리에 있던 정보 제거
        if key_old is not None and key_old in self.circuit:
            del self.circuit[key_old]

        # 새 자리에 다른 게이트가 이미 있으면 이동 취소
        if key_new in self.circuit and self.circuit[key_new] is not gate:
            # 이전 위치로 복귀 (palette에서 내려온 경우에는 그냥 현재 위치 유지)
            if key_old is not None:
                ox = X_OFFSET + key_old[1] * CELL_WIDTH - gate.WIDTH / 2
                oy = Y_OFFSET + key_old[0] * ROW_HEIGHT - gate.HEIGHT / 2
                gate.setPos(ox, oy)
                self.circuit[key_old] = gate
            return

        # 회로에 등록
        self.circuit[key_new] = gate
        gate.row, gate.col = row, col
        gate.setPos(nx, ny)

        # 팔레트 게이트였다면 이제 회로에 들어갔으므로 비움
        if gate is self.palette_gate:
            self.palette_gate = None

    # ------------------------------------------------------------------
    # Delete 키로 선택된 게이트 삭제
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            for item in list(self.scene.selectedItems()):
                if isinstance(item, GateItem):
                    if item.row is not None:
                        self.circuit.pop((item.row, item.col), None)
                    if item is self.palette_gate:
                        self.palette_gate = None
                    self.scene.removeItem(item)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Export용 GateInfo 리스트
    # ------------------------------------------------------------------
    def export_gate_infos(self) -> List[GateInfo]:
        lst: List[GateInfo] = []
        for (r, c), g in self.circuit.items():
            angle = None
            if g.gate_type in ("RX", "RY", "RZ"):
                # 일단 기본값 pi/2
                angle = 3.141592653589793 / 2
            lst.append(GateInfo(g.gate_type, r, c, angle))
        return sorted(lst, key=lambda x: (x.col, x.row))


# ============================================================================
#  Tutorial Tab (나중에 확장 예정)
# ============================================================================
class TutorialTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel(
            "Quantum Algorithm Tutorial\n\n"
            "튜토리얼 기능은 추후에 구현될 예정입니다.\n"
            "상단의 'Circuit Composer' 탭에서 회로를 직접 만들어볼 수 있습니다."
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)


# ============================================================================
#  Composer Tab (우리가 만든 회로 에디터)
# ============================================================================
class ComposerTab(QWidget):
    def __init__(self):
        super().__init__()

        main_layout = QHBoxLayout(self)

        # ---------- 왼쪽 패널 (팔레트 + 설명 + 버튼들) ----------
        panel = QVBoxLayout()
        main_layout.addLayout(panel)

        # 게이트 선택 버튼들
        btn_ctrl = QPushButton("● Control")
        btn_xtgt = QPushButton("⊕ X Target")
        btn_ztgt = QPushButton("⊙ Z Target")

        btn_h = QPushButton("H")
        btn_x = QPushButton("X")
        btn_y = QPushButton("Y")
        btn_z = QPushButton("Z")

        btn_rx = QPushButton("Rx")
        btn_ry = QPushButton("Ry")
        btn_rz = QPushButton("Rz")

        btn_measure = QPushButton("M (Measure)")

        panel.addWidget(btn_ctrl)
        panel.addWidget(btn_xtgt)
        panel.addWidget(btn_ztgt)

        panel.addSpacing(10)

        panel.addWidget(btn_h)
        panel.addWidget(btn_x)
        panel.addWidget(btn_y)
        panel.addWidget(btn_z)

        panel.addSpacing(10)

        panel.addWidget(btn_rx)
        panel.addWidget(btn_ry)
        panel.addWidget(btn_rz)

        panel.addSpacing(10)

        panel.addWidget(btn_measure)

        panel.addSpacing(15)

        # 큐빗 추가/삭제
        btn_add_qubit = QPushButton("Add Qubit")
        btn_del_qubit = QPushButton("Delete Qubit")
        panel.addWidget(btn_add_qubit)
        panel.addWidget(btn_del_qubit)

        panel.addSpacing(10)

        btn_export = QPushButton("Export to Qiskit")
        panel.addWidget(btn_export)

        panel.addSpacing(10)

        # Help 버튼
        btn_help = QPushButton("Help")
        panel.addWidget(btn_help)

        panel.addSpacing(20)

        # 게이트 설명 라벨
        self.description_label = QLabel("게이트를 선택하면 설명이 여기에 표시됩니다.")
        self.description_label.setWordWrap(True)
        self.description_label.setMinimumWidth(230)
        panel.addWidget(self.description_label)
        panel.addStretch()

        # ---------- 오른쪽: 회로 캔버스 ----------
        self.view = CircuitView()
        main_layout.addWidget(self.view, stretch=1)

        # 게이트 설명 텍스트 사전
        self.gate_descriptions: Dict[str, str] = {
            "CTRL": (
                "Control gate (●)\n"
                "같은 column 안의 Target(X⊕ 또는 Z⊙)을 제어합니다.\n"
                "- Control 0개 + X Target → X\n"
                "- Control 1개 + X Target → CNOT\n"
                "- Control n개 + X Target → MCX\n"
                "- Control 0개 + Z Target → Z\n"
                "- Control 1개 + Z Target → CZ\n"
                "- Control n개 + Z Target → MCZ"
            ),
            "X_T": (
                "X Target gate (⊕)\n"
                "Control과 함께 놓이면 CNOT/MCX, 혼자 놓이면 단일 X처럼 동작합니다."
            ),
            "Z_T": (
                "Z Target gate (⊙)\n"
                "Control과 함께 놓이면 CZ/MCZ, 혼자 놓이면 단일 Z처럼 동작합니다."
            ),
            "H": (
                "Hadamard gate (H)\n"
                "입력이 |0⟩이면 (|0⟩ + |1⟩)/√2,\n"
                "입력이 |1⟩이면 (|0⟩ - |1⟩)/√2 상태로 만듭니다.\n"
                "즉, 입력 상태에 따라 위상이 포함된 중첩 상태를 생성합니다."
            ),
            "X": "Pauli-X gate: |0⟩ ↔ |1⟩, 고전적인 NOT과 유사한 연산입니다.",
            "Y": "Pauli-Y gate: π만큼 Y축 회전을 수행하며, 위상까지 변화시킵니다.",
            "Z": "Pauli-Z gate: |1⟩의 위상에 -1을 곱하는 위상 반전 게이트입니다.",
            "RX": "Rx(θ): Bloch sphere의 X축에 대한 회전 게이트입니다. (기본 θ = π/2)",
            "RY": "Ry(θ): Bloch sphere의 Y축에 대한 회전 게이트입니다. (기본 θ = π/2)",
            "RZ": "Rz(θ): Bloch sphere의 Z축에 대한 회전 게이트입니다. (기본 θ = π/2)",
            "MEASURE": (
                "Measurement gate (M)\n"
                "해당 큐빗을 classical bit c[i]에 측정합니다.\n"
                "이 프로그램에서는 모든 큐빗이 초기 상태 |0⟩에서 시작한다고 가정합니다."
            ),
        }

        # 버튼 → 게이트 선택 연결
        btn_ctrl.clicked.connect(lambda: self._select_gate("CTRL", "●"))
        btn_xtgt.clicked.connect(lambda: self._select_gate("X_T", "⊕"))
        btn_ztgt.clicked.connect(lambda: self._select_gate("Z_T", "⊙"))

        btn_h.clicked.connect(lambda: self._select_gate("H", "H"))
        btn_x.clicked.connect(lambda: self._select_gate("X", "X"))
        btn_y.clicked.connect(lambda: self._select_gate("Y", "Y"))
        btn_z.clicked.connect(lambda: self._select_gate("Z", "Z"))

        btn_rx.clicked.connect(lambda: self._select_gate("RX", "Rx"))
        btn_ry.clicked.connect(lambda: self._select_gate("RY", "Ry"))
        btn_rz.clicked.connect(lambda: self._select_gate("RZ", "Rz"))

        btn_measure.clicked.connect(lambda: self._select_gate("MEASURE", "M"))

        btn_add_qubit.clicked.connect(self._add_qubit)
        btn_del_qubit.clicked.connect(self._delete_qubit)

        btn_export.clicked.connect(self._export_qiskit)
        btn_help.clicked.connect(self._open_help)

    # --------------------------------------------------------------
    # 게이트 선택: 팔레트에 하나만 띄우고, 설명 업데이트
    # --------------------------------------------------------------
    def _select_gate(self, gate_type: str, label: str):
        self.view.set_palette_gate(gate_type, label)
        desc = self.gate_descriptions.get(gate_type, "")
        if desc:
            self.description_label.setText(desc)
        else:
            self.description_label.setText(f"{gate_type} gate")

    # --------------------------------------------------------------
    # Qubit 추가/삭제
    # --------------------------------------------------------------
    def _add_qubit(self):
        if self.view.n_qubits >= MAX_QUBITS:
            QMessageBox.information(self, "Limit", f"최대 {MAX_QUBITS}개의 큐빗까지 가능합니다.")
            return
        self.view.n_qubits += 1
        self.view._draw_wires()

    def _delete_qubit(self):
        if self.view.n_qubits <= 1:
            QMessageBox.warning(self, "Limit", "최소 1개의 큐빗은 남겨야 합니다.")
            return

        remove_row = self.view.n_qubits - 1

        # 마지막 줄의 게이트 제거
        for (r, c), gate in list(self.view.circuit.items()):
            if r == remove_row:
                self.view.scene.removeItem(gate)
                self.view.circuit.pop((r, c))

        self.view.n_qubits -= 1
        self.view._draw_wires()

    # --------------------------------------------------------------
    # Help 다이얼로그
    # --------------------------------------------------------------
    def _open_help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Quantum Gate Help")

        layout = QVBoxLayout(dlg)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setMinimumSize(450, 550)

        help_text = """
📌 Quantum Circuit Composer Help

➤ 모든 큐빗은 초기 상태 |0⟩ 에서 시작합니다.

────────────────────────────────────
● Control gate
  같은 column 안의 Target(X⊕ 또는 Z⊙)을 제어합니다.
  - Control 0개 + X Target → X
  - Control 1개 + X Target → CNOT
  - Control n개 + X Target → MCX
  - Control 0개 + Z Target → Z
  - Control 1개 + Z Target → CZ
  - Control n개 + Z Target → MCZ

⊕ X Target gate
  Control과 함께 사용하면 CNOT/MCX를 만듭니다.
  Control 없이 사용하면 단일 X 게이트처럼 동작합니다.

⊙ Z Target gate
  Control과 함께 사용하면 CZ/MCZ를 만듭니다.
  Control 없이 사용하면 단일 Z 게이트처럼 동작합니다.

H (Hadamard)
  입력이 |0⟩이면 (|0⟩ + |1⟩)/√2,
  입력이 |1⟩이면 (|0⟩ - |1⟩)/√2.
  입력 상태에 따라 위상이 다른 중첩 상태를 만듭니다.

X, Y, Z (Pauli gates)
  X: |0⟩ ↔ |1⟩, 고전적인 NOT과 유사
  Y: Y축 회전과 위상 변화
  Z: |1⟩의 위상을 -1로 반전

Rx, Ry, Rz (Rotation gates)
  Bloch sphere의 X/Y/Z 축을 기준으로 θ 라디안 회전합니다.
  현재 기본값 θ = π/2 입니다.

M (Measurement)
  해당 큐빗을 classical bit c[i]에 측정합니다.

────────────────────────────────────
회로 편집 기능:
  - 왼쪽 패널에서 게이트를 선택하면,
    회로 위쪽 팔레트 영역에 해당 게이트가 1개 나타납니다.
  - 이 GateItem을 드래그하여 원하는 큐빗 선 위에 놓으면
    격자에 스냅(snap)됩니다.
  - 오른쪽 위 Trash(🗑) 영역에 드래그하면 삭제됩니다.
  - Delete 키를 눌러 선택된 게이트를 삭제할 수도 있습니다.
  - Add/Delete Qubit 버튼으로 큐빗 줄을 추가/삭제할 수 있습니다.
"""
        text.setText(help_text)
        layout.addWidget(text)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.close)
        layout.addWidget(btn_close)

        dlg.exec()

    # --------------------------------------------------------------
    # Qiskit Export
    # --------------------------------------------------------------
    def _export_qiskit(self):
        try:
            from qiskit import QuantumCircuit
        except Exception:
            QMessageBox.warning(self, "Error", "Qiskit이 없습니다.\n터미널에서: uv add qiskit")
            return

        gates = self.view.export_gate_infos()

        qc = QuantumCircuit(self.view.n_qubits, self.view.n_qubits)

        by_col: Dict[int, List[GateInfo]] = {}
        for g in gates:
            by_col.setdefault(g.col, []).append(g)

        try:
            for col in sorted(by_col.keys()):
                ops = by_col[col]

                # 1. 단일 큐빗 게이트 (H, X, Y, Z, RX, RY, RZ)
                for g in ops:
                    if g.gate_type == "H":
                        qc.h(g.row)
                    elif g.gate_type == "X":
                        qc.x(g.row)
                    elif g.gate_type == "Y":
                        qc.y(g.row)
                    elif g.gate_type == "Z":
                        qc.z(g.row)
                    elif g.gate_type == "RX":
                        qc.rx(g.angle, g.row)
                    elif g.gate_type == "RY":
                        qc.ry(g.angle, g.row)
                    elif g.gate_type == "RZ":
                        qc.rz(g.angle, g.row)

                # 2. Controlled X/Z 구조 (CTRL + X_T / Z_T)
                ctrls = [g for g in ops if g.gate_type == "CTRL"]
                x_tgts = [g for g in ops if g.gate_type == "X_T"]
                z_tgts = [g for g in ops if g.gate_type == "Z_T"]

                num_targets = len(x_tgts) + len(z_tgts)
                if num_targets > 1:
                    raise ValueError(
                        f"column {col}: Target gate(X_T/Z_T)는 한 개만 있어야 합니다."
                    )

                # X 타깃 (단일 X, CNOT, MCX)
                if len(x_tgts) == 1:
                    tgt = x_tgts[0].row
                    if len(ctrls) == 0:
                        qc.x(tgt)
                    elif len(ctrls) == 1:
                        qc.cx(ctrls[0].row, tgt)
                    else:
                        ctrl_list = [c.row for c in ctrls]
                        qc.mcx(ctrl_list, tgt)

                # Z 타깃 (단일 Z, CZ, MCZ)
                if len(z_tgts) == 1:
                    tgt = z_tgts[0].row
                    if len(ctrls) == 0:
                        qc.z(tgt)
                    elif len(ctrls) == 1:
                        qc.cz(ctrls[0].row, tgt)
                    else:
                        ctrl_list = [c.row for c in ctrls]
                        qc.mcz(ctrl_list, tgt)

                # 3. 측정
                for g in ops:
                    if g.gate_type == "MEASURE":
                        qc.measure(g.row, g.row)

        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Qiskit 회로 생성 중 오류:\n{e}")
            return

        QMessageBox.information(self, "Qiskit Export", str(qc))


# ============================================================================
#  MainWindow: 탭으로 Tutorial / Composer 제공
# ============================================================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quantum Learning Environment")

        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        self.tutorial_tab = TutorialTab()
        self.composer_tab = ComposerTab()

        tabs.addTab(self.tutorial_tab, "Tutorial")
        tabs.addTab(self.composer_tab, "Circuit Composer")


# ============================================================================
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1300, 800)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
