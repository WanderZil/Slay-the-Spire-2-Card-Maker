from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CardConfig:
    card_name: str = "Strike"
    description: str = "Deal {6} damage."
    card_type: str = "attack"  # attack|skill|power
    character: str = "ironclad"  # ironclad|silent|defect|necrobinder|regent|colorless|quest|status|curse|event|token
    rarity: str = "common"  # basic|common|uncommon|rare|curse|status|event|quest|ancient
    cost: str = "1"
    upgraded: bool = False
    cost_green: bool = False
    portrait_path: Path | None = None


@dataclass
class LayoutConfig:
    canvas_offset_x: int = 0
    canvas_offset_y: int = 16
    user_art_box: tuple[int, int, int, int] = (50, 86, 498, 380)
    ancient_art_box: tuple[int, int, int, int] = (10, 10, 575, 820)
    ancient_clip_radius: int = 34
    portrait_border_rect: tuple[int, int, int, int] = (24, 94, 550, 420)
    energy_pos: tuple[int, int] = (-32, -24)
    energy_size: int = 110
    cost_y_offset: int = 0
    banner_y_normal: int = 22
    banner_y_ancient: int = 10
    banner_h: int = 133
    banner_h_ancient: int = 162
    banner_w_scale: float = 1.075
    title_y_normal: int = 28
    title_y_ancient: int = 48
    type_plaque_rect: tuple[int, int, int, int] = (239, 424, 122, 74)
    desc_max_width: int = 480
    desc_center_y: int = 590
    desc_line_h: int = 42
