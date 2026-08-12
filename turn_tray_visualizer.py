"""Turn Tray Fitter — visual 2D packing tool.

Shows the freezer's turn tray from above as a circle, with a small circle
in the middle representing the tray's center spindle/pole, and lets the
user add any mix of cylinders, cubes, and rectangular prisms to see how
many of each actually fit on the tray and where they land.

Units: millimeters throughout, matching freezer_models.json (R, H,
handle_bar_clearance already in mm) and the mm-based GAP used in
turn-tray-calculator.py.
"""

import sys
import os
import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox, QListWidget,
    QListWidgetItem, QMessageBox, QGraphicsView, QGraphicsScene, QGroupBox,
)
from PyQt6.QtGui import QColor, QBrush, QPen, QPixmap, QPainter, QIcon, QPolygonF
from PyQt6.QtCore import Qt, QPointF

DIRECTORY = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(DIRECTORY, "freezer_models.json")
ICON_PATH = os.path.join(DIRECTORY, "MVE logos", "icon_blue.ico")
LOGO_PATH = os.path.join(DIRECTORY, "MVE logos", "white_logo.png")

DEFAULT_GAP = 3.175            # mm, 1/8" mandatory spacing (wall, object-object)
CENTER_POLE_DIAMETER = 25.4    # mm, ~1" turn tray center spindle

PALETTE = [
    "#4a90d9", "#e07b39", "#4caf50", "#c94f7c", "#f2c14e",
    "#8e6bb0", "#3fbfbf", "#d9534f", "#8bc34a", "#ff8a65",
]


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_freezer_models(json_path: str) -> List[dict]:
    with open(json_path, "r") as f:
        data = json.load(f)
    return data["models"]


# --------------------------------------------------------------------------
# Object model
# --------------------------------------------------------------------------

@dataclass
class ObjectSpec:
    shape: str          # "cylinder" | "cube" | "rect"
    dims: Dict[str, float]
    quantity: int
    color: str
    label: str

    def footprint_eff(self, gap: float) -> Tuple[str, Dict[str, float]]:
        """Footprint padded with the mandatory gap halo (see freezer-packing-algorithm.md)."""
        if self.shape == "cylinder":
            return ("circle", {"r": self.dims["r"] + gap / 2})
        if self.shape == "cube":
            s = self.dims["s"] + gap
            return ("rect", {"l": s, "w": s})
        l = self.dims["l"] + gap
        w = self.dims["w"] + gap
        return ("rect", {"l": l, "w": w})


@dataclass
class PlacedObject:
    spec: ObjectSpec
    x: float
    y: float
    footprint_type: str
    footprint_dims: Dict[str, float]


# --------------------------------------------------------------------------
# Geometry helpers (all shapes are axis-aligned; no rotation in v1)
# --------------------------------------------------------------------------

def _clamp(value, lo, hi):
    return max(lo, min(value, hi))


def circle_circle_overlap(x1, y1, r1, x2, y2, r2) -> bool:
    dx, dy = x1 - x2, y1 - y2
    return dx * dx + dy * dy < (r1 + r2) ** 2


def rect_rect_overlap(x1, y1, l1, w1, x2, y2, l2, w2) -> bool:
    return abs(x1 - x2) < (l1 + l2) / 2 and abs(y1 - y2) < (w1 + w2) / 2


def circle_rect_overlap(cx, cy, r, rx, ry, l, w) -> bool:
    closest_x = _clamp(cx, rx - l / 2, rx + l / 2)
    closest_y = _clamp(cy, ry - w / 2, ry + w / 2)
    dx, dy = cx - closest_x, cy - closest_y
    return dx * dx + dy * dy < r * r


