# ============================================================
# Quantum Circuit Composer — DRAG & DROP FIXED FINAL VERSION
# ============================================================

from __future__ import annotations
import sys
import math
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QLabel, QPushButton, QMessageBox,
    QTabWidget, QDialog, QTextEdit, QInputDialog,
    QGraphicsDropShadowEffect
)
from PyQt6.QtGui import QColor, QPen, QPainter, QFont, QBrush, QLinearGradient, QCursor, QDrag
from PyQt6.QtCore import Qt, QRectF, QPointF, QMimeData

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator


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
        # Ensure the item receives left-button mouse events (needed for palette dragging)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)

        # Make ALL items movable so Qt delivers mouseMoveEvent during drag
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

    # --------------------------------------------------------
    def format_pi_fraction(self, angle):
        if angle is None:
            return ""
        coef = angle / math.pi
        best_num, best_den, best_err = None, None, 999
        for den in range(1, 9):
            num = round(coef * den)
            err = abs(num/den - coef)
            if err < best_err:
                best_err, best_num, best_den = err, num, den
        if best_err < 1e-3:
            if best_num == 0:
                return "0"
            if best_den == 1:
                return "π" if best_num == 1 else f"{best_num}π"
            return f"{'' if best_num == 1 else best_num}π/{best_den}"
        return f"{coef:.2f}π"

    # --------------------------------------------------------
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

    # --------------------------------------------------------
    def _center(self):
        r = self.rect()
        t = self.text.boundingRect()
        self.text.setPos((r.width() - t.width()) / 2,
                         (r.height() - t.height()) / 2)

    # --------------------------------------------------------
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

    # --------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            if not self.palette_mode and self.gate_type in ("RX","RY","RZ"):
                self.open_angle_dialog()
            return
        print(f"GateItem.mousePressEvent: label={self.label}, palette_mode={self.palette_mode}, button={e.button()}", file=sys.stderr)
        e.accept()
        if self.palette_mode:
            self.drag_started = False
            print(f"GateItem.mousePressEvent: drag_started reset for {self.label}", file=sys.stderr)
        super().mousePressEvent(e)

    # --------------------------------------------------------
    def mouseMoveEvent(self, e):
        print(f"GateItem.mouseMoveEvent: label={self.label}, palette_mode={self.palette_mode}, buttons={e.buttons()}", file=sys.stderr)
        if self.palette_mode:
            if not self.drag_started:
                self.drag_started = True
                # Clone 생성 (각도 복사)
                self.clone = GateItem(self.label, self.gate_type,
                                      self.view, palette_mode=False)
                self.clone.angle = self.angle  # Copy angle from palette item
                if self.view:
                    self.view.scene.addItem(self.clone)
                    self.clone.setZValue(1000)
                    print(f"GateItem.mouseMoveEvent: clone created for {self.label}", file=sys.stderr)
            
            # Update clone position based on global cursor
            if self.clone:
                global_pos = QCursor.pos()
                circuit_view_pos = self.view.mapFromGlobal(global_pos)
                circuit_scene_pos = self.view.mapToScene(circuit_view_pos)
                self.clone.setPos(
                    circuit_scene_pos.x() - self.clone.WIDTH/2,
                    circuit_scene_pos.y() - self.clone.HEIGHT/2
                )
                print(f"GateItem.mouseMoveEvent: clone pos updated to {circuit_scene_pos.x()},{circuit_scene_pos.y()}", file=sys.stderr)
        else:
            # For circuit items, allow normal move but snap afterwards
            super().mouseMoveEvent(e)

    # --------------------------------------------------------
    def mouseReleaseEvent(self, e):
        if self.palette_mode:
            # If a clone was created during dragging from the palette, snap it into the circuit
            if self.clone:
                print(f"mouseReleaseEvent: dropping clone for {self.label}", file=sys.stderr)
                try:
                    self.view.snap_gate(self.clone)
                except Exception as ex:
                    print(f"mouseReleaseEvent: error snapping clone: {ex}", file=sys.stderr)
                self.clone = None
            self.drag_started = False
        else:
            super().mouseReleaseEvent(e)
            if self.view:
                self.view.snap_gate(self)
        print(f"GateItem.mouseReleaseEvent: label={self.label}, palette_mode={self.palette_mode}", file=sys.stderr)

    # --------------------------------------------------------
    def hoverEnterEvent(self, e):
        self.hovering = True
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(60, 60, 60, 130))
        self.setGraphicsEffect(shadow)

    def hoverLeaveEvent(self, e):
        self.hovering = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setGraphicsEffect(None)

    # --------------------------------------------------------
    def paint(self, p, opt, widget=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        grad = QLinearGradient(0, 0, 0, self.HEIGHT)
        if self.hovering:
            grad.setColorAt(0, QColor("#C7ECFF"))
            grad.setColorAt(1, QColor("#9EDBFF"))
        else:
            grad.setColorAt(0, QColor("#93D5F5"))
            grad.setColorAt(1, QColor("#6FBDE5"))

        p.setBrush(QBrush(grad))
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        p.setPen(pen)
        p.drawRoundedRect(self.rect(), self.RADIUS, self.RADIUS)


# ============================================================
# CIRCUIT VIEW
# ============================================================
class CircuitView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.circuit: Dict[Tuple[int,int], GateItem] = {}
        self.n_qubits = N_QUBITS
        self.trash_rect = None

        self.update_scene_rect()
        self.draw_all()

    # --------------------------------------------------------
    def get_right_end(self):
        return X_OFFSET + CELL_WIDTH * MAX_COLS

    def update_scene_rect(self):
        self.setSceneRect(
            0, 0,
            self.get_right_end() + 200,
            Y_OFFSET + (self.n_qubits + 1)*ROW_HEIGHT + 200
        )
        self.trash_rect = QRectF(self.get_right_end() - 90, 10, 70, 60)

    # --------------------------------------------------------
    def draw_all(self):
        for it in list(self.scene.items()):
            if isinstance(it, GateItem):
                continue
            if isinstance(it, QGraphicsTextItem) and isinstance(it.parentItem(), GateItem):
                continue
            self.scene.removeItem(it)

        self.draw_wires()
        self.draw_trash()

        for (r, c), g in self.circuit.items():
            g.setPos(
                X_OFFSET + c*CELL_WIDTH - g.WIDTH/2,
                Y_OFFSET + r*ROW_HEIGHT - g.HEIGHT/2
            )

        # draw multi-qubit control/target connectors
        self.draw_multi_qubit_ops()

    # --------------------------------------------------------
    def draw_wires(self):
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)

        right = self.get_right_end()
        for i in range(self.n_qubits):
            y = Y_OFFSET + i*ROW_HEIGHT
            self.scene.addLine(X_OFFSET - 30, y, right - 30, y, pen)

            lbl = QGraphicsTextItem(f"q[{i}]")
            lbl.setFont(QFont("Segoe UI", 11))
            # Nudge labels slightly left and up for better alignment
            lbl.setPos(X_OFFSET - 64, y - 14)
            self.scene.addItem(lbl)

        cy = Y_OFFSET + self.n_qubits*ROW_HEIGHT
        self.scene.addLine(X_OFFSET - 30, cy, right - 30, cy, pen)
        c_lbl = QGraphicsTextItem(f"c[{self.n_qubits}]")
        c_lbl.setFont(QFont("Segoe UI", 11))
        c_lbl.setPos(X_OFFSET - 64, cy - 14)
        self.scene.addItem(c_lbl)

    # --------------------------------------------------------
    def draw_trash(self):
        pen = QPen(Qt.GlobalColor.black)
        brush = QBrush(QColor("#FFCCCC"))
        self.scene.addRect(self.trash_rect, pen, brush)

        t = QGraphicsTextItem("🗑")
        t.setFont(QFont("Segoe UI", 20))
        t.setPos(self.trash_rect.x() + 18, self.trash_rect.y() + 8)
        self.scene.addItem(t)

    # --------------------------------------------------------
    def draw_multi_qubit_ops(self):
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)

        # For each column, check for controls and a single target
        cols = set(c for (_r, c) in self.circuit.keys())
        for col in cols:
            ops = [(r, g) for (r, c), g in self.circuit.items() if c == col]
            if not ops:
                continue

            ctrls = [r for (r, g) in ops if g.gate_type == "CTRL"]
            xts = [r for (r, g) in ops if g.gate_type == "X_T"]
            zts = [r for (r, g) in ops if g.gate_type == "Z_T"]

            targets = xts + zts

            # Only draw if exactly one target present and at least one control
            if len(targets) == 1 and len(ctrls) >= 1:
                all_rows = ctrls + targets
                top = min(all_rows)
                bottom = max(all_rows)

                x = X_OFFSET + col*CELL_WIDTH
                y1 = Y_OFFSET + top*ROW_HEIGHT
                y2 = Y_OFFSET + bottom*ROW_HEIGHT

                # draw vertical connector (on top)
                line = self.scene.addLine(x, y1, x, y2, pen)
                try:
                    line.setZValue(900)
                except Exception:
                    pass
                # draw small ticks at control and target positions (on top)
                for r in all_rows:
                    cy = Y_OFFSET + r*ROW_HEIGHT
                    tick = self.scene.addLine(x-6, cy, x+6, cy, pen)
                    try:
                        tick.setZValue(900)
                    except Exception:
                        pass

    # --------------------------------------------------------
    def snap_gate(self, g: GateItem):
        print(f"snap_gate: placing {g.label} (type={g.gate_type}) pos={g.pos().x()},{g.pos().y()} row/col before={g.row},{g.col} angle={g.angle}", file=sys.stderr)
        cx = g.pos().x() + g.WIDTH/2
        cy = g.pos().y() + g.HEIGHT/2

        if self.trash_rect.contains(cx, cy):
            if g.row is not None:
                self.circuit.pop((g.row, g.col), None)
            self.scene.removeItem(g)
            return

        col = round((cx - X_OFFSET) / CELL_WIDTH)
        row = round((cy - Y_OFFSET) / ROW_HEIGHT)

        col = max(0, min(col, MAX_COLS - 1))
        row = max(0, min(row, self.n_qubits - 1))

        new = (row, col)
        old = (g.row, g.col) if g.row is not None else None

        target = self.circuit.get(new)
        print(f"snap_gate: target at {new} -> {None if target is None else (target.label, target.gate_type)} old={old} new={new}", file=sys.stderr)

        # Prevent placing more than one target (X_T or Z_T) in the same column
        other_targets = [g2 for (r2, c2), g2 in self.circuit.items()
                         if c2 == col and g2.gate_type in ("X_T", "Z_T") and g2 is not g]
        if g.gate_type in ("X_T", "Z_T") and other_targets:
            print(f"snap_gate: cannot place target {g.label} at {new} because another target exists in column {col}", file=sys.stderr)
            # If this is a palette clone, remove it quietly; if moving an existing gate, revert position
            if old is None:
                try:
                    self.scene.removeItem(g)
                except Exception:
                    pass
                return
            else:
                # revert to old position
                g.setPos(
                    X_OFFSET + old[1]*CELL_WIDTH - g.WIDTH/2,
                    Y_OFFSET + old[0]*ROW_HEIGHT - g.HEIGHT/2
                )
                return

        # If target exists and is a different item, handle replacement or swap
        swap_handled = False
        if target is not None and target is not g:
            if old is None:
                # Dropping a clone from the palette onto an occupied cell -> remove target
                print(f"snap_gate: removing target {target.label} at {new} to place clone {g.label}", file=sys.stderr)
                # Remove from circuit dict first
                try:
                    del self.circuit[new]
                except KeyError:
                    pass
                # Then remove from scene
                try:
                    self.scene.removeItem(target)
                except Exception as e:
                    print(f"snap_gate: error removing item from scene: {e}", file=sys.stderr)
                # proceed to place the clone into `new`
            else:
                # Dragging an existing gate onto another occupied cell -> swap positions
                # Remove g from its old slot (we'll replace it with target)
                if old in self.circuit:
                    try:
                        del self.circuit[old]
                    except KeyError:
                        pass

                # Move target into old slot
                self.circuit[old] = target
                target.row, target.col = old
                target.setPos(
                    X_OFFSET + old[1]*CELL_WIDTH - target.WIDTH/2,
                    Y_OFFSET + old[0]*ROW_HEIGHT - target.HEIGHT/2
                )
                print(f"snap_gate: swapped target {target.label} into old slot {old}", file=sys.stderr)
                swap_handled = True

        # If g was previously placed, remove its old mapping (unless it was already handled by swap)
        if old in self.circuit and not swap_handled:
            try:
                del self.circuit[old]
            except KeyError:
                pass

        # Place g into the new slot
        self.circuit[new] = g
        g.row, g.col = row, col

        g.setPos(
            X_OFFSET + col*CELL_WIDTH - g.WIDTH/2,
            Y_OFFSET + row*ROW_HEIGHT - g.HEIGHT/2
        )

        g.update_text()
        print(f"snap_gate: placed {g.label} at {new} with angle={g.angle}", file=sys.stderr)
        # Refresh scene decorations (wires, trash, connectors)
        try:
            self.draw_all()
        except Exception as e:
            print(f"snap_gate: error redrawing scene: {e}", file=sys.stderr)

    # --------------------------------------------------------
    def export_gate_infos(self):
        out = []
        for (r, c), g in self.circuit.items():
            ang = g.angle if g.angle is not None else 0
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
        
        # Disable view drag mode so item mouse events work properly
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self.init_palette()

    def init_palette(self):
        gates = [
            ("CTRL","●"), ("X_T","⊕"), ("Z_T","⊙"),
            ("H","H"), ("X","X"), ("Y","Y"), ("Z","Z"),
            ("RX","Rx"), ("RY","Ry"), ("RZ","Rz"),
            ("MEASURE","M"),
        ]

        x_pos = [20, 80]
        col, row = 0, 0
        spacing = 70

        for gt, lb in gates:
            item = GateItem(lb, gt, view=self.circuit_view, palette_mode=True)
            item.setPos(x_pos[col], 20 + row*spacing)
            self.scene.addItem(item)

            col += 1
            if col >= 2:
                col = 0
                row += 1


