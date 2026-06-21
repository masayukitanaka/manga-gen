"""Layout engine using recursive space partitioning with advanced features."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..ast import Page, RowNode, ColNode, PanelNode, LayoutNode, Length, PanelAttrs

from ..errors import LayoutError


@dataclass
class Rect:
    """A rectangle in mm units."""
    x: float
    y: float
    w: float
    h: float


@dataclass
class SkewLine:
    """A skewed straight line for a shared vertical border.

    The line passes through (base_x, mid_y) at the given angle.
    Both the left panel's right edge and the right panel's left edge have
    their own base_x (panel boundary), but share mid_y and skew_angle so
    they are exactly parallel.

    x_at(y) computes the X position of *this panel's edge* at height y.
    """
    base_x: float      # X of this panel's own boundary at mid_y
    mid_y: float       # Shared reference Y (midpoint of the taller panel)
    skew_angle: float  # degrees — shared between both sides

    def x_at(self, y: float) -> float:
        import math
        if self.skew_angle == 0.0:
            return self.base_x
        return self.base_x + (y - self.mid_y) * math.tan(math.radians(self.skew_angle))


@dataclass
class SkewHLine:
    """A skewed horizontal border line.

    Passes through (mid_x, base_y) at the given angle.
    y_at(x) computes the Y position at horizontal position x.
    Analogous to SkewLine but for horizontal borders (top/bottom).
    """
    base_y: float      # Y of the gutter centre at mid_x
    mid_x: float       # X reference (midpoint of panel width)
    skew_angle: float  # degrees — positive = right side lower

    def y_at(self, x: float) -> float:
        import math
        if self.skew_angle == 0.0:
            return self.base_y
        return self.base_y + (x - self.mid_x) * math.tan(math.radians(self.skew_angle))


@dataclass
class LayoutedPanel:
    """A panel with computed layout (absolute coordinates)."""
    id: str
    rect: Rect
    attrs: "PanelAttrs"
    draw_left: bool = True
    draw_right: bool = True
    draw_top: bool = True
    draw_bottom: bool = True
    # Skew values from adjacent panels for shared borders
    adjacent_left_skew: float = 0.0
    adjacent_right_skew: float = 0.0
    adjacent_top_skew: float = 0.0
    adjacent_bottom_skew: float = 0.0
    # Position of shared borders (middle of gutter) — used for polygon base
    shared_left_x: float | None = None
    shared_right_x: float | None = None
    shared_top_y: float | None = None
    shared_bottom_y: float | None = None
    # Skew line descriptors for vertical shared borders.
    shared_left_skewline: "SkewLine | None" = None
    shared_right_skewline: "SkewLine | None" = None
    # Y range over which the left/right skewline is valid (the panel overlap span).
    shared_left_skewline_y: "tuple[float, float] | None" = None
    shared_right_skewline_y: "tuple[float, float] | None" = None
    # Skew line descriptors for horizontal shared borders (top/bottom).
    shared_top_skewline: "SkewHLine | None" = None
    shared_bottom_skewline: "SkewHLine | None" = None
    # For horizontal shared borders (top/bottom), keep simple endpoint tuples.
    # Format: (left_x, left_y, right_x, right_y)
    shared_top_endpoints: tuple[float, float, float, float] | None = None
    shared_bottom_endpoints: tuple[float, float, float, float] | None = None


class LayoutEngine:
    """Recursive space partitioning layout engine."""

    def __init__(self, page: "Page"):
        self.page = page
        self.panels: list[LayoutedPanel] = []
        # Inherited skew values from ancestor containers
        self._inherited_skew: dict[str, float] = {
            "skew_left": 0.0,
            "skew_right": 0.0,
            "skew_top": 0.0,
            "skew_bottom": 0.0,
        }

    def layout(self) -> list[LayoutedPanel]:
        """Compute layout for all panels.

        Returns:
            List of layouted panels with absolute coordinates
        """
        # Compute inner rectangle (after padding)
        inner = Rect(
            x=self.page.config.padding,
            y=self.page.config.padding,
            w=self.page.config.width_mm - 2 * self.page.config.padding,
            h=self.page.config.height_mm - 2 * self.page.config.padding,
        )

        # Layout root children as vertical stack (rows)
        self._layout_children(
            self.page.children,
            inner,
            axis="vertical",
            gutter=self.page.config.gutter
        )

        # Detect shared borders and disable redundant drawing
        self._resolve_shared_borders()

        return self.panels

    def _layout_children(
        self,
        nodes: list["LayoutNode"],
        bounds: Rect,
        axis: str,  # "vertical" (rows) or "horizontal" (cols)
        gutter: float
    ) -> None:
        """Layout a list of nodes within the given bounds.

        Args:
            nodes: List of layout nodes to arrange
            bounds: Available rectangle
            axis: "vertical" for row stacking, "horizontal" for column arrangement
            gutter: Gap between nodes
            parent_skew: Inherited skew angle from parent
        """
        if not nodes:
            return

        # Compute sizes for each node
        sizes = self._compute_sizes(nodes, bounds, axis, gutter)

        # Assign rectangles and recurse
        # For RTL (right-to-left), horizontal layout starts from the right
        if axis == "horizontal" and self.page.config.direction == "rtl":
            offset = bounds.w  # Start from right edge
            for node, size in zip(nodes, sizes):
                offset -= size  # Move left by panel width
                child_rect = Rect(bounds.x + offset, bounds.y, size, bounds.h)
                offset -= gutter  # Move left by gutter
                self._layout_node(node, child_rect)
        else:
            # LTR (left-to-right) or vertical layout
            offset = 0.0
            for node, size in zip(nodes, sizes):
                # Create child rectangle
                if axis == "vertical":
                    child_rect = Rect(bounds.x, bounds.y + offset, bounds.w, size)
                else:  # horizontal
                    child_rect = Rect(bounds.x + offset, bounds.y, size, bounds.h)

                offset += size + gutter

                # Layout this node
                self._layout_node(node, child_rect)

    def _compute_sizes(
        self,
        nodes: list["LayoutNode"],
        bounds: Rect,
        axis: str,
        gutter: float
    ) -> list[float]:
        """Compute size for each node along the main axis.

        Args:
            nodes: List of nodes
            bounds: Available space
            axis: "vertical" or "horizontal"
            gutter: Gap size

        Returns:
            List of sizes (one per node)

        Raises:
            LayoutError: If size constraints cannot be satisfied
        """
        # Total available space along main axis
        total_gutter = gutter * (len(nodes) - 1)
        available = (bounds.h if axis == "vertical" else bounds.w) - total_gutter

        # Categorize nodes by size type
        fixed_total = 0.0
        percent_total = 0.0
        auto_count = 0

        for node in nodes:
            size_spec = self._get_size_spec(node, axis)

            if size_spec is None:
                auto_count += 1
            elif size_spec.unit == "mm":
                fixed_total += size_spec.value
            elif size_spec.unit == "%":
                percent_total += size_spec.value
            else:  # auto
                auto_count += 1

        # Validate percentage total
        if percent_total > 100:
            raise LayoutError(
                f"Percentage total ({percent_total}%) exceeds 100%"
            )

        # Compute remaining space after fixed and percentage allocations
        percent_space = available * (percent_total / 100)
        remaining = available - fixed_total - percent_space

        if remaining < 0:
            raise LayoutError(
                f"Size specifications exceed available space: "
                f"fixed={fixed_total}mm, percent={percent_space}mm, "
                f"available={available}mm"
            )

        auto_size = remaining / auto_count if auto_count > 0 else 0

        # Compute final sizes
        sizes = []
        for node in nodes:
            size_spec = self._get_size_spec(node, axis)

            if size_spec is None or size_spec.unit == "auto":
                sizes.append(auto_size)
            elif size_spec.unit == "mm":
                sizes.append(size_spec.value)
            elif size_spec.unit == "%":
                sizes.append(available * size_spec.value / 100)

        return sizes

    def _get_size_spec(self, node: "LayoutNode", axis: str) -> Optional["Length"]:
        """Get size specification for a node.

        Args:
            node: Layout node
            axis: "vertical" or "horizontal"

        Returns:
            Length specification or None for auto
        """
        from ..ast import RowNode, ColNode

        if isinstance(node, RowNode):
            return node.height
        elif isinstance(node, ColNode):
            return node.width
        else:  # PanelNode
            return None  # Treat as auto

    def _layout_node(self, node: "LayoutNode", rect: Rect) -> None:
        """Layout a single node.

        Args:
            node: Node to layout
            rect: Assigned rectangle
        """
        from ..ast import PanelNode, RowNode, ColNode, PanelAttrs

        if isinstance(node, PanelNode):
            # Apply inherited skew to panels that don't set their own value
            inh = self._inherited_skew
            attrs = node.attrs
            merged = PanelAttrs(
                **{
                    **attrs.model_dump(),
                    "skew_left":   attrs.skew_left   if attrs.skew_left   != 0.0 else inh["skew_left"],
                    "skew_right":  attrs.skew_right  if attrs.skew_right  != 0.0 else inh["skew_right"],
                    "skew_top":    attrs.skew_top    if attrs.skew_top    != 0.0 else inh["skew_top"],
                    "skew_bottom": attrs.skew_bottom if attrs.skew_bottom != 0.0 else inh["skew_bottom"],
                }
            )
            self.panels.append(LayoutedPanel(
                id=node.id,
                rect=rect,
                attrs=merged
            ))

        elif isinstance(node, RowNode):
            # Row: layout children horizontally
            child_gutter = node.gutter if node.gutter is not None else self.page.config.gutter
            inner = Rect(
                x=rect.x + node.margin_left,
                y=rect.y + node.margin_top,
                w=rect.w - node.margin_left - node.margin_right,
                h=rect.h - node.margin_top - node.margin_bottom,
            )
            prev = self._push_inherited_skew(node)
            self._layout_children(node.children, inner, "horizontal", child_gutter)
            self._inherited_skew = prev

        elif isinstance(node, ColNode):
            # Col: layout children vertically
            child_gutter = node.gutter if node.gutter is not None else self.page.config.gutter
            inner = Rect(
                x=rect.x + node.margin_left,
                y=rect.y + node.margin_top,
                w=rect.w - node.margin_left - node.margin_right,
                h=rect.h - node.margin_top - node.margin_bottom,
            )
            prev = self._push_inherited_skew(node)
            self._layout_children(node.children, inner, "vertical", child_gutter)
            self._inherited_skew = prev

    def _push_inherited_skew(self, node: "RowNode | ColNode") -> dict[str, float]:
        """Merge container skew with current inherited values; return previous state."""
        prev = dict(self._inherited_skew)
        new = dict(self._inherited_skew)
        for key in ("skew_left", "skew_right", "skew_top", "skew_bottom"):
            val = getattr(node, key, None)
            if val is not None:
                new[key] = val
        self._inherited_skew = new
        return prev

    def _resolve_shared_borders(self) -> None:
        """Detect shared borders between adjacent panels and disable redundant drawing.

        Panels are considered left-right adjacent when they overlap on the Y axis and
        are close (within gutter distance) on the X axis.  This handles the case where
        a tall panel on the left shares its right edge with multiple shorter panels on
        the right (each covering only a portion of that edge).

        Top-bottom adjacency still requires the same X and width (panels in the same
        column are always the same width).
        """
        import math
        EPSILON = 0.01
        max_gutter = 20.0

        for i, panel_a in enumerate(self.panels):
            for panel_b in self.panels[i+1:]:
                ra = panel_a.rect
                rb = panel_b.rect

                # ── Left-right adjacency ───────────────────────────────────────
                # Panels overlap on Y if their Y ranges intersect with meaningful length.
                overlap_top = max(ra.y, rb.y)
                overlap_bottom = min(ra.y + ra.h, rb.y + rb.h)
                y_overlap = overlap_bottom - overlap_top

                if y_overlap > EPSILON:
                    # panel_a is to the left of panel_b
                    gap = rb.x - (ra.x + ra.w)
                    if 0 <= gap < max_gutter:
                        self._link_lr(panel_a, panel_b, ra, rb, gap,
                                      overlap_top, overlap_bottom)

                    # panel_b is to the left of panel_a
                    gap = ra.x - (rb.x + rb.w)
                    if 0 <= gap < max_gutter:
                        self._link_lr(panel_b, panel_a, rb, ra, gap,
                                      overlap_top, overlap_bottom)

                # ── Top-bottom adjacency ───────────────────────────────────────
                # Panels are top-bottom adjacent when their X ranges overlap
                # (handles both same-width columns and wide-panel-over-multiple-columns).
                x_overlap = min(ra.x + ra.w, rb.x + rb.w) - max(ra.x, rb.x)
                if x_overlap > EPSILON:
                    # panel_a is above panel_b
                    gap = rb.y - (ra.y + ra.h)
                    if 0 <= gap < max_gutter:
                        self._link_tb(panel_a, panel_b, ra, rb, gap)

                    # panel_b is above panel_a
                    gap = ra.y - (rb.y + rb.h)
                    if 0 <= gap < max_gutter:
                        self._link_tb(panel_b, panel_a, rb, ra, gap)

        # ── Unify mid_y for collinear skewlines ───────────────────────────────
        # When the same diagonal edge spans multiple row-pairs (e.g. a col with
        # skew_right and two child rows), each pair gets its own mid_y, producing
        # two different lines instead of one continuous diagonal.  Fix by grouping
        # all skewlines that share the same base_x and skew_angle and setting them
        # all to the mid_y of the first (topmost) segment.
        self._unify_skewline_mid_y()

        # ── Adjust vertical skewline_y when a slanted horizontal gutter crosses it ──
        # When a bottom panel has both a shared_top_skewline (slanted horizontal gutter
        # from the panel above) and a shared vertical skewline on its right or left,
        # the vertical skewline's draw range must start at the intersection of those two
        # lines so the corner closes cleanly (no triangular gap).
        self._adjust_skewline_y_for_slanted_top()

    def _adjust_skewline_y_for_slanted_top(self) -> None:
        """For panels with both a slanted top gutter and a vertical skewline,
        set the vertical skewline's top Y to the intersection of the two lines."""
        import math

        def _intersect(hsl: "SkewHLine", vsl: "SkewLine"):
            tan_h = math.tan(math.radians(hsl.skew_angle))
            tan_v = math.tan(math.radians(vsl.skew_angle))
            denom = 1 - tan_h * tan_v
            if abs(denom) < 1e-9:
                return None
            xi = (vsl.base_x + (hsl.base_y - vsl.mid_y) * tan_v
                  - hsl.mid_x * tan_h * tan_v) / denom
            yi = hsl.base_y + (xi - hsl.mid_x) * tan_h
            return yi

        for p in self.panels:
            # Adjust bottom panel's vertical skewline top to the intersection
            # with this panel's own top border (base_y = rb.y).
            hsl_top = p.shared_top_skewline
            if hsl_top is not None:
                if p.shared_right_skewline and p.shared_right_skewline_y:
                    yi = _intersect(hsl_top, p.shared_right_skewline)
                    if yi is not None:
                        old_top, old_bot = p.shared_right_skewline_y
                        p.shared_right_skewline_y = (yi, old_bot)
                if p.shared_left_skewline and p.shared_left_skewline_y:
                    yi = _intersect(hsl_top, p.shared_left_skewline)
                    if yi is not None:
                        old_top, old_bot = p.shared_left_skewline_y
                        p.shared_left_skewline_y = (yi, old_bot)

            # Adjust top panel's vertical skewline bottom to the intersection
            # with its own bottom border (base_y = rt.y+rt.h, gutter top side).
            hsl_bot = p.shared_bottom_skewline
            if hsl_bot is not None:
                if p.shared_right_skewline and p.shared_right_skewline_y:
                    yi = _intersect(hsl_bot, p.shared_right_skewline)
                    if yi is not None:
                        old_top, old_bot = p.shared_right_skewline_y
                        p.shared_right_skewline_y = (old_top, yi)
                if p.shared_left_skewline and p.shared_left_skewline_y:
                    yi = _intersect(hsl_bot, p.shared_left_skewline)
                    if yi is not None:
                        old_top, old_bot = p.shared_left_skewline_y
                        p.shared_left_skewline_y = (old_top, yi)

    def _unify_skewline_mid_y(self) -> None:
        """Ensure collinear skewlines (same base_x + angle) share one mid_y."""
        from collections import defaultdict

        # Collect (side, panel) keyed by (base_x, angle)
        right_groups: dict[tuple, list] = defaultdict(list)
        left_groups:  dict[tuple, list] = defaultdict(list)

        for p in self.panels:
            if p.shared_right_skewline:
                sl = p.shared_right_skewline
                right_groups[(sl.base_x, sl.skew_angle)].append(p)
            if p.shared_left_skewline:
                sl = p.shared_left_skewline
                left_groups[(sl.base_x, sl.skew_angle)].append(p)

        for key, panels in right_groups.items():
            if len(panels) < 2:
                continue
            # Sort by panel top Y; use the first panel's mid_y for all
            panels.sort(key=lambda p: p.rect.y)
            canonical_mid_y = panels[0].shared_right_skewline.mid_y
            for p in panels[1:]:
                sl = p.shared_right_skewline
                p.shared_right_skewline = SkewLine(sl.base_x, canonical_mid_y, sl.skew_angle)

        for key, panels in left_groups.items():
            if len(panels) < 2:
                continue
            panels.sort(key=lambda p: p.rect.y)
            canonical_mid_y = panels[0].shared_left_skewline.mid_y
            for p in panels[1:]:
                sl = p.shared_left_skewline
                p.shared_left_skewline = SkewLine(sl.base_x, canonical_mid_y, sl.skew_angle)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _link_lr(
        self,
        left: "LayoutedPanel",
        right: "LayoutedPanel",
        rl: "Rect",
        rr: "Rect",
        gap: float,
        overlap_top: float,
        overlap_bottom: float,
    ) -> None:
        """Register left-right shared border between `left` and `right`."""
        left.adjacent_right_skew = right.attrs.skew_left
        right.adjacent_left_skew = left.attrs.skew_right

        skew_l = left.attrs.skew_right
        skew_r = right.attrs.skew_left
        # Use the non-zero value; if both are non-zero, average them for smooth join
        if skew_l != 0 and skew_r != 0:
            shared_skew = (skew_l + skew_r) / 2
        else:
            shared_skew = skew_l + skew_r  # one is 0, so this equals the non-zero one

        shared_x = rl.x + rl.w + gap / 2
        left.shared_right_x = rl.x + rl.w   # left panel's own right boundary
        right.shared_left_x = rr.x           # right panel's own left boundary

        # Effective border widths for determining who draws the line
        left_right_bw  = left.attrs.border_right  if left.attrs.border_right  is not None else left.attrs.border
        right_left_bw  = right.attrs.border_left  if right.attrs.border_left  is not None else right.attrs.border
        left_draws  = left_right_bw  > 0
        right_draws = right_left_bw  > 0

        # Each panel draws its own skewline at its own rect boundary.
        # left panel's right edge at rl.x+rl.w, right panel's left edge at rr.x.
        # Both lines are parallel (same angle, same mid_y) but offset by the gutter width,
        # forming the two visible edges of the skewed gutter.
        left_border_x  = rl.x + rl.w   # left panel's right rect edge
        right_border_x = rr.x           # right panel's left rect edge

        effective_skew = skew_l if skew_l != 0 else skew_r

        if effective_skew != 0:
            if left_draws:
                prev_sl = left.shared_right_skewline
                if prev_sl is not None and prev_sl.base_x == left_border_x and prev_sl.skew_angle == effective_skew:
                    # Reuse the existing skewline's mid_y so all segments of this
                    # edge form one continuous diagonal line across multiple row pairs.
                    ref_mid_y_left = prev_sl.mid_y
                else:
                    ref_mid_y_left = (rl.y + rl.h / 2) if rl.h >= rr.h else (rr.y + rr.h / 2)
                left.shared_right_skewline = SkewLine(left_border_x, ref_mid_y_left, effective_skew)
                prev_y = left.shared_right_skewline_y
                left.shared_right_skewline_y = (
                    min(prev_y[0], overlap_top) if prev_y else overlap_top,
                    max(prev_y[1], overlap_bottom) if prev_y else overlap_bottom,
                )
            if right_draws:
                prev_sl = right.shared_left_skewline
                if prev_sl is not None and prev_sl.base_x == right_border_x and prev_sl.skew_angle == effective_skew:
                    ref_mid_y_right = prev_sl.mid_y
                else:
                    ref_mid_y_right = (rl.y + rl.h / 2) if rl.h >= rr.h else (rr.y + rr.h / 2)
                right.shared_left_skewline = SkewLine(right_border_x, ref_mid_y_right, effective_skew)
                prev_y = right.shared_left_skewline_y
                new_top = overlap_top
                new_bottom = overlap_bottom
                if prev_y:
                    # Bridge the gutter gap between the previous neighbor's range and
                    # this neighbor's range so the diagonal is continuous.
                    new_top = min(prev_y[0], overlap_top)
                    new_bottom = max(prev_y[1], overlap_bottom)
                elif rl.y < rr.y:
                    # The left panel starts above this right panel — extend the range
                    # upward through the gutter so the diagonal meets the horizontal border.
                    new_top = min(rr.y - gap, overlap_top)
                right.shared_left_skewline_y = (new_top, new_bottom)

    def _link_tb(
        self,
        top: "LayoutedPanel",
        bottom: "LayoutedPanel",
        rt: "Rect",
        rb: "Rect",
        gap: float,
    ) -> None:
        """Register top-bottom shared border between `top` and `bottom`."""
        import math

        top.adjacent_bottom_skew = bottom.attrs.skew_top
        bottom.adjacent_top_skew = top.attrs.skew_bottom

        skew_t = top.attrs.skew_bottom
        skew_b = bottom.attrs.skew_top
        if skew_t != 0 and skew_b != 0:
            shared_skew = (skew_t + skew_b) / 2
        else:
            shared_skew = skew_t + skew_b  # one is 0

        # Top panel owns the shared border line.
        # Suppress the bottom panel's top border whenever the top panel's X span
        # fully covers the bottom panel's X span — the top panel already draws
        # the full slanted line, so the bottom panel must not redraw its portion.
        EPSILON2 = 0.01
        top_covers_bottom = (rt.x <= rb.x + EPSILON2) and (rt.x + rt.w >= rb.x + rb.w - EPSILON2)
        # For slanted gutters (shared_skew != 0) the top panel's bottom border and
        # the bottom panel's top border lie on different parallel lines separated by
        # the gutter width — both must be drawn. Only suppress for flat gutters where
        # both panels would draw the exact same line.
        if top_covers_bottom and shared_skew == 0:
            bottom.draw_top = False

        shared_y = rt.y + rt.h + gap / 2
        top.shared_bottom_y = shared_y
        bottom.shared_top_y = shared_y

        offset = (rt.w / 2) * math.tan(math.radians(shared_skew)) if shared_skew != 0 else 0
        left_x = rt.x
        right_x = rt.x + rt.w

        if shared_skew != 0:
            mid_x = rt.x + rt.w / 2
            # Top panel polygon: bottom edge evaluated at rt.y+rt.h (top side of gutter)
            top.shared_bottom_skewline = SkewHLine(rt.y + rt.h, mid_x, shared_skew)
            # Bottom panel polygon: top edge evaluated at rb.y (bottom side of gutter)
            bottom.shared_top_skewline = SkewHLine(rb.y, mid_x, shared_skew)
            # Store the top panel's border skewline on the bottom panel so that
            # _adjust_skewline_y_for_slanted_top can compute the correct intersection
            # with vertical skewlines (needs base_y=rt.y+rt.h, not rb.y).
            bottom._top_border_skewline = SkewHLine(rt.y + rt.h, mid_x, shared_skew)

        # Border lines: top panel uses its own full-width endpoints.
        top.shared_bottom_endpoints = (
            left_x, rt.y + rt.h - offset,
            right_x, rt.y + rt.h + offset,
        )
        bot_left_x = rb.x
        bot_right_x = rb.x + rb.w
        if shared_skew != 0:
            # Bottom panel's top border lies on the gutter-bottom line (base_y=rb.y),
            # parallel to the top panel's bottom border (base_y=rt.y+rt.h).
            sl_bot = SkewHLine(rb.y, rt.x + rt.w / 2, shared_skew)
            bot_left_y = sl_bot.y_at(bot_left_x)
            bot_right_y = sl_bot.y_at(bot_right_x)

            # Extend the top panel's vertical skewline bottom to meet the bottom
            # panel's top border (base_y=rb.y) so the diagonal corner closes cleanly.
            # This must happen here (before _adjust_skewline_y_for_slanted_top) so
            # the gutter-bottom line is used rather than the gutter-top line.
            def _intersect_vsl(hsl, vsl):
                tan_h = math.tan(math.radians(hsl.skew_angle))
                tan_v = math.tan(math.radians(vsl.skew_angle))
                denom = 1 - tan_h * tan_v
                if abs(denom) < 1e-9:
                    return None
                xi = (vsl.base_x + (hsl.base_y - vsl.mid_y) * tan_v
                      - hsl.mid_x * tan_h * tan_v) / denom
                yi = hsl.base_y + (xi - hsl.mid_x) * tan_h
                return yi

        else:
            bot_left_y = rb.y
            bot_right_y = rb.y
        bottom.shared_top_endpoints = (
            bot_left_x, bot_left_y,
            bot_right_x, bot_right_y,
        )