def shapes_overlap(t1, d1, x1, y1, t2, d2, x2, y2) -> bool:
    if t1 == "circle" and t2 == "circle":
        return circle_circle_overlap(x1, y1, d1["r"], x2, y2, d2["r"])
    if t1 == "rect" and t2 == "rect":
        return rect_rect_overlap(x1, y1, d1["l"], d1["w"], x2, y2, d2["l"], d2["w"])
    if t1 == "circle" and t2 == "rect":
        return circle_rect_overlap(x1, y1, d1["r"], x2, y2, d2["l"], d2["w"])
    return circle_rect_overlap(x2, y2, d2["r"], x1, y1, d1["l"], d1["w"])


def fits_in_tray(t, d, x, y, R_eff) -> bool:
    if t == "circle":
        return math.hypot(x, y) + d["r"] <= R_eff
    half_l, half_w = d["l"] / 2, d["w"] / 2
    corners = [(x - half_l, y - half_w), (x + half_l, y - half_w),
               (x - half_l, y + half_w), (x + half_l, y + half_w)]
    return all(math.hypot(cx, cy) <= R_eff for cx, cy in corners)


def clears_center(t, d, x, y, center_r) -> bool:
    if t == "circle":
        return not circle_circle_overlap(0, 0, center_r, x, y, d["r"])
    return not circle_rect_overlap(0, 0, center_r, x, y, d["l"], d["w"])


# --------------------------------------------------------------------------
# Tray shape (full circle, or a convex pie-cut such as a half circle)
#
# A wedge is defined by (start_deg, span_deg): the sector sweeps span_deg
# degrees counter-clockwise starting at start_deg. Centered on -90 deg so
# a half circle (span=180) sits "dome up" with its flat cut at the bottom,
# matching how a physically-cut turn tray is normally pictured.
# `span_deg` is capped at <=180 by the UI so the sector stays convex —
# that keeps the corner/tangent-only containment checks below exact.
# --------------------------------------------------------------------------

def angle_bounds(sweep_deg: float) -> Optional[Tuple[float, float]]:
    if sweep_deg is None or sweep_deg >= 359.999:
        return None
    half = sweep_deg / 2.0
    return (-90.0 - half, sweep_deg)  # (start_deg, span_deg)


def in_angle_range(angle_deg: float, start_deg: float, span_deg: float) -> bool:
    a = (angle_deg - start_deg) % 360.0
    return 0.0 <= a <= span_deg


def within_wedge(t, d, x, y, bounds: Optional[Tuple[float, float]]) -> bool:
    """True if the whole shape (not just its center) lies inside the wedge."""
    if bounds is None:
        return True
    start_deg, span_deg = bounds

    if t == "circle":
        r = d["r"]
        dist = math.hypot(x, y)
        if dist <= 1e-9:
            return False
        # Angular half-width the circle subtends as seen from the origin —
        # exact for a circle that doesn't contain the origin (dist > r,
        # already guaranteed by the center-pole clearance check).
        delta = math.degrees(math.asin(min(1.0, r / dist)))
        angle = math.degrees(math.atan2(y, x))
        return (in_angle_range(angle - delta, start_deg, span_deg)
                and in_angle_range(angle + delta, start_deg, span_deg))

    # Rect: the wedge is convex, so containing all 4 corners is sufficient.
    half_l, half_w = d["l"] / 2, d["w"] / 2
    corners = [(x - half_l, y - half_w), (x + half_l, y - half_w),
               (x - half_l, y + half_w), (x + half_l, y + half_w)]
    for cx, cy in corners:
        if math.hypot(cx, cy) <= 1e-9:
            return False
        angle = math.degrees(math.atan2(cy, cx))
        if not in_angle_range(angle, start_deg, span_deg):
            return False
    return True


# --------------------------------------------------------------------------
# Packing engine — greedy nearest-to-center placement
# --------------------------------------------------------------------------