# ============================================================
# COMPOSER TAB
# ============================================================
class ComposerTab(QWidget):
    def __init__(self):
        super().__init__()

        main = QHBoxLayout(self)

        # --------- 핵심 수정: CircuitView 먼저 생성 ---------
        self.view = CircuitView()
        self.palette = PaletteView(self.view)

        main.addWidget(self.palette)
        main.addWidget(self.view, stretch=1)

        side = QVBoxLayout()
        main.addLayout(side)

        btn_add = QPushButton("Add Qubit")
        btn_del = QPushButton("Delete Qubit")
        btn_export = QPushButton("Export Qiskit Code")
        btn_meas = QPushButton("Run Measurement")

        side.addWidget(btn_add)
        side.addWidget(btn_del)
        side.addWidget(btn_export)
        side.addWidget(btn_meas)
        side.addStretch()

        btn_add.clicked.connect(self.add_q)
        btn_del.clicked.connect(self.del_q)
        btn_export.clicked.connect(self.export_qiskit)
        btn_meas.clicked.connect(self.run_measurement)

    # --------------------------------------------------------
    def add_q(self):
        if self.view.n_qubits >= MAX_QUBITS:
            QMessageBox.warning(self, "Limit", "Max 8 qubits")
            return

        self.view.n_qubits += 1
        self.view.update_scene_rect()
        self.view.draw_all()

    # --------------------------------------------------------
    def del_q(self):
        if self.view.n_qubits <= 1:
            QMessageBox.warning(self, "Limit", "At least 1 qubit")
            return

        r = self.view.n_qubits - 1

        for (row, col), g in list(self.view.circuit.items()):
            if row == r:
                self.view.scene.removeItem(g)
                del self.view.circuit[(row, col)]

        self.view.n_qubits -= 1
        self.view.update_scene_rect()
        self.view.draw_all()

    # --------------------------------------------------------
    def export_qiskit(self):
        infos = self.view.export_gate_infos()

        code = []
        code.append("from qiskit import QuantumCircuit\n")
        code.append(f"qc = QuantumCircuit({self.view.n_qubits}, {self.view.n_qubits})\n\n")

        for g in infos:
            if g.gate_type == "H": code.append(f"qc.h({g.row})\n")
            elif g.gate_type == "X": code.append(f"qc.x({g.row})\n")
            elif g.gate_type == "Y": code.append(f"qc.y({g.row})\n")
            elif g.gate_type == "Z": code.append(f"qc.z({g.row})\n")
            elif g.gate_type == "RX": code.append(f"qc.rx({g.angle}, {g.row})\n")
            elif g.gate_type == "RY": code.append(f"qc.ry({g.angle}, {g.row})\n")
            elif g.gate_type == "RZ": code.append(f"qc.rz({g.angle}, {g.row})\n")
            elif g.gate_type == "MEASURE":
                code.append(f"qc.measure({g.row}, {g.row})\n")

        dlg = QDialog(self)
        dlg.setWindowTitle("Qiskit Code")
        lay = QVBoxLayout(dlg)

        box = QTextEdit()
        box.setReadOnly(True)
        box.setText("".join(code))
        lay.addWidget(box)

        btn = QPushButton("Copy to Clipboard")
        lay.addWidget(btn)
        btn.clicked.connect(lambda: QApplication.clipboard().setText("".join(code)))

        dlg.resize(600, 450)
        dlg.exec()

    # --------------------------------------------------------
    def build_qiskit_circuit(self):
        infos = self.view.export_gate_infos()
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
                elif g.gate_type=="RX": qc.rx(g.angle, g.row)
                elif g.gate_type=="RY": qc.ry(g.angle, g.row)
                elif g.gate_type=="RZ": qc.rz(g.angle, g.row)

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

            for g in ops:
                if g.gate_type=="MEASURE":
                    qc.measure(g.row, g.row)

        return qc

    # --------------------------------------------------------
    def run_measurement(self):
        qc = self.build_qiskit_circuit()

        if not any(inst.operation.name == "measure" for inst in qc.data):
            qc.measure_all()

        sim = AerSimulator()
        counts = sim.run(qc, shots=1024).result().get_counts()

        QMessageBox.information(self, "Measurement", str(counts))


# ============================================================
# MAIN WINDOW
# ============================================================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(ComposerTab(), "Circuit Composer")
        layout.addWidget(tabs)

        self.setWindowTitle("Quantum Circuit Composer — Drag & Drop FIXED")


# ============================================================
def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1450, 800)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
