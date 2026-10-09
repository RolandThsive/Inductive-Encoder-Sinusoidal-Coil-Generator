#!/usr/bin/env python3
"""Twisted-Fields inductive encoder coil generator, with a 4-phase/1-loop fix.

Based on the geometry and routing rules in:
https://github.com/Twisted-Fields/induction_encoder/blob/main/spiral_pcb_2024.py

Key fix
-------
The original layer-switch schedule for phases 2 and 3 assumes there are exactly
TWO half-turn loop sections: loop 0 ends with a layer change, then loop 1 starts
with the matching change and adds a mid-turn crossover. When ``loops = 1``, the
loop-1 branch never executes. Phases 2 and 3 therefore miss the start and
mid-turn transitions required to close a one-revolution trace consistently.
For ``loops == 1``, phases 2 and 3 now use the full-turn symmetric schedule:
start transition + mid-turn crossover + end transition, matching phases 0 and 1.

This edition writes a native KiCad .kicad_pcb file directly (no pykicad
installation required). NumPy is also not required. Copper widths are set to
0.25 mm for explicit, reproducible geometry; the upstream script leaves width
to pykicad's Segment defaults.

Examples
--------
python spiral_pcb_2024.py                         # 4 phases, 1 loop
python spiral_pcb_2024.py --loops 2               # original 2-loop arrangement
python spiral_pcb_2024.py --loops 1 --steps 400 --out one_loop.kicad_pcb
"""
from __future__ import annotations

import argparse
import json
import math
import os
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path

SOURCE_URL = "https://github.com/Twisted-Fields/induction_encoder/blob/main/spiral_pcb_2024.py"

@dataclass
class Segment:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str
    net: int
    width: float = 0.25

@dataclass
class Via:
    at: tuple[float, float]
    size: float
    drill: float
    net: int

@dataclass
class Circle:
    center: tuple[float, float]
    end: tuple[float, float]
    layer: str = "Edge.Cuts"
    width: float = 0.05

@dataclass
class Config:
    center_x: float = 100.0
    center_y: float = 100.0
    inside_radius: float = 38.0
    outside_radius: float = 51.0
    inside_edge_inset: float = 1.2
    outside_edge_offset: float = 4.0
    phases: int = 4
    loops: int = 1
    steps: int = 200
    rx_width: float = 0.25
    via_size: float = 0.8
    via_drill: float = 0.4
    tx_steps: int = 300
    tx_loops: int = 3
    tx_loop_offset_mm: float = 0.6
    tx_offset_mm: float = 1.1
    tx_extra_tail_mm: float = 2.0
    tx_angle_offset: float = 0.0
    angle_offset_deg: float | None = None

    def validate(self) -> None:
        if self.phases != 4:
            raise ValueError("This routing schedule is defined for exactly 4 phases.")
        if self.loops not in (1, 2):
            raise ValueError("Supported loop settings are 1 (fixed full turn) and 2 (original configuration).")
        if self.steps < 40 or self.steps % 4:
            raise ValueError("steps must be >= 40 and divisible by 4.")
        if self.inside_radius <= 0 or self.outside_radius <= self.inside_radius:
            raise ValueError("Need outside_radius > inside_radius > 0.")
        if min(self.rx_width, self.via_size, self.via_drill) <= 0 or self.via_drill >= self.via_size:
            raise ValueError("Invalid track/via dimensions.")


def point_from_radius(angle: float, radius: float, center_offset_x: float, center_offset_y: float) -> tuple[float, float]:
    # Keep the source script's coordinate convention exactly (its two offsets
    # are equal by default, so the historical x/y naming does not alter output).
    y_value = math.sin(angle) * radius + center_offset_x
    x_value = math.cos(angle) * radius + center_offset_y
    return (x_value, y_value)


def calculate_point(idx: float, steps: int, inside_radius: float, width: float,
                    loopnum: int, loop_angle: float, phasenum: int,
                    phase_angle: float, angle_offset: float,
                    center_offset_x: float, center_offset_y: float) -> tuple[float, float]:
    outside_radius = inside_radius + width
    electrical_angle = (idx / steps) * math.tau
    a = 0.5 * (outside_radius**2 - inside_radius**2)
    b = 0.5 * (outside_radius**2 + inside_radius**2)
    radius = math.sqrt(a * math.sin(electrical_angle) + b)
    mechanical_angle = (loop_angle * (idx / steps) + loopnum * loop_angle
                        + phasenum * phase_angle + angle_offset)
    return point_from_radius(mechanical_angle, radius, center_offset_x, center_offset_y)