def generate_candidates(R_eff, center_r, spacing, bounds=None, max_rings=250, max_pts_per_ring=720):
    """Polar grid of candidate placement points, closest-to-center first."""
    spacing = max(spacing, 1.0)
    candidates = [(0.0, 0.0)]
    radius = center_r + spacing / 2
    rings = 0
    while radius <= R_eff and rings < max_rings:
        circumference = 2 * math.pi * radius
        num_points = min(max(1, math.floor(circumference / spacing)), max_pts_per_ring)
        for i in range(num_points):
            theta = 2 * math.pi * i / num_points
            if bounds is not None:
                start_deg, span_deg = bounds
                if not in_angle_range(math.degrees(theta), start_deg, span_deg):
                    continue
            candidates.append((radius * math.cos(theta), radius * math.sin(theta)))
        radius += spacing
        rings += 1
    candidates.sort(key=lambda p: p[0] ** 2 + p[1] ** 2)
    return candidates


def _bounding_radius(ftype, fdims) -> float:
    """Radius of the smallest circle centered on the object that contains it."""
    if ftype == "circle":
        return fdims["r"]
    return math.hypot(fdims["l"], fdims["w"]) / 2


class _SpatialIndex:
    """Uniform grid over placed objects so overlap checks only look at nearby
    cells instead of scanning every placed object (needed once a tray holds
    hundreds of objects — a linear scan per candidate point gets very slow)."""

    def __init__(self, cell_size: float, search_radius_cells: int = 2):
        self.cell_size = max(cell_size, 1.0)
        self.search_radius_cells = search_radius_cells
        self.cells: Dict[Tuple[int, int], List[PlacedObject]] = {}

    def _cell(self, x, y) -> Tuple[int, int]:
        return (math.floor(x / self.cell_size), math.floor(y / self.cell_size))

    def add(self, obj: PlacedObject):
        self.cells.setdefault(self._cell(obj.x, obj.y), []).append(obj)

    def nearby(self, x, y):
        cx, cy = self._cell(x, y)
        r = self.search_radius_cells
        for i in range(cx - r, cx + r + 1):
            for j in range(cy - r, cy + r + 1):
                yield from self.cells.get((i, j), ())


def _is_valid_spot(ftype, fdims, x, y, R_eff, center_r, bounds, index: _SpatialIndex) -> bool:
    if not fits_in_tray(ftype, fdims, x, y, R_eff):
        return False
    if not clears_center(ftype, fdims, x, y, center_r):
        return False
    if not within_wedge(ftype, fdims, x, y, bounds):
        return False
    return not any(shapes_overlap(ftype, fdims, x, y, p.footprint_type, p.footprint_dims, p.x, p.y)
                    for p in index.nearby(x, y))


def pack_tray(freezer: dict, object_specs: List[ObjectSpec], gap: float = DEFAULT_GAP,
              sweep_deg: float = 360.0):
    """Places each requested object on the tray (2D, top-down, single layer).

    `sweep_deg` restricts the tray to a pie-cut sector (e.g. 180 = half
    circle); 360 = full circle. Returns (placed_objects, results) where
    results maps object label -> {requested, placed, leftover}.
    """
    if not object_specs:
        return [], {}

    R_eff = freezer["R"] - gap
    center_r = CENTER_POLE_DIAMETER / 2 + gap / 2
    bounds = angle_bounds(sweep_deg)

    footprints = [spec.footprint_eff(gap) for spec in object_specs]
    min_dim = min(min(fdims.values()) for _, fdims in footprints)
    spacing = max(min_dim / 2, 2.0)
    candidates = generate_candidates(R_eff, center_r, spacing, bounds)

    # Cell size covers the largest footprint so any pair of objects that
    # could possibly overlap always falls within the search radius below.
    max_extent = max(_bounding_radius(ftype, fdims) for ftype, fdims in footprints)
    index = _SpatialIndex(cell_size=max(max_extent, spacing / 2))

    placed: List[PlacedObject] = []
    results = {}

    num_candidates = len(candidates)

    for spec, (ftype, fdims) in zip(object_specs, footprints):
        placed_count = 0
        # A candidate rejected for one instance of this exact footprint stays
        # rejected for the next (more placed objects only add constraints),
        # so each spec sweeps the candidate list once instead of restarting
        # from the center for every single object — this is what keeps large
        # quantities responsive.
        idx = 0
        while placed_count < spec.quantity and idx < num_candidates:
            x, y = candidates[idx]
            idx += 1
            if not _is_valid_spot(ftype, fdims, x, y, R_eff, center_r, bounds, index):
                continue
            obj = PlacedObject(spec, x, y, ftype, fdims)
            placed.append(obj)
            index.add(obj)
            placed_count += 1
        results[spec.label] = {
            "requested": spec.quantity,
            "placed": placed_count,
            "leftover": spec.quantity - placed_count,
        }

    return placed, results


