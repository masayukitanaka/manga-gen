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
    # The line runs the full panel height; border segments are clipped per adjacency.
    shared_left_skewline: "SkewLine | None" = None
    shared_right_skewline: "SkewLine | None" = None
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
                # Panels in the same column share the same x and width.
                if (abs(ra.x - rb.x) < EPSILON and
                        abs(ra.w - rb.w) < EPSILON):
                    # panel_a is above panel_b
                    gap = rb.y - (ra.y + ra.h)
                    if 0 <= gap < max_gutter:
                        self._link_tb(panel_a, panel_b, ra, rb, gap)

                    # panel_b is above panel_a
                    gap = ra.y - (rb.y + rb.h)
                    if 0 <= gap < max_gutter:
                        self._link_tb(panel_b, panel_a, rb, ra, gap)

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
        left.shared_right_x = shared_x
        right.shared_left_x = shared_x

        # Decide which side owns the shared border line.
        # When the left panel has skew_right (skew_l != 0), it draws the line.
        # When only the right panel has skew_left, its polygon edge IS the visual border.
        ref_mid_y = (rl.y + rl.h / 2) if rl.h >= rr.h else (rr.y + rr.h / 2)

        # Effective border widths for determining who draws the line
        left_right_bw  = left.attrs.border_right  if left.attrs.border_right  is not None else left.attrs.border
        right_left_bw  = right.attrs.border_left  if right.attrs.border_left  is not None else right.attrs.border
        left_draws  = left_right_bw  > 0
        right_draws = right_left_bw  > 0

        # Use the gutter centre as the single reference x for both polygon corners.
        # This ensures the owning panel's border line and the non-owning panel's
        # polygon edge are evaluated at the same x, so they meet exactly.
        border_x = shared_x  # gutter centre

        if skew_l != 0:
            # Left panel owns the shared border line.
            right.draw_left = False
            if left_draws:
                left.shared_right_skewline  = SkewLine(border_x, ref_mid_y, skew_l)
                right.shared_left_skewline  = SkewLine(border_x, ref_mid_y, skew_l)
        else:
            # Only right panel has skew — its polygon left edge is the visual border.
            left.draw_right = False
            if right_draws:
                right.shared_left_skewline  = SkewLine(border_x, ref_mid_y, skew_r)
                left.shared_right_skewline  = SkewLine(border_x, ref_mid_y, skew_r)

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

        # Top panel always owns the shared border line; bottom panel suppresses its top.
        bottom.draw_top = False

        shared_y = rt.y + rt.h + gap / 2
        top.shared_bottom_y = shared_y
        bottom.shared_top_y = shared_y

        offset = (rt.w / 2) * math.tan(math.radians(shared_skew)) if shared_skew != 0 else 0
        left_x = rt.x
        right_x = rt.x + rt.w

        # Convention matches polygon corners: left end is raised (−offset), right end lowered (+offset)
        top.shared_bottom_endpoints = (
            left_x, shared_y - offset,
            right_x, shared_y + offset,
        )
        bottom.shared_top_endpoints = (
            left_x, shared_y - offset,
            right_x, shared_y + offset,
        )
