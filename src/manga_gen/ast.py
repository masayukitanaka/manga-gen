"""AST node definitions using Pydantic models."""

from typing import Literal, Optional, Union
from pydantic import BaseModel, Field


# Length value (size specification)
class Length(BaseModel):
    """Represents a size value with unit (mm, %, or auto)."""
    value: float
    unit: Literal["mm", "px", "pt", "%", "auto"]


# Page configuration
class PageConfig(BaseModel):
    """Page-level configuration settings."""
    name: Optional[str] = None
    size: Literal["A3", "A4", "B4", "B5"] = "A4"
    width_mm: float = 210.0
    height_mm: float = 297.0
    direction: Literal["rtl", "ltr"] = "ltr"
    gutter: float = 5.0
    padding: float = 10.0
    background: str = "#ffffff"
    dpi: int = 300
    border: float = 1.0
    border_color: str = "#000000"


# Panel attributes
class PanelAttrs(BaseModel):
    """Attributes for a panel node."""
    importance: Literal[1, 2, 3] = 2
    image: Optional[str] = None
    image_fit: Literal["cover", "contain", "fill"] = "cover"
    label: Optional[str] = None
    text: Optional[str] = None
    text_direction: Literal["horizontal", "vertical"] = "horizontal"
    border: float = 1.0
    border_color: str = "#000000"
    # Individual border control (None = use border value, 0 = hide, >0 = specific width)
    border_top: Optional[float] = None
    border_bottom: Optional[float] = None
    border_left: Optional[float] = None
    border_right: Optional[float] = None
    background: str = "#ffffff"
    # Skew for individual edges (in degrees)
    skew_left: float = 0.0  # Positive: shift up, Negative: shift down
    skew_right: float = 0.0
    skew_top: float = 0.0  # Positive: shift right, Negative: shift left
    skew_bottom: float = 0.0
    # Offset for panel position (in mm)
    offset_top: float = 0.0  # Negative: expand up, Positive: shrink from top
    offset_bottom: float = 0.0  # Negative: expand down, Positive: shrink from bottom
    offset_left: float = 0.0  # Negative: expand left, Positive: shrink from left
    offset_right: float = 0.0  # Negative: expand right, Positive: shrink from right


# Panel node
class PanelNode(BaseModel):
    """A panel (manga frame/koma)."""
    kind: Literal["panel"] = "panel"
    id: str
    attrs: PanelAttrs = Field(default_factory=PanelAttrs)


# Row node
class RowNode(BaseModel):
    """A vertical container that divides space into rows."""
    kind: Literal["row"] = "row"
    height: Optional[Length] = None
    gutter: Optional[float] = None
    align: Literal["start", "center", "end"] = "start"
    margin_top: float = 0.0
    margin_bottom: float = 0.0
    margin_left: float = 0.0
    margin_right: float = 0.0
    children: list["LayoutNode"]


# Col node
class ColNode(BaseModel):
    """A horizontal container that divides space into columns."""
    kind: Literal["col"] = "col"
    width: Optional[Length] = None
    gutter: Optional[float] = None
    align: Literal["start", "center", "end"] = "start"
    margin_top: float = 0.0
    margin_bottom: float = 0.0
    margin_left: float = 0.0
    margin_right: float = 0.0
    children: list["LayoutNode"]


# Union type for all layout nodes
LayoutNode = Union[PanelNode, RowNode, ColNode]


# Page root
class Page(BaseModel):
    """The root node representing a manga page."""
    config: PageConfig
    children: list[LayoutNode]


# Resolve forward references for recursive types
RowNode.model_rebuild()
ColNode.model_rebuild()
Page.model_rebuild()