def compute_max_fit(freezer: dict, spec: ObjectSpec, gap: float = DEFAULT_GAP,
                     sweep_deg: float = 360.0) -> Dict[str, int]:
    """Max quantity of a single object type that fits in the whole freezer,
    stacked across every vertical layer the interior height allows (see
    freezer-packing-algorithm.md sections 4-5). objects_per_layer comes from
    an actual pack_tray() placement rather than the spec's ring/grid formulas,
    since real geometric placement is already exact here.
    """
    height = spec.dims["s"] if spec.shape == "cube" else spec.dims["h"]
    h_eff = height + gap
    h_usable = freezer["H"] - freezer["handle_bar_clearance"]
    num_layers = max(0, math.floor(h_usable / h_eff))

    if num_layers == 0:
        return {"per_layer": 0, "num_layers": 0, "total": 0}

    probe = ObjectSpec(shape=spec.shape, dims=spec.dims, quantity=10**6,
                        color=spec.color, label=spec.label)
    _, results = pack_tray(freezer, [probe], gap, sweep_deg)
    per_layer = results[probe.label]["placed"]

    return {"per_layer": per_layer, "num_layers": num_layers, "total": per_layer * num_layers}


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------

STYLESHEET = """
    QMainWindow, QWidget {
        background-color: #0a1628;
        color: #ffffff;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 13px;
    }
    QGroupBox {
        border: 1px solid #2a4a7f;
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        color: #6a8ab0;
    }
    QLabel { color: #ffffff; }
    QLabel#titleLabel { font-size: 32px; font-weight: bold; }
    QLineEdit, QComboBox, QSpinBox {
        background-color: #152642;
        color: #ffffff;
        border: 1px solid #2a4a7f;
        border-radius: 6px;
        padding: 6px 10px;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
        border: 1px solid #4a90d9;
    }
    QPushButton {
        background-color: #ffffff;
        color: #0a1628;
        border: none;
        border-radius: 8px;
        padding: 10px 0px;
        font-weight: bold;
    }
    QPushButton:hover { background-color: #dce8ff; }
    QPushButton:pressed { background-color: #b0c8f0; }
    QListWidget {
        background-color: #152642;
        border: 1px solid #2a4a7f;
        border-radius: 6px;
    }
"""

SHAPE_FIELDS = {
    "Cylinder": [("r", "Radius (mm)"), ("h", "Height (mm)")],
    "Cube": [("s", "Side (mm)")],
    "Rectangle": [("l", "Length (mm)"), ("w", "Width (mm)"), ("h", "Height (mm)")],
}
SHAPE_KEY = {"Cylinder": "cylinder", "Cube": "cube", "Rectangle": "rect"}


class TrayCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background-color: #0a1628; border: none;")
        self._last_rect = None

    def draw_tray(self, freezer: Optional[dict], placed_objects: List[PlacedObject],
                  gap: float = DEFAULT_GAP, sweep_deg: float = 360.0):
        self.scene.clear()
        if freezer is None:
            return

        R = freezer["R"]
        target_px = 560
        s = target_px / (2 * R)   # mm -> px scale
        bounds = angle_bounds(sweep_deg)

        outer_d = 2 * R * s
        wall_pen = QPen(QColor("#4a90d9"))
        wall_pen.setWidth(2)
        R_eff = R - gap
        eff_pen = QPen(QColor("#2a4a7f"))
        eff_pen.setStyle(Qt.PenStyle.DashLine)

        if bounds is None:
            self.scene.addEllipse(-R * s, -R * s, outer_d, outer_d, wall_pen, QBrush(QColor("#152642")))
            self.scene.addEllipse(-R_eff * s, -R_eff * s, 2 * R_eff * s, 2 * R_eff * s, eff_pen)
        else:
            self.scene.addPolygon(self._wedge_polygon(R, s, bounds), wall_pen, QBrush(QColor("#152642")))
            self.scene.addPolygon(self._wedge_polygon(R_eff, s, bounds), eff_pen, QBrush())

        pole_r = CENTER_POLE_DIAMETER / 2
        pole_pen = QPen(QColor("#6a8ab0"))
        self.scene.addEllipse(-pole_r * s, -pole_r * s, 2 * pole_r * s, 2 * pole_r * s,
                               pole_pen, QBrush(QColor("#3a5578")))

        for obj in placed_objects:
            color = QColor(obj.spec.color)
            pen = QPen(color.darker(150))
            brush = QBrush(color)
            if obj.footprint_type == "circle":
                r = obj.spec.dims["r"] * s
                item = self.scene.addEllipse(obj.x * s - r, obj.y * s - r, 2 * r, 2 * r, pen, brush)
            else:
                if obj.spec.shape == "cube":
                    l = w = obj.spec.dims["s"] * s
                else:
                    l = obj.spec.dims["l"] * s
                    w = obj.spec.dims["w"] * s
                item = self.scene.addRect(obj.x * s - l / 2, obj.y * s - w / 2, l, w, pen, brush)
            item.setToolTip(obj.spec.label)

        margin = 20
        self.scene.setSceneRect(-R * s - margin, -R * s - margin, outer_d + 2 * margin, outer_d + 2 * margin)
        self._last_rect = self.scene.sceneRect()
        self.fitInView(self._last_rect, Qt.AspectRatioMode.KeepAspectRatio)

    @staticmethod
    def _wedge_polygon(radius: float, s: float, bounds: Tuple[float, float]) -> QPolygonF:
        start_deg, span_deg = bounds
        steps = max(2, int(span_deg / 3) + 1)
        points = [QPointF(0.0, 0.0)]
        for i in range(steps + 1):
            theta = math.radians(start_deg + span_deg * i / steps)
            points.append(QPointF(radius * math.cos(theta) * s, radius * math.sin(theta) * s))
        points.append(QPointF(0.0, 0.0))
        return QPolygonF(points)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._last_rect is not None:
            self.fitInView(self._last_rect, Qt.AspectRatioMode.KeepAspectRatio)