def _rx_layer_and_transition_indices(cfg: Config, loopnum: int, phasenum: int, idx: int):
    """Return (layer, should-place-via-at-previous-point) for one RX segment.

    This helper mirrors the upstream index schedule, with one full-turn branch
    for phases 2/3 when loops=1. Kept separate to make seam closure testable.
    """
    steps = cfg.steps
    bottom_layer = phasenum in (0, 2)
    via_here = False
    half = steps // 2

    if phasenum in (0, 1):
        if loopnum == 0:
            if idx < 5 or idx > steps - 4:
                bottom_layer = not bottom_layer
            if idx in (5, steps - 3, half + 5, half - 3):
                via_here = True
            if half + 5 > idx > half - 4:
                bottom_layer = not bottom_layer
        else:  # second half-turn of the original 2-loop design
            if idx < 5:
                bottom_layer = not bottom_layer
            if idx == 5:
                via_here = True
    elif phasenum in (2, 3):
        if cfg.loops == 1:
            # FIX: the one-loop trace is a complete 360-degree revolution.
            # Add the missing start and mid-turn switches for phases 2/3 so
            # their layer state closes across idx=steps -> idx=0 and has the
            # same crossover coverage as phases 0/1, phase-rotated by 180 deg.
            if idx < 5 or idx > steps - 4:
                bottom_layer = not bottom_layer
            if idx in (5, steps - 3, half + 5, half - 3):
                via_here = True
            if half + 5 > idx > half - 4:
                bottom_layer = not bottom_layer
        elif loopnum == 1:
            if half < idx < half + 5:
                bottom_layer = not bottom_layer
            if idx in (half + 5, 5):
                via_here = True
            if idx < 5:
                bottom_layer = not bottom_layer
        else:  # first half-turn of the original 2-loop design
            if idx == steps - 3:
                via_here = True
            if idx > steps - 4:
                bottom_layer = not bottom_layer

    return ("B.Cu" if bottom_layer else "F.Cu"), via_here


