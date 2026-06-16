"""DSL parser using Lark."""

from pathlib import Path
from typing import Optional
from lark import Lark, Transformer, v_args
from .ast import (
    Page, PageConfig, RowNode, ColNode, PanelNode, PanelAttrs, Length
)
from .errors import ParseError


# Page size definitions (width x height in mm)
PAGE_SIZES = {
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "B4": (257.0, 364.0),
    "B5": (182.0, 257.0),
}


class MangaTransformer(Transformer):
    """Transform parse tree into AST."""

    def __init__(self) -> None:
        super().__init__()
        self.page_config = PageConfig()
        self.panel_attrs_stack: list[dict[str, any]] = []

    @v_args(inline=False)
    def start(self, items: list) -> Page:
        """Root rule: start -> page"""
        return items[0]

    @v_args(inline=False)
    def page(self, items: list) -> Page:
        """page: "page" CNAME? "{" page_body* "}" """
        # Check if first item is a name
        children = []
        for item in items:
            if isinstance(item, str) and not isinstance(item, (RowNode, ColNode, PanelNode)):
                self.page_config.name = item
            elif isinstance(item, (RowNode, ColNode, PanelNode)):
                children.append(item)

        return Page(config=self.page_config, children=children)

    @v_args(inline=True)
    def page_body(self, item: any) -> any:
        """page_body: page_attr | statement"""
        return item

    @v_args(inline=True)
    def page_attr(self, name: str, value: any) -> None:
        """page_attr: CNAME ":" value"""
        import re
        attr_name = str(name)

        if attr_name == "size":
            value_str = str(value)
            m = re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(mm|px|pt)?", value_str)
            if m:
                w, h = float(m.group(1)), float(m.group(2))
                unit = m.group(3) or "mm"
                self.page_config.size = value_str
                self.page_config.size_unit = unit  # type: ignore
                # Always convert to mm for layout calculations
                factor = {"mm": 1.0, "px": 25.4 / 96, "pt": 25.4 / 72}[unit]
                self.page_config.width_mm = w * factor
                self.page_config.height_mm = h * factor
            elif value_str in PAGE_SIZES:
                width, height = PAGE_SIZES[value_str]
                self.page_config.size = value_str
                self.page_config.size_unit = "mm"
                self.page_config.width_mm = width
                self.page_config.height_mm = height
            else:
                raise ParseError(f"Unknown page size: {value_str}")
        elif attr_name == "direction":
            self.page_config.direction = str(value)  # type: ignore
        elif attr_name == "gutter":
            self.page_config.gutter = float(value)
        elif attr_name == "padding":
            self.page_config.padding = float(value)
        elif attr_name == "background":
            self.page_config.background = str(value).strip('"')
        elif attr_name == "dpi":
            self.page_config.dpi = int(float(value))
        elif attr_name == "border":
            self.page_config.border = float(value)
        elif attr_name == "border_color":
            self.page_config.border_color = str(value).strip('"')
        else:
            raise ParseError(f"Unknown page attribute: {attr_name}")

        return None

    @v_args(inline=False)
    def statement(self, items: list) -> any:
        """statement: row_stmt | col_stmt | panel_stmt"""
        return items[0]

    @v_args(inline=False)
    def row_stmt(self, items: list) -> RowNode:
        """row_stmt: "row" row_attrs? "{" statement* "}" """
        height = None
        gutter = None
        align = "start"
        margin_top = 0.0
        margin_bottom = 0.0
        margin_left = 0.0
        margin_right = 0.0
        children = []

        for item in items:
            if isinstance(item, dict):
                height = item.get("height", height)
                gutter = item.get("gutter", gutter)
                align = item.get("align", align)
                margin_top = item.get("margin_top", margin_top)
                margin_bottom = item.get("margin_bottom", margin_bottom)
                margin_left = item.get("margin_left", margin_left)
                margin_right = item.get("margin_right", margin_right)
            elif isinstance(item, (RowNode, ColNode, PanelNode)):
                children.append(item)

        return RowNode(
            height=height,
            gutter=gutter,
            align=align,  # type: ignore
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            margin_right=margin_right,
            children=children
        )

    @v_args(inline=False)
    def col_stmt(self, items: list) -> ColNode:
        """col_stmt: "col" col_attrs? "{" statement* "}" """
        width = None
        gutter = None
        align = "start"
        margin_top = 0.0
        margin_bottom = 0.0
        margin_left = 0.0
        margin_right = 0.0
        children = []

        for item in items:
            if isinstance(item, dict):
                width = item.get("width", width)
                gutter = item.get("gutter", gutter)
                align = item.get("align", align)
                margin_top = item.get("margin_top", margin_top)
                margin_bottom = item.get("margin_bottom", margin_bottom)
                margin_left = item.get("margin_left", margin_left)
                margin_right = item.get("margin_right", margin_right)
            elif isinstance(item, (RowNode, ColNode, PanelNode)):
                children.append(item)

        return ColNode(
            width=width,
            gutter=gutter,
            align=align,  # type: ignore
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            margin_right=margin_right,
            children=children
        )

    @v_args(inline=False)
    def panel_stmt(self, items: list) -> PanelNode:
        """panel_stmt: "panel" CNAME panel_def?"""
        panel_id = str(items[0])
        # Initialize panel attributes with page-level defaults
        attrs = PanelAttrs(
            border=self.page_config.border,
            border_color=self.page_config.border_color
        )

        if len(items) > 1 and isinstance(items[1], dict):
            attrs_dict = items[1]
            for key, value in attrs_dict.items():
                if hasattr(attrs, key):
                    setattr(attrs, key, value)

        return PanelNode(id=panel_id, attrs=attrs)

    @v_args(inline=False)
    def panel_def(self, items: list) -> dict[str, any]:
        """panel_def: "{" panel_attr* "}" | panel_inline_attrs"""
        attrs: dict[str, any] = {}
        for item in items:
            if isinstance(item, dict):
                attrs.update(item)
        return attrs

    @v_args(inline=False)
    def panel_inline_attrs(self, items: list) -> dict[str, any]:
        """panel_inline_attrs: panel_attr ("," panel_attr)*"""
        attrs: dict[str, any] = {}
        for item in items:
            if isinstance(item, dict):
                attrs.update(item)
        return attrs

    @v_args(inline=True)
    def panel_attr(self, name: str, value: any) -> dict[str, any]:
        """panel_attr: CNAME ":" value"""
        attr_name = str(name)
        if attr_name == "importance":
            return {attr_name: int(float(value))}
        elif attr_name in ["border", "skew_left", "skew_right", "skew_top", "skew_bottom",
                            "offset_top", "offset_bottom", "offset_left", "offset_right",
                            "border_top", "border_bottom", "border_left", "border_right"]:
            return {attr_name: float(value)}
        elif attr_name in ["image", "text", "label", "border_color", "background", "shape"]:
            return {attr_name: str(value).strip('"')}
        elif attr_name in ["image_fit", "text_direction"]:
            return {attr_name: str(value)}
        else:
            return {attr_name: value}

    @v_args(inline=False)
    def row_attrs(self, items: list) -> dict[str, any]:
        """row_attrs: row_attr ("," row_attr)*"""
        attrs: dict[str, any] = {}
        for item in items:
            if isinstance(item, dict):
                attrs.update(item)
        return attrs

    @v_args(inline=True)
    def row_attr(self, item: dict) -> dict[str, any]:
        """row_attr: row_height | row_gutter | row_align | row_skew"""
        return item

    @v_args(inline=True)
    def row_height(self, value: Length) -> dict[str, Length]:
        """row_height: \"height\" \":\" length_value"""
        return {"height": value}

    @v_args(inline=True)
    def row_gutter(self, value: str) -> dict[str, float]:
        """row_gutter: \"gutter\" \":\" NUMBER"""
        return {"gutter": float(value)}

    @v_args(inline=True)
    def row_align(self, value: str) -> dict[str, str]:
        """row_align: \"align\" \":\" CNAME"""
        return {"align": str(value)}

    @v_args(inline=False)
    def row_margin(self, items: list) -> dict[str, float]:
        """row_margin: margin_key ":" NUMBER"""
        return {str(items[0]): float(items[1])}

    @v_args(inline=False)
    def col_attrs(self, items: list) -> dict[str, any]:
        """col_attrs: col_attr ("," col_attr)*"""
        attrs: dict[str, any] = {}
        for item in items:
            if isinstance(item, dict):
                attrs.update(item)
        return attrs

    @v_args(inline=True)
    def col_attr(self, item: dict) -> dict[str, any]:
        """col_attr: col_width | col_gutter | col_align"""
        return item

    @v_args(inline=True)
    def col_width(self, value: Length) -> dict[str, Length]:
        """col_width: \"width\" \":\" length_value"""
        return {"width": value}

    @v_args(inline=True)
    def col_gutter(self, value: str) -> dict[str, float]:
        """col_gutter: \"gutter\" \":\" NUMBER"""
        return {"gutter": float(value)}

    @v_args(inline=True)
    def col_align(self, value: str) -> dict[str, str]:
        """col_align: \"align\" \":\" CNAME"""
        return {"align": str(value)}

    @v_args(inline=False)
    def col_margin(self, items: list) -> dict[str, float]:
        """col_margin: margin_key ":" NUMBER"""
        return {str(items[0]): float(items[1])}

    @v_args(inline=False)
    def length_value(self, items: list) -> Length:
        """length_value: NUMBER UNIT | PERCENTAGE"""
        if len(items) == 1:
            # PERCENTAGE
            token = items[0]
            value_str = str(token).rstrip('%')
            return Length(value=float(value_str), unit="%")
        else:
            # NUMBER UNIT
            number = items[0]
            unit = items[1]
            return Length(value=float(number), unit=str(unit))

    @v_args(inline=True)
    def value(self, *args: any) -> any:
        """value: NUMBER UNIT? | PERCENTAGE | STRING | CNAME"""
        if len(args) == 1:
            return args[0]
        elif len(args) == 2:
            # NUMBER with UNIT
            return float(args[0])
        return args[0]

    # Terminal handlers
    def NUMBER(self, token: any) -> str:
        return token.value

    def CNAME(self, token: any) -> str:
        return token.value

    def UNIT(self, token: any) -> str:
        return token.value

    def PERCENTAGE(self, token: any) -> str:
        return token.value

    def STRING(self, token: any) -> str:
        return token.value


# Global parser instance (cached)
_parser: Optional[Lark] = None


def get_parser() -> Lark:
    """Get or create the cached parser instance."""
    global _parser
    if _parser is None:
        grammar_path = Path(__file__).parent / "grammar.lark"
        _parser = Lark.open(
            grammar_path,
            parser="lalr",
            start="start",
        )
    return _parser


def parse(source: str) -> Page:
    """Parse DSL source code and return AST.

    Args:
        source: DSL source code string

    Returns:
        Page AST node

    Raises:
        ParseError: If source has syntax errors
    """
    parser = get_parser()

    try:
        tree = parser.parse(source)
        transformer = MangaTransformer()
        ast = transformer.transform(tree)
        return ast  # type: ignore
    except Exception as e:
        raise ParseError(f"Parse error: {e}") from e
