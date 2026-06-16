"""Raster (PNG) renderer using CairoSVG."""

import cairosvg
from typing import Optional


def svg_to_png(svg_string: str, dpi: int = 300,
               output_width: Optional[int] = None,
               output_height: Optional[int] = None) -> bytes:
    """Convert SVG string to PNG bytes.

    When output_width/output_height are given, the image is rendered at exactly
    that pixel size regardless of DPI (used for px-unit page sizes).
    """
    if output_width is not None or output_height is not None:
        png_bytes = cairosvg.svg2png(
            bytestring=svg_string.encode("utf-8"),
            output_width=output_width,
            output_height=output_height,
        )
    else:
        png_bytes = cairosvg.svg2png(
            bytestring=svg_string.encode("utf-8"),
            dpi=dpi,
        )
    return png_bytes  # type: ignore
