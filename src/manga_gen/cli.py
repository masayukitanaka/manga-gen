"""Command-line interface for MangaDSL compiler."""

import click
from pathlib import Path
from .parser import parse
from .layout.slicing import LayoutEngine
from .renderer.svg import SVGRenderer
from .renderer.raster import svg_to_png
from .errors import MangaDSLError


@click.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", help="Output file (.png or .svg)")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["png", "svg", "auto"]),
    default="auto",
    help="Output format (default: auto-detect from extension)"
)
@click.option(
    "--dpi",
    type=int,
    default=None,
    help="DPI for PNG output (default: use DSL dpi setting or 300)"
)
def main(input: str, output: str | None, fmt: str, dpi: int | None) -> None:
    """MangaDSL compiler - convert .manga files to images.

    INPUT: Path to .manga source file
    """
    try:
        # Read source file
        source_path = Path(input)
        source = source_path.read_text(encoding="utf-8")

        click.echo(f"Parsing {input}...")

        # Parse DSL
        page = parse(source)

        click.echo("Computing layout...")

        # Compute layout
        engine = LayoutEngine(page)
        panels = engine.layout()

        click.echo(f"Layouted {len(panels)} panel(s)")

        # Determine output file
        if output is None:
            output_path = source_path.with_suffix(".png")
        else:
            output_path = Path(output)

        # Auto-detect format from extension
        if fmt == "auto":
            fmt = "svg" if output_path.suffix.lower() == ".svg" else "png"

        # Render
        click.echo(f"Rendering {fmt.upper()}...")

        # Create renderer with source directory for image resolution
        renderer = SVGRenderer(page, panels, source_dir=source_path.parent)

        if fmt == "svg":
            svg_str = renderer.render()
            output_path.write_text(svg_str, encoding="utf-8")
        else:
            svg_str = renderer.render()
            if page.config.size_unit == "px" and dpi is None:
                # px-specified size: render at exact pixel dimensions
                MM_PER_INCH = 25.4
                PX_PER_INCH = 96.0
                w_px = round(page.config.width_mm / (MM_PER_INCH / PX_PER_INCH))
                h_px = round(page.config.height_mm / (MM_PER_INCH / PX_PER_INCH))
                png_bytes = svg_to_png(svg_str, output_width=w_px, output_height=h_px)
            else:
                actual_dpi = dpi if dpi is not None else page.config.dpi
                png_bytes = svg_to_png(svg_str, dpi=actual_dpi)
            output_path.write_bytes(png_bytes)

        click.echo(f"✓ Output: {output_path}")

    except MangaDSLError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        raise


if __name__ == "__main__":
    main()
