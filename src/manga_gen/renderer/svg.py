"""SVG renderer with image and skew support."""

import base64
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..ast import Page
    from ..layout.slicing import LayoutedPanel

from ..layout.slicing import Rect


def _clip_line_to_rect(
    x1: float, y1: float, x2: float, y2: float,
    xmin: float, ymin: float, xmax: float, ymax: float,
) -> tuple[float, float, float, float] | None:
    """Cohen-Sutherland line clipping to axis-aligned rectangle.

    Returns clipped (x1,y1,x2,y2) or None if segment is entirely outside.
    """
    INSIDE, LEFT, RIGHT, BOTTOM, TOP = 0, 1, 2, 4, 8

    def code(x: float, y: float) -> int:
        c = INSIDE
        if x < xmin: c |= LEFT
        elif x > xmax: c |= RIGHT
        if y < ymin: c |= TOP
        elif y > ymax: c |= BOTTOM
        return c

    c1, c2 = code(x1, y1), code(x2, y2)

    while True:
        if not (c1 | c2):
            return x1, y1, x2, y2
        if c1 & c2:
            return None
        c = c1 if c1 else c2
        dx = x2 - x1
        dy = y2 - y1
        if c & BOTTOM:
            x = x1 + dx * (ymax - y1) / dy if dy else x1
            y = ymax
        elif c & TOP:
            x = x1 + dx * (ymin - y1) / dy if dy else x1
            y = ymin
        elif c & RIGHT:
            y = y1 + dy * (xmax - x1) / dx if dx else y1
            x = xmax
        else:
            y = y1 + dy * (xmin - x1) / dx if dx else y1
            x = xmin
        if c == c1:
            x1, y1, c1 = x, y, code(x, y)
        else:
            x2, y2, c2 = x, y, code(x, y)


def _clip_polygon_to_rect(
    pts: list[tuple[float, float]],
    x_min: float, y_min: float, x_max: float, y_max: float,
) -> list[tuple[float, float]]:
    """Clip a convex polygon to an axis-aligned rectangle (Sutherland-Hodgman)."""
    def _intersect(p1: tuple, p2: tuple, a: tuple, b: tuple) -> tuple[float, float]:
        x1, y1 = p1; x2, y2 = p2; x3, y3 = a; x4, y4 = b
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-12:
            return ((x1 + x2) / 2, (y1 + y2) / 2)
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))

    def _clip_edge(poly: list, a: tuple, b: tuple, inside) -> list:
        if not poly:
            return []
        out = []
        prev = poly[-1]
        for cur in poly:
            if inside(cur):
                if not inside(prev):
                    out.append(_intersect(prev, cur, a, b))
                out.append(cur)
            elif inside(prev):
                out.append(_intersect(prev, cur, a, b))
            prev = cur
        return out

    poly = list(pts)
    poly = _clip_edge(poly, (x_min, y_min), (x_min, y_max), lambda p: p[0] >= x_min)
    poly = _clip_edge(poly, (x_max, y_min), (x_max, y_max), lambda p: p[0] <= x_max)
    poly = _clip_edge(poly, (x_min, y_min), (x_max, y_min), lambda p: p[1] >= y_min)
    poly = _clip_edge(poly, (x_min, y_max), (x_max, y_max), lambda p: p[1] <= y_max)
    return poly


def _panel_fill_polygon(
    tl_x: float, tl_y: float,
    tr_x: float, tr_y: float,
    br_x: float, br_y: float,
    bl_x: float, bl_y: float,
    x_min: float, y_min: float, x_max: float, y_max: float,
) -> list[tuple[float, float]]:
    """Clip the panel trapezoid to its bounding rect using Sutherland-Hodgman."""
    quad = [(tl_x, tl_y), (tr_x, tr_y), (br_x, br_y), (bl_x, bl_y)]
    return _clip_polygon_to_rect(quad, x_min, y_min, x_max, y_max)


