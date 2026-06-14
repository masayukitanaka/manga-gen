"""Raster (PNG) renderer using CairoSVG."""

import cairosvg


def svg_to_png(svg_string: str, dpi: int = 300) -> bytes:
    """Convert SVG string to PNG bytes.

    Args:
        svg_string: SVG markup
        dpi: Resolution in dots per inch

    Returns:
        PNG image as bytes
    """
    png_bytes = cairosvg.svg2png(
        bytestring=svg_string.encode("utf-8"),
        dpi=dpi,
    )
    return png_bytes  # type: ignore