class ControlPanel(QWidget):
    def __init__(self, main_window: "MainWindow"):
        super().__init__()
        self.main_window = main_window
        self.object_specs: List[ObjectSpec] = []
        self.color_index = 0
        self.dim_inputs: Dict[str, QLineEdit] = {}

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setFixedWidth(320)

        # --- Freezer / turn tray selection ---
        freezer_box = QGroupBox("Freezer / Turn Tray")
        freezer_layout = QFormLayout()
        self.freezer_combo = QComboBox()
        self.freezer_combo.currentIndexChanged.connect(self.on_freezer_changed)
        self.radius_label = QLabel("--")
        self.height_label = QLabel("--")
        freezer_layout.addRow("Model:", self.freezer_combo)
        freezer_layout.addRow("Tray radius (mm):", self.radius_label)
        freezer_layout.addRow("Interior height (mm):", self.height_label)
        freezer_box.setLayout(freezer_layout)

        # --- Tray shape (full circle, or a cut like a half circle) & spacing ---
        shape_box = QGroupBox("Tray Shape && Spacing")
        shape_layout = QFormLayout()
        self.tray_shape_combo = QComboBox()
        self.tray_shape_combo.addItems(["Full Circle", "Half Circle", "Custom"])
        self.tray_shape_combo.currentIndexChanged.connect(self.on_tray_shape_changed)

        self.sweep_spin = QDoubleSpinBox()
        self.sweep_spin.setRange(10.0, 180.0)
        self.sweep_spin.setSingleStep(5.0)
        self.sweep_spin.setValue(180.0)
        self.sweep_spin.setSuffix(" deg")
        self.sweep_spin.setEnabled(False)
        self.sweep_spin.valueChanged.connect(self.redraw_tray_boundary)

        self.gap_spin = QDoubleSpinBox()
        self.gap_spin.setRange(0.0, 25.0)
        self.gap_spin.setDecimals(3)
        self.gap_spin.setSingleStep(0.5)
        self.gap_spin.setValue(DEFAULT_GAP)
        self.gap_spin.setSuffix(" mm")
        self.gap_spin.valueChanged.connect(self.redraw_tray_boundary)

        shape_layout.addRow("Tray shape:", self.tray_shape_combo)
        shape_layout.addRow("Wedge angle:", self.sweep_spin)
        shape_layout.addRow("Object gap:", self.gap_spin)
        shape_box.setLayout(shape_layout)

        # --- Add object ---
        add_box = QGroupBox("Add Object")
        add_layout = QVBoxLayout()
        self.shape_combo = QComboBox()
        self.shape_combo.addItems(list(SHAPE_FIELDS.keys()))
        self.shape_combo.currentIndexChanged.connect(self.on_shape_changed)

        self.dim_form = QFormLayout()

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 5000)
        self.qty_spin.setValue(1)

        add_btn = QPushButton("Add to Tray")
        add_btn.setFixedSize(110, 32)
        add_btn.clicked.connect(self.on_add_object)

        max_fit_btn = QPushButton("Max Fit")
        max_fit_btn.setFixedSize(110, 32)
        max_fit_btn.setToolTip(
            "Add this object at the maximum quantity that fits in the whole "
            "freezer, accounting for tray radius, gap, interior height, and "
            "handle bar clearance."
        )
        max_fit_btn.clicked.connect(self.on_max_fit)

        add_btn_row = QHBoxLayout()
        add_btn_row.addStretch()
        add_btn_row.addWidget(add_btn)
        add_btn_row.addSpacing(12)
        add_btn_row.addWidget(max_fit_btn)
        add_btn_row.addStretch()

        add_layout.addWidget(QLabel("Shape:"))
        add_layout.addWidget(self.shape_combo)
        add_layout.addLayout(self.dim_form)
        add_layout.addWidget(QLabel("Quantity:"))
        add_layout.addWidget(self.qty_spin)
        add_layout.addLayout(add_btn_row)
        add_box.setLayout(add_layout)

        # --- Object list ---
        list_box = QGroupBox("Objects in Tray")
        list_layout = QVBoxLayout()
        self.object_list = QListWidget()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.setFixedWidth(150)
        remove_btn.clicked.connect(self.on_remove_selected)
        clear_btn = QPushButton("Clear All")
        clear_btn.setFixedWidth(150) 
        clear_btn.clicked.connect(self.on_clear_all)
        list_layout.addWidget(self.object_list)
        list_layout.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        list_layout.addWidget(clear_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        list_box.setLayout(list_layout)

        pack_btn = QPushButton("Pack && Visualize")
        pack_btn.setFixedWidth(200)         
        pack_btn.clicked.connect(self.on_pack)

        self.results_label = QLabel("")
        self.results_label.setWordWrap(True)
        self.results_label.setTextFormat(Qt.TextFormat.RichText)

        layout.addWidget(freezer_box)
        layout.addWidget(shape_box)
        layout.addWidget(add_box)
        layout.addWidget(list_box)
        layout.addWidget(pack_btn, 0, Qt.AlignmentFlag.AlignHCenter) 
        layout.addWidget(self.results_label)
        self.setLayout(layout)

        self.on_shape_changed(0)

    # -- freezer / tray shape --

    def on_freezer_changed(self, index: int):
        if index < 0 or index >= len(self.main_window.models):
            return
        freezer = self.main_window.models[index]
        self.main_window.freezer = freezer
        self.radius_label.setText(f"{freezer['R']:g}")
        self.height_label.setText(f"{freezer['H']:g}")
        self.redraw_tray_boundary()

    def current_sweep_deg(self) -> float:
        shape = self.tray_shape_combo.currentText()
        if shape == "Full Circle":
            return 360.0
        if shape == "Half Circle":
            return 180.0
        return self.sweep_spin.value()

    def on_tray_shape_changed(self, index: int):
        self.sweep_spin.setEnabled(self.tray_shape_combo.currentText() == "Custom")
        self.redraw_tray_boundary()

    def redraw_tray_boundary(self):
        freezer = self.main_window.freezer
        if freezer is None:
            return
        self.main_window.canvas.draw_tray(freezer, [], self.gap_spin.value(), self.current_sweep_deg())
        self.results_label.setText("")

    # -- add-object form --

    def on_shape_changed(self, index: int):
        while self.dim_form.count():
            item = self.dim_form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.dim_inputs.clear()

        shape_name = list(SHAPE_FIELDS.keys())[index]
        for key, placeholder in SHAPE_FIELDS[shape_name]:
            field_input = QLineEdit()
            field_input.setPlaceholderText(placeholder)
            self.dim_form.addRow(field_input)
            self.dim_inputs[key] = field_input

    def on_add_object(self):
        shape_name = self.shape_combo.currentText()
        shape = SHAPE_KEY[shape_name]

        dims = {}
        try:
            for key, field_input in self.dim_inputs.items():
                value = float(field_input.text())
                if value <= 0:
                    raise ValueError
                dims[key] = value
        except ValueError:
            QMessageBox.warning(self, "Invalid input", "All dimensions must be positive numbers.")
            return

        quantity = self.qty_spin.value()
        color = PALETTE[self.color_index % len(PALETTE)]
        self.color_index += 1

        if shape == "cylinder":
            label = f"Cylinder r={dims['r']:g} h={dims['h']:g}"
        elif shape == "cube":
            label = f"Cube s={dims['s']:g}"
        else:
            label = f"Rect {dims['l']:g}x{dims['w']:g}x{dims['h']:g}"
        label = f"{label} (qty {quantity})"

        spec = ObjectSpec(shape=shape, dims=dims, quantity=quantity, color=color, label=label)
        self.object_specs.append(spec)

        item = QListWidgetItem(f"● {label}")
        item.setForeground(QColor(color))
        self.object_list.addItem(item)

    def on_max_fit(self):
        freezer = self.main_window.freezer
        if freezer is None:
            QMessageBox.warning(self, "No freezer selected", "Select a freezer model first.")
            return

        shape_name = self.shape_combo.currentText()
        shape = SHAPE_KEY[shape_name]

        dims = {}
        try:
            for key, field_input in self.dim_inputs.items():
                value = float(field_input.text())
                if value <= 0:
                    raise ValueError
                dims[key] = value
        except ValueError:
            QMessageBox.warning(self, "Invalid input", "All dimensions must be positive numbers.")
            return

        gap = self.gap_spin.value()
        sweep_deg = self.current_sweep_deg()
        color = PALETTE[self.color_index % len(PALETTE)]

        probe_spec = ObjectSpec(shape=shape, dims=dims, quantity=1, color=color, label="max-fit-probe")
        capacity = compute_max_fit(freezer, probe_spec, gap, sweep_deg)

        if capacity["total"] <= 0:
            QMessageBox.warning(
                self, "Doesn't fit",
                "This object doesn't fit in the freezer at all — check its "
                "height against the interior height and handle bar clearance, "
                "or its footprint against the tray radius."
            )
            return

        self.color_index += 1

        if shape == "cylinder":
            label = f"Cylinder r={dims['r']:g} h={dims['h']:g}"
        elif shape == "cube":
            label = f"Cube s={dims['s']:g}"
        else:
            label = f"Rect {dims['l']:g}x{dims['w']:g}x{dims['h']:g}"
        label = f"{label} (qty {capacity['total']}, max fit)"

        spec = ObjectSpec(shape=shape, dims=dims, quantity=capacity["total"], color=color, label=label)
        self.object_specs.append(spec)

        item = QListWidgetItem(f"● {label}")
        item.setForeground(QColor(color))
        self.object_list.addItem(item)

        QMessageBox.information(
            self, "Max fit calculated",
            f"{capacity['per_layer']} per layer × {capacity['num_layers']} layers "
            f"= {capacity['total']} total added to the tray."
        )

    def on_remove_selected(self):
        for item in self.object_list.selectedItems():
            row = self.object_list.row(item)
            self.object_list.takeItem(row)
            del self.object_specs[row]

    def on_clear_all(self):
        self.object_list.clear()
        self.object_specs.clear()
        self.color_index = 0
        self.redraw_tray_boundary()

    # -- pack --

    def on_pack(self):
        freezer = self.main_window.freezer
        if freezer is None:
            QMessageBox.warning(self, "No freezer selected", "Select a freezer model first.")
            return
        if not self.object_specs:
            QMessageBox.warning(self, "No objects", "Add at least one object to the tray first.")
            return

        gap = self.gap_spin.value()
        sweep_deg = self.current_sweep_deg()
        placed, results = pack_tray(freezer, self.object_specs, gap, sweep_deg)
        self.main_window.canvas.draw_tray(freezer, placed, gap, sweep_deg)

        lines = []
        total_requested = total_placed = 0
        for spec in self.object_specs:
            r = results[spec.label]
            total_requested += r["requested"]
            total_placed += r["placed"]
            status = "#4caf50" if r["leftover"] == 0 else "#e07b39"
            lines.append(
                f'<span style="color:{spec.color}">●</span> {spec.label}: '
                f'<span style="color:{status}">{r["placed"]}/{r["requested"]} placed</span>'
            )
        lines.append(f"<b>Total: {total_placed}/{total_requested} objects placed on tray</b>")
        self.results_label.setText("<br>".join(lines))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Turn Tray Fitter — Visualizer")
        self.resize(1150, 720)
        self.setStyleSheet(STYLESHEET)
        if os.path.isfile(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self.freezer: Optional[dict] = None
        self.models: List[dict] = []
        try:
            self.models = load_freezer_models(JSON_PATH)
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Error", f"Could not load freezer_models.json:\n{e}")

        self.canvas = TrayCanvas()
        self.control_panel = ControlPanel(self)
        self.control_panel.freezer_combo.addItems([m["model_id"] for m in self.models])

        central = QWidget()
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(8) 

        header = QVBoxLayout()
        header.setContentsMargins(10, 10, 10, 10)
        header.setSpacing(4)

        title_label = QLabel("Freezer Rack Capacity Estimator")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        header.addWidget(title_label)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        if os.path.isfile(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH)
            logo_label.setPixmap(
                pixmap.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation)
            )
        header.addWidget(logo_label)

        outer_layout.addLayout(header)

        content_layout = QHBoxLayout()
        content_layout.addWidget(self.control_panel, 0)
        content_layout.addWidget(self.canvas, 1) 
        outer_layout.addLayout(content_layout) 

        central.setLayout(outer_layout)
        self.setCentralWidget(central) 

        if self.models:
            self.control_panel.on_freezer_changed(0)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