def build_geometry(cfg: Config) -> tuple[list[Segment], list[Via], list[Circle], dict]:
    cfg.validate()
    cx, cy = cfg.center_x, cfg.center_y
    width = cfg.outside_radius - cfg.inside_radius
    loops, phases, steps = cfg.loops, cfg.phases, cfg.steps
    loop_angle = math.tau / loops
    phase_angle = loop_angle / phases
    if cfg.angle_offset_deg is None:
        angle_offset = -phase_angle / 2.5 - phase_angle
    else:
        angle_offset = math.radians(cfg.angle_offset_deg)

    # Upstream net assignment: phase 0/2 -> net 2, phase 1/3 -> net 1.
    rx_net_ids = [3, 2, 3, 2]
    tx_net_id = 1
    segments: list[Segment] = []
    vias: list[Via] = []
    last_point: list[tuple[float, float] | None] = [None] * 8
    tab_outer_point: tuple[float, float] | None = None
    half = steps // 2
    quarter = steps // 4

    # ------------------------------ RX coils
    for loopnum in range(loops):
        for phasenum in range(phases):
            skip_next_segment = False
            for idx in range(steps + 1):
                if idx == steps and loopnum != loops - 1:
                    # As in the source, don't double-draw the intermediate seam.
                    continue
                current_point = calculate_point(idx, steps, cfg.inside_radius, width,
                                                loopnum, loop_angle, phasenum,
                                                phase_angle, angle_offset, cx, cy)
                if skip_next_segment:
                    skip_current_segment = True
                    skip_next_segment = False
                else:
                    skip_current_segment = False

                layer, place_transition_via = _rx_layer_and_transition_indices(cfg, loopnum, phasenum, idx)
                if last_point[phasenum] is not None and place_transition_via:
                    vias.append(Via(last_point[phasenum], cfg.via_size, cfg.via_drill, rx_net_ids[phasenum]))

                # Preserve the source's special outward lobe tabs. Phases 0/2
                # require endpoint vias because their normal path is primarily B.Cu.
                if phasenum in (0, 2) and quarter + 1 >= idx > quarter - 2:
                    layer = "F.Cu"
                if phasenum in (0, 2) and idx in (quarter + 1, quarter - 2):
                    tmp_pt = calculate_point(idx, steps, cfg.inside_radius, width,
                                             loopnum, loop_angle, phasenum,
                                             phase_angle, angle_offset, cx, cy)
                    vias.append(Via(tmp_pt, cfg.via_size, cfg.via_drill, rx_net_ids[phasenum]))
                if idx == quarter - 1:
                    # tmp_pt1 equals current_point in the source; its first
                    # Segment is a zero-length primitive. Omit that invalid
                    # geometry while retaining the actual radial tab segment.
                    tmp_pt2 = calculate_point(idx, steps, cfg.inside_radius + 3.0, width,
                                              loopnum, loop_angle, phasenum,
                                              phase_angle, angle_offset, cx, cy)
                    if math.dist(current_point, tmp_pt2) > 1e-9:
                        segments.append(Segment(current_point, tmp_pt2, "F.Cu", rx_net_ids[phasenum], cfg.rx_width))
                    tab_outer_point = tmp_pt2
                    skip_next_segment = True
                if idx == quarter:
                    tmp_pt1 = calculate_point(idx, steps, cfg.inside_radius + 3.0, width,
                                              loopnum, loop_angle, phasenum,
                                              phase_angle, angle_offset, cx, cy)
                    if math.dist(current_point, tmp_pt1) > 1e-9:
                        segments.append(Segment(current_point, tmp_pt1, "F.Cu", rx_net_ids[phasenum], cfg.rx_width))
                    if tab_outer_point is not None and math.dist(tab_outer_point, tmp_pt1) > 1e-9:
                        segments.append(Segment(tab_outer_point, tmp_pt1, "F.Cu", rx_net_ids[phasenum], cfg.rx_width))

                if last_point[phasenum] is not None and not skip_current_segment:
                    if math.dist(last_point[phasenum], current_point) > 1e-9:
                        segments.append(Segment(last_point[phasenum], current_point, layer, rx_net_ids[phasenum], cfg.rx_width))
                last_point[phasenum] = current_point

    # ------------------------------ TX winding (source geometry)
    tx_steps = cfg.tx_steps
    tx_loops = cfg.tx_loops
    loop_offset_mm = cfg.tx_loop_offset_mm
    tx_offset_mm = cfg.tx_offset_mm
    tx_angle_offset = cfg.tx_angle_offset
    tx_extra_tail_mm = cfg.tx_extra_tail_mm
    last_tx_point: tuple[float, float] | None = None
    tail_end_pt: tuple[float, float] | None = None
    for loopnum in range(tx_loops + 1):
        for stepnum in range(tx_steps):
            radius = loopnum * loop_offset_mm + cfg.outside_radius + tx_offset_mm
            angle = stepnum / tx_steps * math.tau + tx_angle_offset
            current_point = point_from_radius(angle, radius, cx, cy)
            if stepnum == 0 and loopnum == 0:
                via_angle = (stepnum + 0.15) / tx_steps * math.tau + tx_angle_offset
                via_point = point_from_radius(via_angle, radius, cx, cy)
                vias.append(Via(via_point, cfg.via_size, cfg.via_drill, tx_net_id))
                tmp_radius = radius + tx_loops * loop_offset_mm + tx_extra_tail_mm
                tail_end_pt = point_from_radius(angle, tmp_radius, cx, cy)
                segments.append(Segment(current_point, tail_end_pt, "F.Cu", tx_net_id, cfg.rx_width))
            if stepnum == 0 and last_tx_point is not None:
                radius_tmp1 = (loopnum - 1) * loop_offset_mm + cfg.outside_radius + tx_offset_mm
                radius_tmp2 = radius - loop_offset_mm / 3.0
                angle_tmp1 = (loopnum * -0.08 - 0.75) / tx_steps * math.tau + tx_angle_offset
                angle_tmp2 = (loopnum * -0.08 - 0.3) / tx_steps * math.tau + tx_angle_offset
                tmp_point1 = point_from_radius(angle_tmp1, radius_tmp1, cx, cy)
                tmp_point2 = point_from_radius(angle_tmp2, radius_tmp2, cx, cy)
                segments.append(Segment(last_tx_point, tmp_point1, "B.Cu", tx_net_id, cfg.rx_width))
                segments.append(Segment(tmp_point1, tmp_point2, "B.Cu", tx_net_id, cfg.rx_width))
                last_tx_point = tmp_point2
            if last_tx_point is not None and math.dist(last_tx_point, current_point) > 1e-9:
                segments.append(Segment(last_tx_point, current_point, "B.Cu", tx_net_id, cfg.rx_width))
            last_tx_point = current_point
            if loopnum == tx_loops:
                assert tail_end_pt is not None
                if math.dist(current_point, tail_end_pt) > 1e-9:
                    segments.append(Segment(current_point, tail_end_pt, "B.Cu", tx_net_id, cfg.rx_width))
                break

    edge_inner = cfg.inside_radius - cfg.inside_edge_inset
    edge_outer = cfg.outside_radius + cfg.outside_edge_offset
    circles = [Circle((cx, cy), (cx, cy + edge_inner)), Circle((cx, cy), (cx, cy + edge_outer))]

    seam_check = {}
    if loops == 1:
        for phasenum in range(phases):
            l_start, _ = _rx_layer_and_transition_indices(cfg, 0, phasenum, 1)
            l_end, _ = _rx_layer_and_transition_indices(cfg, 0, phasenum, steps)
            seam_check[str(phasenum)] = {"start_segment_layer": l_start, "end_segment_layer": l_end,
                                         "closed_layer_state": l_start == l_end}
    meta = {
        "source": SOURCE_URL,
        "settings": asdict(cfg),
        "angle_offset_deg_used": math.degrees(angle_offset),
        "segment_width_mm": cfg.rx_width,
        "segment_count": len(segments),
        "via_count": len(vias),
        "via_count_by_net": {str(n): sum(v.net == n for v in vias) for n in (1, 2, 3)},
        "layer_segment_count": {layer: sum(s.layer == layer for s in segments) for layer in ("F.Cu", "B.Cu")},
        "rx_one_loop_seam_check": seam_check,
        "notes": [
            "The RX phase 2/3 layer schedule changes only when loops=1; loops=2 follows the original schedule.",
            "Zero-length segments from the source tab code are omitted.",
            "Copper width is explicitly 0.25 mm in this standalone exporter.",
            "The original script adds duplicate F.SilkS line art for every copper segment; omitted here to keep fabricated silkscreen clean.",
        ],
    }
    return segments, vias, circles, meta