class SVGRenderer:
    """Renders layouted panels to SVG with advanced features."""

    def __init__(self, page: "Page", panels: list["LayoutedPanel"], source_dir: Optional[Path] = None):
        self.page = page
        self.panels = panels
        self.source_dir = source_dir or Path.cwd()

    def render(self) -> str:
        """Generate SVG string.

        Returns:
            SVG markup as string
        """
        cfg = self.page.config

        if cfg.size_unit == "px":
            # px-specified: SVG viewport = original px, layout coords (mm) scaled up via viewBox
            # viewBox in mm units so all panel coords (mm) work as-is
            MM_PER_INCH = 25.4
            PX_PER_INCH = 96.0
            w_px = round(cfg.width_mm / (MM_PER_INCH / PX_PER_INCH))
            h_px = round(cfg.height_mm / (MM_PER_INCH / PX_PER_INCH))
            svg = ET.Element("svg", {
                "xmlns": "http://www.w3.org/2000/svg",
                "xmlns:xlink": "http://www.w3.org/1999/xlink",
                "width": str(w_px),
                "height": str(h_px),
                "viewBox": f"0 0 {cfg.width_mm} {cfg.height_mm}",
            })
        else:
            svg = ET.Element("svg", {
                "xmlns": "http://www.w3.org/2000/svg",
                "xmlns:xlink": "http://www.w3.org/1999/xlink",
                "width": f"{cfg.width_mm}mm",
                "height": f"{cfg.height_mm}mm",
                "viewBox": f"0 0 {cfg.width_mm} {cfg.height_mm}",
            })

        # Page background: gutter_color fills the entire page (padding + gutters).
        # Panel backgrounds painted on top cover the panel areas, leaving gutter_color
        # visible in the padding margins and gutter gaps between panels.
        ET.SubElement(svg, "rect", {
            "x": "0",
            "y": "0",
            "width": str(cfg.width_mm),
            "height": str(cfg.height_mm),
            "fill": cfg.gutter_color,
        })

        # ClipPath definitions for panels with skewed borders
        defs = ET.SubElement(svg, "defs")

        # Two-pass rendering: backgrounds first, then borders on top.
        # This ensures no panel's white background covers another panel's border line.
        bg_group = ET.SubElement(svg, "g", {"id": "backgrounds"})
        border_group = ET.SubElement(svg, "g", {"id": "borders"})
        for panel in self.panels:
            self._render_panel(bg_group, border_group, panel, defs)

        # Convert to string
        return ET.tostring(svg, encoding="unicode")

    def _render_panel(self, bg_parent: ET.Element, border_parent: ET.Element, panel: "LayoutedPanel", defs: ET.Element | None = None) -> None:
        """Render a single panel: background into bg_parent, borders into border_parent."""
        r = panel.rect
        attrs = panel.attrs

        # Apply offset to panel rect (for dynamic overlapping effects)
        # Negative offset = expand (bleed out), Positive offset = shrink
        offset_rect = Rect(
            x=r.x - attrs.offset_left,
            y=r.y - attrs.offset_top,
            w=r.w + attrs.offset_left + attrs.offset_right,
            h=r.h + attrs.offset_top + attrs.offset_bottom
        )
        # Use offset_rect for rendering
        r = offset_rect

        # Background group (drawn first, before all borders)
        g = ET.SubElement(bg_parent, "g", {"id": panel.id})
        # Border group (drawn last, on top of all backgrounds)
        gb = ET.SubElement(border_parent, "g", {"id": f"{panel.id}_borders"})

        # Check if panel has any edge skew (including adjacent panels)
        has_skew = (attrs.skew_left != 0 or attrs.skew_right != 0 or
                    attrs.skew_top != 0 or attrs.skew_bottom != 0 or
                    panel.adjacent_left_skew != 0 or panel.adjacent_right_skew != 0 or
                    panel.adjacent_top_skew != 0 or panel.adjacent_bottom_skew != 0)

        if has_skew:
            import math
            from ..layout.slicing import SkewLine, SkewHLine

            # ── Effective skew per edge ───────────────────────────────────────
            # When both sides specify a skew, average them; otherwise use the non-zero one.
            def _eff(own: float, adj: float) -> float:
                if own != 0 and adj != 0:
                    return (own + adj) / 2
                return own + adj  # one is 0

            left_skew   = _eff(attrs.skew_left,   panel.adjacent_left_skew)
            right_skew  = _eff(attrs.skew_right,  panel.adjacent_right_skew)
            top_skew    = _eff(attrs.skew_top,    panel.adjacent_top_skew)
            bottom_skew = _eff(attrs.skew_bottom, panel.adjacent_bottom_skew)

            # ── Edge base positions ───────────────────────────────────────────
            # Left/right: use gutter centre x (shared_left/right_x) when adjacent.
            # Top/bottom: use gutter centre y (shared_top/bottom_y) for both the
            #   polygon corners and the border lines so slanted edges meet cleanly.
            left_base_x   = panel.shared_left_x   if panel.shared_left_x   is not None else r.x
            right_base_x  = panel.shared_right_x  if panel.shared_right_x  is not None else r.x + r.w
            top_edge_y    = panel.shared_top_y    if panel.shared_top_y    is not None else r.y
            bottom_edge_y = panel.shared_bottom_y if panel.shared_bottom_y is not None else r.y + r.h

            # Skew offsets
            top_offset_y    = (r.w / 2) * math.tan(math.radians(top_skew))    if top_skew    != 0 else 0
            bottom_offset_y = (r.w / 2) * math.tan(math.radians(bottom_skew)) if bottom_skew != 0 else 0
            own_left_offset  = (r.h / 2) * math.tan(math.radians(attrs.skew_left))  if attrs.skew_left  != 0 else 0
            own_right_offset = (r.h / 2) * math.tan(math.radians(attrs.skew_right)) if attrs.skew_right != 0 else 0

            # ── Polygon corners ───────────────────────────────────────────────
            # Left/right X: use shared skewline evaluated at the panel's own top/bottom
            # (r.y, r.y+r.h) — not at gutter centre — so the polygon stays inside
            # the horizontal gutter gap and doesn't bleed into the neighbour's space.
            if panel.shared_left_skewline:
                tl_x = panel.shared_left_skewline.x_at(r.y)
                bl_x = panel.shared_left_skewline.x_at(r.y + r.h)
            elif panel.shared_left_x is not None:
                tl_x = bl_x = left_base_x
            else:
                tl_x = left_base_x - own_left_offset
                bl_x = left_base_x + own_left_offset

            if panel.shared_right_skewline:
                tr_x = panel.shared_right_skewline.x_at(r.y)
                br_x = panel.shared_right_skewline.x_at(r.y + r.h)
            elif panel.shared_right_x is not None:
                tr_x = br_x = right_base_x
            else:
                tr_x = right_base_x + own_right_offset
                br_x = right_base_x - own_right_offset

            # Top/bottom Y: use SkewHLine when available so both panels reference
            # the same gutter-centre line, preserving the visible gutter gap.
            if panel.shared_top_skewline:
                tl_y = panel.shared_top_skewline.y_at(tl_x)
                tr_y = panel.shared_top_skewline.y_at(tr_x)
            else:
                tl_y = r.y - top_offset_y
                tr_y = r.y + top_offset_y

            if panel.shared_bottom_skewline:
                bl_y = panel.shared_bottom_skewline.y_at(bl_x)
                br_y = panel.shared_bottom_skewline.y_at(br_x)
            else:
                br_y = r.y + r.h + bottom_offset_y
                bl_y = r.y + r.h - bottom_offset_y

            # ── Background: fill the clipped panel trapezoid ─────────────────
            # The trapezoid corners (tl/tr/br/bl) may extend outside the panel's
            # rect when the skew is steep.  Clip to rect so the fill never bleeds
            # into the gutter or the neighbour's space.
            poly_pts = _panel_fill_polygon(
                tl_x, tl_y, tr_x, tr_y, br_x, br_y, bl_x, bl_y,
                r.x, r.y, r.x + r.w, r.y + r.h,
            )
            if poly_pts:
                points_str = " ".join(f"{x},{y}" for x, y in poly_pts)
                ET.SubElement(g, "polygon", {
                    "points": points_str,
                    "fill": attrs.background, "stroke": "none",
                })

            # ── Border lines ──────────────────────────────────────────────────
            border_left_width   = attrs.border_left   if attrs.border_left   is not None else attrs.border
            border_right_width  = attrs.border_right  if attrs.border_right  is not None else attrs.border
            border_top_width    = attrs.border_top    if attrs.border_top    is not None else attrs.border
            border_bottom_width = attrs.border_bottom if attrs.border_bottom is not None else attrs.border

            # Left/right skewlines must be clipped to the panel rect so they don't
            # spill outside. Top/bottom slanted lines span the full panel width and
            # are drawn without a clipPath so they are never cut short.
            if defs is not None:
                clip_id = f"clip_{panel.id}"
                cp = ET.SubElement(defs, "clipPath", {"id": clip_id})
                ET.SubElement(cp, "rect", {
                    "x": str(r.x), "y": str(r.y),
                    "width": str(r.w), "height": str(r.h),
                })
                gb.set("clip-path", f"url(#{clip_id})")

            def _line(parent, x1, y1, x2, y2, width):
                ET.SubElement(parent, "line", {
                    "x1": str(x1), "y1": str(y1),
                    "x2": str(x2), "y2": str(y2),
                    "stroke": attrs.border_color,
                    "stroke-width": str(width),
                })

            # Left/right borders.
            # The Y extent of each vertical edge must meet the slanted top/bottom borders
            # exactly where they cross the left (or right) side of the panel.
            # Vertical border (left/right edge) Y extent.
            # Default: panel rect top/bottom, adjusted by shared slanted top/bottom endpoints.
            if panel.shared_top_endpoints:
                _tx1, _ty1, _tx2, _ty2 = panel.shared_top_endpoints
                # For a slanted top gutter the left/right Y values differ.
                # When there's a vertical skewline, the skewline itself defines the edge —
                # use r.y so the vertical border starts at the panel rect top.
                # When there's no vertical skewline but the top gutter is slanted,
                # use the endpoint Y so the vertical border meets the slanted line.
                if panel.shared_left_skewline:
                    left_top_y = r.y
                elif panel.shared_top_skewline:
                    left_top_y = panel.shared_top_skewline.y_at(r.x)
                else:
                    left_top_y = r.y
                if panel.shared_right_skewline:
                    right_top_y = r.y
                elif panel.shared_top_skewline:
                    right_top_y = panel.shared_top_skewline.y_at(r.x + r.w)
                else:
                    right_top_y = r.y
            else:
                left_top_y = right_top_y = r.y

            if panel.shared_bottom_endpoints:
                _bx1, _by1, _bx2, _by2 = panel.shared_bottom_endpoints
                # Same reasoning for bottom.
                if panel.shared_left_skewline:
                    left_bottom_y = r.y + r.h
                elif panel.shared_bottom_skewline:
                    left_bottom_y = panel.shared_bottom_skewline.y_at(r.x)
                else:
                    left_bottom_y = r.y + r.h
                if panel.shared_right_skewline:
                    right_bottom_y = r.y + r.h
                elif panel.shared_bottom_skewline:
                    right_bottom_y = panel.shared_bottom_skewline.y_at(r.x + r.w)
                else:
                    right_bottom_y = r.y + r.h
            else:
                left_bottom_y = right_bottom_y = r.y + r.h


            if panel.draw_left and border_left_width > 0:
                if panel.shared_left_skewline:
                    sl = panel.shared_left_skewline
                    y1, y2 = panel.shared_left_skewline_y if panel.shared_left_skewline_y else (r.y, r.y + r.h)
                    # Clamp top to panel rect: don't draw above r.y (wedge gap prevention).
                    y1 = max(y1, r.y)
                    # Bottom always ends at offset rect bottom (handles both positive
                    # offset_bottom=shrink and negative=expand correctly).
                    y2 = r.y + r.h
                    x1_sl, x2_sl = sl.x_at(y1), sl.x_at(y2)
                    _line(border_parent, x1_sl, y1, x2_sl, y2, border_left_width)
                else:
                    # Draw to border_parent so slanted top/bottom endpoint trimming
                    # is not clipped by the panel's clipPath rect.
                    _line(border_parent, r.x, left_top_y, r.x, left_bottom_y, border_left_width)

            if panel.draw_right and border_right_width > 0:
                if panel.shared_right_skewline:
                    sl = panel.shared_right_skewline
                    y1, y2 = panel.shared_right_skewline_y if panel.shared_right_skewline_y else (r.y, r.y + r.h)
                    # Clamp top to panel rect: don't draw above r.y (wedge gap prevention).
                    y1 = max(y1, r.y)
                    # Bottom always ends at offset rect bottom.
                    y2 = r.y + r.h
                    x1_sl, x2_sl = sl.x_at(y1), sl.x_at(y2)
                    _line(border_parent, x1_sl, y1, x2_sl, y2, border_right_width)
                else:
                    # Draw to border_parent so slanted top/bottom endpoint trimming
                    # is not clipped by the panel's clipPath rect.
                    _line(border_parent, r.x + r.w, right_top_y, r.x + r.w, right_bottom_y, border_right_width)

            # Top/bottom: slanted lines drawn without clipPath so the full diagonal
            # is always visible across the entire panel width.
            # When a vertical skewline is shared on the left or right, adjust the
            # draw_top=False is set by _link_tb to suppress double-drawing of flat shared
            # borders. Override when a vertical skewline is present: the skewline trims
            # the top border's start X, making it unique to this panel.
            needs_top = panel.draw_top or (
                border_top_width > 0 and
                (panel.shared_left_skewline or panel.shared_right_skewline) and
                panel.shared_top_endpoints is not None
            )
            if needs_top and border_top_width > 0:
                if panel.shared_top_endpoints:
                    tx1, ty1, tx2, ty2 = panel.shared_top_endpoints
                else:
                    tx1, ty1, tx2, ty2 = tl_x, tl_y, tr_x, tr_y
                if panel.shared_left_skewline:
                    tx1 = panel.shared_left_skewline.x_at(r.y)
                    ty1 = r.y
                else:
                    # No skewline: use the endpoint Y from shared_top_endpoints (preserves slope).
                    pass  # ty1 already set from shared_top_endpoints above
                if panel.shared_right_skewline:
                    tx2 = panel.shared_right_skewline.x_at(r.y)
                    ty2 = r.y
                else:
                    pass  # ty2 already set from shared_top_endpoints above
                _line(border_parent, tx1, ty1, tx2, ty2, border_top_width)

            if panel.draw_bottom and border_bottom_width > 0:
                if panel.shared_bottom_endpoints:
                    bx1, by1, bx2, by2 = panel.shared_bottom_endpoints
                else:
                    bx1, by1, bx2, by2 = bl_x, bl_y, br_x, br_y
                if panel.shared_left_skewline:
                    sl_y_end = (panel.shared_left_skewline_y[1]
                                if panel.shared_left_skewline_y else by1)
                    sl_y_end = max(sl_y_end, r.y + r.h)  # respect offset_bottom
                    if panel.shared_bottom_skewline:
                        # Slanted horizontal gutter with vertical skewline on left:
                        # the left corner must snap to the skewline end so the border
                        # closes cleanly (no gap between skewline end and bottom-left corner).
                        by1_clamped = sl_y_end
                    else:
                        # No horizontal skew: bottom border must meet the vertical left
                        # edge exactly at r.y+r.h.
                        by1_clamped = max(min(by1, sl_y_end), r.y + r.h)
                    bx1 = panel.shared_left_skewline.x_at(by1_clamped)
                    by1 = by1_clamped
                else:
                    if panel.shared_bottom_endpoints:
                        # No left skewline: use shared_bottom_endpoints directly so a
                        # slanted bottom gutter (skew_bottom/skew_top) is drawn correctly.
                        pass  # by1 already correct from shared_bottom_endpoints
                    else:
                        by1 = r.y + r.h
                if panel.shared_right_skewline:
                    sl_y_end = (panel.shared_right_skewline_y[1]
                                if panel.shared_right_skewline_y else by2)
                    sl_y_end = max(sl_y_end, r.y + r.h)
                    if panel.shared_bottom_skewline:
                        by2_clamped = sl_y_end
                    else:
                        by2_clamped = max(min(by2, sl_y_end), r.y + r.h)
                    bx2 = panel.shared_right_skewline.x_at(by2_clamped)
                    by2 = by2_clamped
                else:
                    if panel.shared_bottom_endpoints:
                        pass  # by2 already correct from shared_bottom_endpoints
                    else:
                        by2 = r.y + r.h
                _line(border_parent, bx1, by1, bx2, by2, border_bottom_width)
        else:
            # Render as rectangle (no skew)
            # Check if individual border control is needed
            has_individual_borders = (attrs.border_top is not None or
                                     attrs.border_bottom is not None or
                                     attrs.border_left is not None or
                                     attrs.border_right is not None)

            if has_individual_borders:
                ET.SubElement(g, "rect", {
                    "x": str(r.x), "y": str(r.y),
                    "width": str(r.w), "height": str(r.h),
                    "fill": attrs.background, "stroke": "none",
                })

                border_left_width = attrs.border_left if attrs.border_left is not None else attrs.border
                border_right_width = attrs.border_right if attrs.border_right is not None else attrs.border
                border_top_width = attrs.border_top if attrs.border_top is not None else attrs.border
                border_bottom_width = attrs.border_bottom if attrs.border_bottom is not None else attrs.border

                if border_left_width > 0:
                    ET.SubElement(gb, "line", {
                        "x1": str(r.x), "y1": str(r.y),
                        "x2": str(r.x), "y2": str(r.y + r.h),
                        "stroke": attrs.border_color,
                        "stroke-width": str(border_left_width),
                    })
                if border_right_width > 0:
                    ET.SubElement(gb, "line", {
                        "x1": str(r.x + r.w), "y1": str(r.y),
                        "x2": str(r.x + r.w), "y2": str(r.y + r.h),
                        "stroke": attrs.border_color,
                        "stroke-width": str(border_right_width),
                    })
                if border_top_width > 0:
                    ET.SubElement(gb, "line", {
                        "x1": str(r.x), "y1": str(r.y),
                        "x2": str(r.x + r.w), "y2": str(r.y),
                        "stroke": attrs.border_color,
                        "stroke-width": str(border_top_width),
                    })
                if border_bottom_width > 0:
                    ET.SubElement(gb, "line", {
                        "x1": str(r.x), "y1": str(r.y + r.h),
                        "x2": str(r.x + r.w), "y2": str(r.y + r.h),
                        "stroke": attrs.border_color,
                        "stroke-width": str(border_bottom_width),
                    })
            else:
                # Split rect into background fill + border line for two-pass ordering
                ET.SubElement(g, "rect", {
                    "x": str(r.x), "y": str(r.y),
                    "width": str(r.w), "height": str(r.h),
                    "fill": attrs.background, "stroke": "none",
                })
                if attrs.border > 0:
                    ET.SubElement(gb, "rect", {
                        "x": str(r.x), "y": str(r.y),
                        "width": str(r.w), "height": str(r.h),
                        "fill": "none",
                        "stroke": attrs.border_color,
                        "stroke-width": str(attrs.border),
                    })

        # Render image if specified
        if attrs.image:
            self._render_image(g, panel)

        # Render text if specified
        if attrs.text:
            self._render_text(g, panel)

        if attrs.label is not None:
            ET.SubElement(g, "text", {
                "x": str(r.x + r.w / 2),
                "y": str(r.y + r.h / 2),
                "text-anchor": "middle",
                "dominant-baseline": "middle",
                "font-size": "4",
                "font-family": "Hiragino Sans, Hiragino Kaku Gothic Pro, sans-serif",
                "fill": "#999999",
            }).text = attrs.label if attrs.label else panel.id

    def _render_image(self, parent: ET.Element, panel: "LayoutedPanel") -> None:
        """Render image within panel.

        Args:
            parent: Parent group element
            panel: Panel with image
        """
        r = panel.rect
        attrs = panel.attrs

        if not attrs.image:
            return

        # Resolve image path
        image_path = self.source_dir / attrs.image

        if not image_path.exists():
            # Image not found - show placeholder
            ET.SubElement(parent, "rect", {
                "x": str(r.x),
                "y": str(r.y),
                "width": str(r.w),
                "height": str(r.h),
                "fill": "#cccccc",
                "opacity": "0.3",
            })
            ET.SubElement(parent, "text", {
                "x": str(r.x + r.w / 2),
                "y": str(r.y + r.h / 2),
                "text-anchor": "middle",
                "dominant-baseline": "middle",
                "font-size": "3",
                "font-family": "Hiragino Sans, Hiragino Kaku Gothic Pro, sans-serif",
                "fill": "#666666",
            }).text = f"Image not found: {attrs.image}"
            return

        # Read and encode image
        try:
            image_data = image_path.read_bytes()
            b64_data = base64.b64encode(image_data).decode('utf-8')

            # Determine MIME type
            ext = image_path.suffix.lower()
            mime_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.svg': 'image/svg+xml',
            }
            mime = mime_types.get(ext, 'image/png')

            # Map image_fit to preserveAspectRatio
            aspect_ratio_map = {
                'cover': 'xMidYMid slice',
                'contain': 'xMidYMid meet',
                'fill': 'none',
            }
            aspect_ratio = aspect_ratio_map.get(attrs.image_fit, 'xMidYMid slice')

            # Embed image
            ET.SubElement(parent, "image", {
                "x": str(r.x),
                "y": str(r.y),
                "width": str(r.w),
                "height": str(r.h),
                "href": f"data:{mime};base64,{b64_data}",
                "preserveAspectRatio": aspect_ratio,
            })
        except Exception as e:
            # Error reading image - show error message
            ET.SubElement(parent, "text", {
                "x": str(r.x + r.w / 2),
                "y": str(r.y + r.h / 2),
                "text-anchor": "middle",
                "dominant-baseline": "middle",
                "font-size": "3",
                "font-family": "Hiragino Sans, Hiragino Kaku Gothic Pro, sans-serif",
                "fill": "#ff0000",
            }).text = f"Error: {str(e)}"

    def _render_text(self, parent: ET.Element, panel: "LayoutedPanel") -> None:
        """Render text within panel.

        Args:
            parent: Parent group element
            panel: Panel with text
        """
        r = panel.rect
        attrs = panel.attrs

        if not attrs.text:
            return

        # Calculate text position based on direction
        if attrs.text_direction == "vertical":
            # Vertical text (right-to-left, top-to-bottom)
            text_elem = ET.SubElement(parent, "text", {
                "x": str(r.x + r.w - 10),
                "y": str(r.y + 10),
                "writing-mode": "vertical-rl",
                "font-size": "8",
                "font-family": "Hiragino Sans, Hiragino Kaku Gothic Pro, sans-serif",
                "fill": "#000000",
            })
        else:
            # Horizontal text
            text_elem = ET.SubElement(parent, "text", {
                "x": str(r.x + 10),
                "y": str(r.y + 15),
                "font-size": "8",
                "font-family": "Hiragino Sans, Hiragino Kaku Gothic Pro, sans-serif",
                "fill": "#000000",
            })

        text_elem.text = attrs.text
