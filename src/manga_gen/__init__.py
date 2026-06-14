"""MangaDSL - Manga panel layout DSL compiler."""

__version__ = "1.0.0"

from .parser import parse
from .layout.slicing import LayoutEngine
from .renderer.svg import SVGRenderer
from .renderer.raster import svg_to_png

__all__ = ["parse", "LayoutEngine", "SVGRenderer", "svg_to_png"]
