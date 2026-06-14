# MangaGen

A DSL (Domain Specific Language) and compiler for declaratively describing manga panel layouts.

## Features

- 🎨 **Declarative Layout**: Define panel layouts intuitively with row/col/panel syntax
- 🖼️ **Image Support**: Place PNG, JPEG, GIF, and SVG images within panels
- ⚡ **Dynamic Effects**: Create movement by skewing panel borders
- 📐 **Flexible Sizing**: Combine %, mm, and auto for free-form layouts
- 🎯 **Multiple Output Formats**: SVG and PNG (with high-resolution support)
- 📏 **Standard Sizes**: A3, A4, B4, B5 + custom sizes

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Create a .manga file

```manga
// simple.manga
page {
  size: B5
  gutter: 6

  row height: 60% {
    panel hero {
      image: "images/hero.png"
      image_fit: cover
    }
  }

  row {
    col { panel detail1 }
    col { panel detail2 }
  }
}
```

### 2. Compile

```bash
# PNG output (default)
manga-gen simple.manga

# SVG output
manga-gen simple.manga -o output.svg

# High-resolution PNG
manga-gen simple.manga -o print.png --dpi 600
```

## Documentation

- [DSL Language Reference](docs/DSL.md) - Syntax and usage examples
- [Specification](docs/SPEC.md) - Implementation details

## Examples

See the [examples/](examples/) directory for practical examples:

```bash
# Run an example
manga-gen examples/yonkoma.manga -o yonkoma.png
```

## Key Features

### Layout

- `row` / `col`: Vertical/horizontal division
- Size specification: `height: 40%`, `width: 50mm`, omit for auto
- Nesting: Arbitrarily deep nesting supported

### Panel Attributes

- `image`: Image file path (relative path)
- `image_fit`: `cover` / `contain` / `fill`
- `text`: Text within panel
- `border`: Border thickness
- `importance`: Importance level (1-3)

### Dynamic Effects

Skew panel borders to express movement:

```manga
panel action {
  skew_left: 10   // Rotate left border 10° clockwise
  skew_right: -8  // Rotate right border 8° counterclockwise
}
```

## License

MIT

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src

# Linting
ruff check src
```
