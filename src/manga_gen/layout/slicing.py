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
    adjacent_left_skew: float = 0.0  # Left neighbor's right edge skew
    adjacent_right_skew: float = 0.0  # Right neighbor's left edge skew
    adjacent_top_skew: float = 0.0  # Top neighbor's bottom edge skew
    adjacent_bottom_skew: float = 0.0  # Bottom neighbor's top edge skew
    # Position of shared borders (middle of gutter)
    shared_left_x: float | None = None
    shared_right_x: float | None = None
    shared_top_y: float | None = None
    shared_bottom_y: float | None = None
    # Shared border endpoints (for skewed borders)
    # Format: (top_x, top_y, bottom_x, bottom_y) for vertical borders
    #         (left_x, left_y, right_x, right_y) for horizontal borders
    shared_left_endpoints: tuple[float, float, float, float] | None = None
    shared_right_endpoints: tuple[float, float, float, float] | None = None
    shared_top_endpoints: tuple[float, float, float, float] | None = None
    shared_bottom_endpoints: tuple[float, float, float, float] | None = None


class LayoutEngine:
    """Recursive space partitioning layout engine."""

    def __init__(self, page: "Page"):
        self.page = page
        self.panels: list[LayoutedPanel] = []

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
        from ..ast import PanelNode, RowNode, ColNode

        if isinstance(node, PanelNode):
            # Leaf node: record panel position with attributes
            self.panels.append(LayoutedPanel(
                id=node.id,
                rect=rect,
                attrs=node.attrs
            ))

        elif isinstance(node, RowNode):
            # Row: layout children horizontally
            child_gutter = node.gutter if node.gutter is not None else self.page.config.gutter
            self._layout_children(
                node.children,
                rect,
                "horizontal",
                child_gutter
            )

        elif isinstance(node, ColNode):
            # Col: layout children vertically
            child_gutter = node.gutter if node.gutter is not None else self.page.config.gutter
            self._layout_children(
                node.children,
                rect,
                "vertical",
                child_gutter
            )

    def _resolve_shared_borders(self) -> None:
        """Detect shared borders between adjacent panels and disable redundant drawing.

        Rule: For shared borders, only the left/top panel draws the border.
        Panels are considered adjacent if they share the same position on one axis
        and are close (within gutter distance) on the other axis.
        """
        EPSILON = 0.01  # Tolerance for floating point comparison
        max_gutter = 20.0  # Maximum expected gutter size

        for i, panel_a in enumerate(self.panels):
            for panel_b in self.panels[i+1:]:
                ra = panel_a.rect
                rb = panel_b.rect

                # Check if panels are vertically adjacent (left-right)
                # Same Y position and height, close in X direction
                if (abs(ra.y - rb.y) < EPSILON and
                    abs(ra.h - rb.h) < EPSILON):
                    # Check if panel_a is to the left of panel_b
                    gap = rb.x - (ra.x + ra.w)
                    if 0 <= gap < max_gutter:
                        # panel_a's right border and panel_b's left border are shared
                        # Store adjacent skew values for proper border calculation
                        panel_a.adjacent_right_skew = panel_b.attrs.skew_left
                        panel_b.adjacent_left_skew = panel_a.attrs.skew_right
                        # If no skew, only panel_a draws to avoid double lines
                        avg_skew = (panel_a.attrs.skew_right + panel_b.attrs.skew_left) / 2
                        if avg_skew == 0:
                            panel_b.draw_left = False
                        # Shared border is in the middle of the gutter
                        shared_x = ra.x + ra.w + gap / 2
                        panel_a.shared_right_x = shared_x
                        panel_b.shared_left_x = shared_x
                        # Calculate shared border endpoints for skewed borders
                        # Use average of both panels' skew values for parallel borders
                        import math
                        avg_skew = (panel_a.attrs.skew_right + panel_b.attrs.skew_left) / 2
                        if avg_skew != 0:
                            offset = (ra.h / 2) * math.tan(math.radians(avg_skew))
                            # panel_a's right border (at ra.x + ra.w)
                            panel_a_x = ra.x + ra.w
                            panel_a_top_x = panel_a_x + offset
                            panel_a_bottom_x = panel_a_x - offset
                            # panel_b's left border (at rb.x)
                            panel_b_x = rb.x
                            panel_b_top_x = panel_b_x + offset
                            panel_b_bottom_x = panel_b_x - offset
                            top_y = ra.y
                            bottom_y = ra.y + ra.h
                            panel_a.shared_right_endpoints = (panel_a_top_x, top_y, panel_a_bottom_x, bottom_y)
                            panel_b.shared_left_endpoints = (panel_b_top_x, top_y, panel_b_bottom_x, bottom_y)
                    # Check if panel_b is to the left of panel_a
                    gap = ra.x - (rb.x + rb.w)
                    if 0 <= gap < max_gutter:
                        # panel_b's right border and panel_a's left border are shared
                        # Store adjacent skew values
                        panel_b.adjacent_right_skew = panel_a.attrs.skew_left
                        panel_a.adjacent_left_skew = panel_b.attrs.skew_right
                        # If no skew, only panel_b draws to avoid double lines
                        avg_skew = (panel_b.attrs.skew_right + panel_a.attrs.skew_left) / 2
                        if avg_skew == 0:
                            panel_a.draw_left = False
                        # Shared border is in the middle of the gutter
                        shared_x = rb.x + rb.w + gap / 2
                        panel_b.shared_right_x = shared_x
                        panel_a.shared_left_x = shared_x
                        # Calculate shared border endpoints for skewed borders
                        import math
                        avg_skew = (panel_b.attrs.skew_right + panel_a.attrs.skew_left) / 2
                        if avg_skew != 0:
                            offset = (rb.h / 2) * math.tan(math.radians(avg_skew))
                            # panel_b's right border (at rb.x + rb.w)
                            panel_b_x = rb.x + rb.w
                            panel_b_top_x = panel_b_x + offset
                            panel_b_bottom_x = panel_b_x - offset
                            # panel_a's left border (at ra.x)
                            panel_a_x = ra.x
                            panel_a_top_x = panel_a_x + offset
                            panel_a_bottom_x = panel_a_x - offset
                            top_y = rb.y
                            bottom_y = rb.y + rb.h
                            panel_b.shared_right_endpoints = (panel_b_top_x, top_y, panel_b_bottom_x, bottom_y)
                            panel_a.shared_left_endpoints = (panel_a_top_x, top_y, panel_a_bottom_x, bottom_y)

                # Check if panels are horizontally adjacent (top-bottom)
                # Same X position and width, close in Y direction
                if (abs(ra.x - rb.x) < EPSILON and
                    abs(ra.w - rb.w) < EPSILON):
                    # Check if panel_a is above panel_b
                    gap = rb.y - (ra.y + ra.h)
                    if 0 <= gap < max_gutter:
                        # panel_a's bottom border and panel_b's top border are shared
                        # Store adjacent skew values
                        panel_a.adjacent_bottom_skew = panel_b.attrs.skew_top
                        panel_b.adjacent_top_skew = panel_a.attrs.skew_bottom
                        # If no skew on shared border AND both panels have no skew at all,
                        # only panel_a draws to avoid double lines
                        avg_skew = (panel_a.attrs.skew_bottom + panel_b.attrs.skew_top) / 2
                        panel_b_has_any_skew = (panel_b.attrs.skew_left != 0 or panel_b.attrs.skew_right != 0 or
                                                 panel_b.attrs.skew_top != 0 or panel_b.attrs.skew_bottom != 0)
                        if avg_skew == 0 and not panel_b_has_any_skew:
                            panel_b.draw_top = False
                        # Shared border is in the middle of the gutter
                        shared_y = ra.y + ra.h + gap / 2
                        panel_a.shared_bottom_y = shared_y
                        panel_b.shared_top_y = shared_y
                        # Calculate shared border endpoints
                        import math
                        avg_skew = (panel_a.attrs.skew_bottom + panel_b.attrs.skew_top) / 2
                        offset = (ra.w / 2) * math.tan(math.radians(avg_skew)) if avg_skew != 0 else 0
                        # panel_a's bottom border (at ra.y + ra.h)
                        panel_a_y = ra.y + ra.h
                        panel_a_left_y = panel_a_y + offset
                        panel_a_right_y = panel_a_y - offset
                        # panel_b's top border (at rb.y)
                        panel_b_y = rb.y
                        panel_b_left_y = panel_b_y + offset
                        panel_b_right_y = panel_b_y - offset
                        left_x = ra.x
                        right_x = ra.x + ra.w
                        panel_a.shared_bottom_endpoints = (left_x, panel_a_left_y, right_x, panel_a_right_y)
                        panel_b.shared_top_endpoints = (left_x, panel_b_left_y, right_x, panel_b_right_y)
                    # Check if panel_b is above panel_a
                    gap = ra.y - (rb.y + rb.h)
                    if 0 <= gap < max_gutter:
                        # panel_b's bottom border and panel_a's top border are shared
                        # Store adjacent skew values
                        panel_b.adjacent_bottom_skew = panel_a.attrs.skew_top
                        panel_a.adjacent_top_skew = panel_b.attrs.skew_bottom
                        # If no skew on shared border AND both panels have no skew at all,
                        # only panel_b draws to avoid double lines
                        avg_skew = (panel_b.attrs.skew_bottom + panel_a.attrs.skew_top) / 2
                        panel_a_has_any_skew = (panel_a.attrs.skew_left != 0 or panel_a.attrs.skew_right != 0 or
                                                 panel_a.attrs.skew_top != 0 or panel_a.attrs.skew_bottom != 0)
                        if avg_skew == 0 and not panel_a_has_any_skew:
                            panel_a.draw_top = False
                        # Shared border is in the middle of the gutter
                        shared_y = rb.y + rb.h + gap / 2
                        panel_b.shared_bottom_y = shared_y
                        panel_a.shared_top_y = shared_y
                        # Calculate shared border endpoints
                        import math
                        avg_skew = (panel_b.attrs.skew_bottom + panel_a.attrs.skew_top) / 2
                        offset = (rb.w / 2) * math.tan(math.radians(avg_skew)) if avg_skew != 0 else 0
                        # panel_b's bottom border (at rb.y + rb.h)
                        panel_b_y = rb.y + rb.h
                        panel_b_left_y = panel_b_y + offset
                        panel_b_right_y = panel_b_y - offset
                        # panel_a's top border (at ra.y)
                        panel_a_y = ra.y
                        panel_a_left_y = panel_a_y + offset
                        panel_a_right_y = panel_a_y - offset
                        left_x = rb.x
                        right_x = rb.x + rb.w
                        panel_b.shared_bottom_endpoints = (left_x, panel_b_left_y, right_x, panel_b_right_y)
                        panel_a.shared_top_endpoints = (left_x, panel_a_left_y, right_x, panel_a_right_y)
