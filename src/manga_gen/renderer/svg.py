"""SVG renderer with image and skew support."""

import base64
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..ast import Page
    from ..layout.slicing import LayoutedPanel

from ..layout.slicing import Rect


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

        # Page background
        ET.SubElement(svg, "rect", {
            "x": "0",
            "y": "0",
            "width": str(cfg.width_mm),
            "height": str(cfg.height_mm),
            "fill": cfg.background,
        })

        # Render each panel
        for panel in self.panels:
            self._render_panel(svg, panel)

        # Convert to string
        return ET.tostring(svg, encoding="unicode")

    def _render_panel(self, parent: ET.Element, panel: "LayoutedPanel") -> None:
        """Render a single panel.

        Args:
            parent: Parent SVG element
            panel: Panel to render
        """
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

        # Create group for panel
        g = ET.SubElement(parent, "g", {"id": panel.id})

        # Check if panel has any edge skew (including adjacent panels)
        has_skew = (attrs.skew_left != 0 or attrs.skew_right != 0 or
                    attrs.skew_top != 0 or attrs.skew_bottom != 0 or
                    panel.adjacent_left_skew != 0 or panel.adjacent_right_skew != 0 or
                    panel.adjacent_top_skew != 0 or panel.adjacent_bottom_skew != 0)

        if has_skew:
            import math

            # Calculate offsets for each corner based on edge skews
            # When a vertical edge rotates, its endpoints shift horizontally
            # When a horizontal edge rotates, its endpoints shift vertically

            # For shared borders, use the adjacent panel's skew value
            # This ensures continuous borders across adjacent panels

            # Effective skew for each edge (considering adjacent panels)
            # For shared borders, use the average of both panels' skew values
            # to ensure continuous, parallel borders
            if panel.adjacent_left_skew != 0:
                left_skew = (attrs.skew_left + panel.adjacent_left_skew) / 2
            else:
                left_skew = attrs.skew_left

            if panel.adjacent_right_skew != 0:
                right_skew = (attrs.skew_right + panel.adjacent_right_skew) / 2
            else:
                right_skew = attrs.skew_right

            if panel.adjacent_top_skew != 0:
                top_skew = (attrs.skew_top + panel.adjacent_top_skew) / 2
            else:
                top_skew = attrs.skew_top

            if panel.adjacent_bottom_skew != 0:
                bottom_skew = (attrs.skew_bottom + panel.adjacent_bottom_skew) / 2
            else:
                bottom_skew = attrs.skew_bottom

            # Left edge rotation offset (affects top-left and bottom-left x)
            left_offset_x = (r.h / 2) * math.tan(math.radians(left_skew)) if left_skew != 0 else 0
            # Right edge rotation offset (affects top-right and bottom-right x)
            right_offset_x = (r.h / 2) * math.tan(math.radians(right_skew)) if right_skew != 0 else 0
            # Top edge rotation offset (affects top-left and top-right y)
            top_offset_y = (r.w / 2) * math.tan(math.radians(top_skew)) if top_skew != 0 else 0
            # Bottom edge rotation offset (affects bottom-left and bottom-right y)
            bottom_offset_y = (r.w / 2) * math.tan(math.radians(bottom_skew)) if bottom_skew != 0 else 0

            # Calculate corner positions after skew
            # Use shared border positions when available (for adjacent panels)
            left_edge_x = panel.shared_left_x if panel.shared_left_x is not None else r.x
            right_edge_x = panel.shared_right_x if panel.shared_right_x is not None else r.x + r.w
            top_edge_y = panel.shared_top_y if panel.shared_top_y is not None else r.y
            bottom_edge_y = panel.shared_bottom_y if panel.shared_bottom_y is not None else r.y + r.h

            # Calculate corner positions
            # Each corner is determined by the intersection of two edges
            # Use shared endpoints only for the specific edge, not for the corner

            # Top-left corner (intersection of left and top edges)
            if panel.shared_left_endpoints:
                tl_x = panel.shared_left_endpoints[0]
            else:
                tl_x = left_edge_x - left_offset_x

            if panel.shared_top_endpoints:
                tl_y = panel.shared_top_endpoints[1]
            else:
                tl_y = top_edge_y - top_offset_y

            # Top-right corner (intersection of right and top edges)
            if panel.shared_right_endpoints:
                tr_x = panel.shared_right_endpoints[0]
            else:
                tr_x = right_edge_x + right_offset_x

            if panel.shared_top_endpoints:
                tr_y = panel.shared_top_endpoints[3]
            else:
                tr_y = top_edge_y + top_offset_y

            # Bottom-right corner (intersection of right and bottom edges)
            if panel.shared_right_endpoints:
                br_x = panel.shared_right_endpoints[2]
            else:
                br_x = right_edge_x - right_offset_x

            if panel.shared_bottom_endpoints:
                br_y = panel.shared_bottom_endpoints[3]
            else:
                br_y = bottom_edge_y + bottom_offset_y

            # Bottom-left corner (intersection of left and bottom edges)
            if panel.shared_left_endpoints:
                bl_x = panel.shared_left_endpoints[2]
            else:
                bl_x = left_edge_x + left_offset_x

            if panel.shared_bottom_endpoints:
                bl_y = panel.shared_bottom_endpoints[1]
            else:
                bl_y = bottom_edge_y - bottom_offset_y

            # Render background as polygon with adjusted corners
            points = f"{tl_x},{tl_y} {tr_x},{tr_y} {br_x},{br_y} {bl_x},{bl_y}"
            ET.SubElement(g, "polygon", {
                "points": points,
                "fill": attrs.background,
                "stroke": "none",
            })

            # Render borders individually (only if not shared with adjacent panel)
            # Use individual border settings if specified, otherwise use general border
            border_left_width = attrs.border_left if attrs.border_left is not None else attrs.border
            border_right_width = attrs.border_right if attrs.border_right is not None else attrs.border
            border_top_width = attrs.border_top if attrs.border_top is not None else attrs.border
            border_bottom_width = attrs.border_bottom if attrs.border_bottom is not None else attrs.border

            # Left border
            if panel.draw_left and border_left_width > 0:
                # Use polygon corner positions for the border
                ET.SubElement(g, "line", {
                    "x1": str(tl_x),
                    "y1": str(tl_y),
                    "x2": str(bl_x),
                    "y2": str(bl_y),
                    "stroke": attrs.border_color,
                    "stroke-width": str(border_left_width),
                })

            # Right border
            if panel.draw_right and border_right_width > 0:
                # Use polygon corner positions for the border
                ET.SubElement(g, "line", {
                    "x1": str(tr_x),
                    "y1": str(tr_y),
                    "x2": str(br_x),
                    "y2": str(br_y),
                    "stroke": attrs.border_color,
                    "stroke-width": str(border_right_width),
                })

            # Top border
            if panel.draw_top and border_top_width > 0:
                # Use polygon corner positions for the border
                ET.SubElement(g, "line", {
                    "x1": str(tl_x),
                    "y1": str(tl_y),
                    "x2": str(tr_x),
                    "y2": str(tr_y),
                    "stroke": attrs.border_color,
                    "stroke-width": str(border_top_width),
                })

            # Bottom border
            if panel.draw_bottom and border_bottom_width > 0:
                # Use polygon corner positions for the border
                ET.SubElement(g, "line", {
                    "x1": str(bl_x),
                    "y1": str(bl_y),
                    "x2": str(br_x),
                    "y2": str(br_y),
                    "stroke": attrs.border_color,
                    "stroke-width": str(border_bottom_width),
                })
        else:
            # Render as rectangle (no skew)
            # Check if individual border control is needed
            has_individual_borders = (attrs.border_top is not None or
                                     attrs.border_bottom is not None or
                                     attrs.border_left is not None or
                                     attrs.border_right is not None)

            if has_individual_borders:
                # Render background without stroke
                ET.SubElement(g, "rect", {
                    "x": str(r.x),
                    "y": str(r.y),
                    "width": str(r.w),
                    "height": str(r.h),
                    "fill": attrs.background,
                    "stroke": "none",
                })

                # Render individual borders
                border_left_width = attrs.border_left if attrs.border_left is not None else attrs.border
                border_right_width = attrs.border_right if attrs.border_right is not None else attrs.border
                border_top_width = attrs.border_top if attrs.border_top is not None else attrs.border
                border_bottom_width = attrs.border_bottom if attrs.border_bottom is not None else attrs.border

                if border_left_width > 0:
                    ET.SubElement(g, "line", {
                        "x1": str(r.x), "y1": str(r.y),
                        "x2": str(r.x), "y2": str(r.y + r.h),
                        "stroke": attrs.border_color,
                        "stroke-width": str(border_left_width),
                    })

                if border_right_width > 0:
                    ET.SubElement(g, "line", {
                        "x1": str(r.x + r.w), "y1": str(r.y),
                        "x2": str(r.x + r.w), "y2": str(r.y + r.h),
                        "stroke": attrs.border_color,
                        "stroke-width": str(border_right_width),
                    })

                if border_top_width > 0:
                    ET.SubElement(g, "line", {
                        "x1": str(r.x), "y1": str(r.y),
                        "x2": str(r.x + r.w), "y2": str(r.y),
                        "stroke": attrs.border_color,
                        "stroke-width": str(border_top_width),
                    })

                if border_bottom_width > 0:
                    ET.SubElement(g, "line", {
                        "x1": str(r.x), "y1": str(r.y + r.h),
                        "x2": str(r.x + r.w), "y2": str(r.y + r.h),
                        "stroke": attrs.border_color,
                        "stroke-width": str(border_bottom_width),
                    })
            else:
                # Render as simple rectangle with uniform border
                ET.SubElement(g, "rect", {
                    "x": str(r.x),
                    "y": str(r.y),
                    "width": str(r.w),
                    "height": str(r.h),
                    "fill": attrs.background,
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
                "fill": "#000000",
            })
        else:
            # Horizontal text
            text_elem = ET.SubElement(parent, "text", {
                "x": str(r.x + 10),
                "y": str(r.y + 15),
                "font-size": "8",
                "fill": "#000000",
            })

        text_elem.text = attrs.text