def _layer_table() -> str:
    entries = [
        '(0 "F.Cu" signal)', '(31 "B.Cu" signal)',
        '(32 "B.Adhes" user)', '(33 "F.Adhes" user)',
        '(34 "B.Paste" user)', '(35 "F.Paste" user)',
        '(36 "B.SilkS" user)', '(37 "F.SilkS" user)',
        '(38 "B.Mask" user)', '(39 "F.Mask" user)',
        '(40 "Dwgs.User" user)', '(41 "Cmts.User" user)',
        '(44 "Edge.Cuts" user)', '(45 "Margin" user)',
        '(46 "B.CrtYd" user)', '(47 "F.CrtYd" user)',
        '(48 "B.Fab" user)', '(49 "F.Fab" user)',
    ]
    return "\n\t\t" + "\n\t\t".join(entries)


def export_kicad(segments: list[Segment], vias: list[Via], circles: list[Circle], out_path: str) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    uid = lambda: str(uuid.uuid4())
    lines = [
        '(kicad_pcb (version 20240108) (generator "spiral_pcb_2024_fixed")',
        '\t(general (thickness 1.6))',
        '\t(paper "User" 200 200)',
        '\t(layers' + _layer_table() + '\n\t)',
        '\t(setup (pad_to_mask_clearance 0))',
        '\t(net 0 "")',
        '\t(net 1 "TX")',
        '\t(net 2 "1")',
        '\t(net 3 "2")',
    ]
    for c in circles:
        lines.append(
            f'\t(gr_circle (center {c.center[0]:.5f} {c.center[1]:.5f}) '
            f'(end {c.end[0]:.5f} {c.end[1]:.5f}) '
            f'(stroke (width {c.width}) (type default)) (fill none) '
            f'(layer "{c.layer}") (uuid "{uid()}"))'
        )
    for s in segments:
        lines.append(
            f'\t(segment (start {s.start[0]:.5f} {s.start[1]:.5f}) '
            f'(end {s.end[0]:.5f} {s.end[1]:.5f}) (width {s.width}) '
            f'(layer "{s.layer}") (net {s.net}) (uuid "{uid()}"))'
        )
    for v in vias:
        lines.append(
            f'\t(via (at {v.at[0]:.5f} {v.at[1]:.5f}) (size {v.size}) '
            f'(drill {v.drill}) (layers "F.Cu" "B.Cu") (net {v.net}) (uuid "{uid()}"))'
        )
    lines.append(')')
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def plot_preview(segments: list[Segment], vias: list[Via], cfg: Config, out_path: str) -> None:
    """Optional visual preview. Matplotlib is only needed when --preview is set."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 9))
    for s in segments:
        col = "#e34a33" if s.layer == "F.Cu" else "#3182bd"
        ax.plot((s.start[0], s.end[0]), (s.start[1], s.end[1]), color=col,
                linewidth=max(0.25, s.width * 2.1), alpha=0.85)
    for v in vias:
        ax.add_patch(plt.Circle(v.at, v.size / 2, edgecolor="#d4a900", facecolor="none", linewidth=0.8))
    ax.add_patch(plt.Circle((cfg.center_x, cfg.center_y), cfg.inside_radius - cfg.inside_edge_inset,
                            edgecolor="#555", facecolor="none", linewidth=0.8))
    ax.add_patch(plt.Circle((cfg.center_x, cfg.center_y), cfg.outside_radius + cfg.outside_edge_offset,
                            edgecolor="#555", facecolor="none", linewidth=0.8))
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(f"4 phases, {cfg.loops} loop(s): F.Cu red, B.Cu blue")
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)")
    ax.grid(True, alpha=0.2)
    ax.set_xlim(cfg.center_x - cfg.outside_radius - 10, cfg.center_x + cfg.outside_radius + 10)
    ax.set_ylim(cfg.center_y - cfg.outside_radius - 10, cfg.center_y + cfg.outside_radius + 10)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fixed 4-phase Twisted-Fields spiral coil generator")
    ap.add_argument("--loops", type=int, choices=(1, 2), default=1,
                    help="1 = fixed full-turn mode (default); 2 = original two half-turn sections")
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--inside-radius", type=float, default=38.0)
    ap.add_argument("--outside-radius", type=float, default=51.0)
    ap.add_argument("--rx-width", type=float, default=0.25)
    ap.add_argument("--angle-offset-deg", type=float, default=None)
    ap.add_argument("--out", default=None, help="Output .kicad_pcb path")
    ap.add_argument("--preview", action="store_true", help="Also write a PNG preview (requires matplotlib)")
    args = ap.parse_args(argv)

    cfg = Config(loops=args.loops, steps=args.steps,
                 inside_radius=args.inside_radius, outside_radius=args.outside_radius,
                 rx_width=args.rx_width, angle_offset_deg=args.angle_offset_deg)
    try:
        segments, vias, circles, meta = build_geometry(cfg)
    except ValueError as e:
        ap.error(str(e))

    out_path = args.out or f"spiral_pcb_2024_{cfg.phases}phase_{cfg.loops}loop.kicad_pcb"
    export_kicad(segments, vias, circles, out_path)
    report_path = str(Path(out_path).with_suffix(".json"))
    meta["output_pcb"] = str(Path(out_path).resolve())
    meta["nonzero_segments"] = sum(math.dist(s.start, s.end) > 1e-9 for s in segments)
    Path(report_path).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if args.preview:
        preview_path = str(Path(out_path).with_suffix(".png"))
        plot_preview(segments, vias, cfg, preview_path)
        print(f"Preview: {preview_path}")
    print(f"Generated: {out_path}")
    print(f"Segments: {len(segments)} | Vias: {len(vias)} | Loop setting: {cfg.loops}")
    print(f"Report: {report_path}")
    if cfg.loops == 1:
        failed = [p for p, c in meta["rx_one_loop_seam_check"].items() if not c["closed_layer_state"]]
        if failed:
            raise RuntimeError(f"One-loop seam layer mismatch on phases: {failed}")
        print("One-loop seam check: PASS for all four phases")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
