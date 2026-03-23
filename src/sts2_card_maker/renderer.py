from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .models import CardConfig, LayoutConfig

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "assets" / "manifest.json"

DEFAULT_BANNER_HSV: dict[str, dict[str, float]] = {
    "basic": {"h": 1.0, "s": 0.0, "v": 0.85},
    "common": {"h": 1.0, "s": 0.0, "v": 0.85},
    "uncommon": {"h": 1.0, "s": 1.0, "v": 1.0},
    "rare": {"h": 0.563, "s": 1.198, "v": 1.14},
    "curse": {"h": 0.27, "s": 1.1, "v": 0.9},
    "event": {"h": 0.875, "s": 0.85, "v": 0.9},
    "quest": {"h": 0.515, "s": 1.727, "v": 0.9},
    "status": {"h": 0.634, "s": 0.35, "v": 0.8},
    "ancient": {"h": 0.0, "s": 0.2, "v": 0.9},
}

TYPE_LABELS = {
    "attack": "Attack",
    "skill": "Skill",
    "power": "Power",
}

ENERGY_ICON_SIZE = 28
ENERGY_ICON_GAP = 2
STAR_ICON_SIZE = 28
STAR_ICON_GAP = 2
DESC_ICON_TOP_OFFSET = 10


class AssetPack:
    def __init__(self, manifest_path: Path = MANIFEST_PATH):
        self.root = manifest_path.parent.parent
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.card_w = int(self.manifest["cardW"])
        self.card_h = int(self.manifest["cardH"])
        self.out_w = int(self.manifest["outW"])
        self.out_h = int(self.manifest["outH"])

        self.atlas_images: list[Image.Image] = []
        for p in self.manifest["atlases"]:
            self.atlas_images.append(Image.open(self.root / p).convert("RGBA"))

        self.type_plaque = Image.open(self.root / self.manifest["typePlaque"]).convert("RGBA")
        self.regions = self.manifest["regions"]
        self.banner_hsv = self.manifest.get("bannerHsv", {})
        self.frame_hsv = self.manifest.get("frameHsv", {})
        self.font_bold = ImageFont.truetype(str(self.root / self.manifest["fonts"]["bold"]), 50)
        self.font_regular = ImageFont.truetype(str(self.root / self.manifest["fonts"]["regular"]), 40)
        self.font_cost = ImageFont.truetype(str(self.root / self.manifest["fonts"]["bold"]), 62)
        self.font_type = ImageFont.truetype(str(self.root / self.manifest["fonts"]["bold"]), 30)

        self.icons = {
            "star": Image.open(self.root / "assets/icons/star_icon.png").convert("RGBA"),
            "ironclad": Image.open(self.root / "assets/icons/ironclad_energy_icon.png").convert("RGBA"),
            "silent": Image.open(self.root / "assets/icons/silent_energy_icon.png").convert("RGBA"),
            "defect": Image.open(self.root / "assets/icons/defect_energy_icon.png").convert("RGBA"),
            "necrobinder": Image.open(self.root / "assets/icons/necrobinder_energy_icon.png").convert("RGBA"),
            "regent": Image.open(self.root / "assets/icons/regent_energy_icon.png").convert("RGBA"),
            "colorless": Image.open(self.root / "assets/icons/colorless_energy_icon.png").convert("RGBA"),
        }

    def region(self, name: str) -> tuple[Image.Image, tuple[int, int, int, int]]:
        entry = self.regions[name]
        atlas = self.atlas_images[int(entry["atlas"])]
        r = entry["region"]
        box = (int(r["x"]), int(r["y"]), int(r["x"]) + int(r["w"]), int(r["y"]) + int(r["h"]))
        return atlas, box


class CardRenderer:
    def __init__(self, assets: AssetPack, layout: LayoutConfig | None = None):
        self.assets = assets
        self.layout = layout or LayoutConfig()

    @staticmethod
    def _char_key(character: str) -> str:
        s = (character or "").strip().lower()
        if s in {"the regent", "regent"}:
            return "regent"
        if s in {"ironclad", "silent", "defect", "necrobinder", "colorless", "quest"}:
            return s
        if s in {"status", "curse", "event", "token"}:
            return "colorless"
        return "colorless"

    @staticmethod
    def _cover_resize(img: Image.Image, w: int, h: int) -> Image.Image:
        sw, sh = img.size
        src_ratio = sw / sh
        dst_ratio = w / h
        if src_ratio > dst_ratio:
            nw = int(sh * dst_ratio)
            x = (sw - nw) // 2
            crop = img.crop((x, 0, x + nw, sh))
        else:
            nh = int(sw / dst_ratio)
            y = (sh - nh) // 2
            crop = img.crop((0, y, sw, y + nh))
        return crop.resize((w, h), Image.Resampling.LANCZOS)

    @staticmethod
    def _apply_hsv(src: Image.Image, h: float, s: float, v: float) -> Image.Image:
        arr = np.array(src).astype(np.float32)
        rgb = arr[..., :3] / 255.0
        a = arr[..., 3:4]

        rgb_to_yiq = np.array([
            [0.2989, 0.5870, 0.1140],
            [0.5959, -0.2774, -0.3216],
            [0.2115, -0.5229, 0.3114],
        ], dtype=np.float32)
        yiq_to_rgb = np.linalg.inv(rgb_to_yiq)

        yiq = rgb @ rgb_to_yiq.T
        hue = (1.0 - h) * (2.0 * np.pi)
        c, si = np.cos(hue), np.sin(hue)
        hue_shift = np.array([[1.0, 0.0, 0.0], [0.0, c, -si], [0.0, si, c]], dtype=np.float32)
        sat_shift = np.array([[1.0, 0.0, 0.0], [0.0, s, 0.0], [0.0, 0.0, s]], dtype=np.float32)
        yiq = yiq @ hue_shift.T
        yiq = yiq @ sat_shift.T
        yiq *= v
        out = yiq @ yiq_to_rgb.T
        out = np.clip(out, 0.0, 1.0)
        rgba = np.concatenate([out * 255.0, a], axis=-1).astype(np.uint8)
        return Image.fromarray(rgba, mode="RGBA")

    @staticmethod
    def _draw_text_with_stroke(draw: ImageDraw.ImageDraw, pos: tuple[float, float], text: str, font: ImageFont.FreeTypeFont,
                               fill: tuple[int, int, int, int], stroke: tuple[int, int, int, int], stroke_w: int) -> None:
        draw.text(pos, text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=stroke)

    @staticmethod
    def _draw_text_with_stroke_shadow(
        draw: ImageDraw.ImageDraw,
        pos: tuple[float, float],
        text: str,
        font: ImageFont.FreeTypeFont,
        fill: tuple[int, int, int, int],
        stroke: tuple[int, int, int, int],
        stroke_w: int,
        shadow_offset: tuple[int, int] = (0, 0),
        shadow_color: tuple[int, int, int, int] = (0, 0, 0, 64),
    ) -> None:
        if shadow_offset != (0, 0):
            draw.text((pos[0] + shadow_offset[0], pos[1] + shadow_offset[1]), text, font=font, fill=shadow_color)
        if stroke_w > 0:
            draw.text(pos, text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=stroke)
        else:
            draw.text(pos, text, font=font, fill=fill)

    @staticmethod
    def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
        mask = Image.new("L", size, 0)
        d = ImageDraw.Draw(mask)
        d.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
        return mask

    def _type_label(self, cfg: CardConfig) -> str:
        if cfg.character == "quest":
            return "Quest"
        return TYPE_LABELS.get(cfg.card_type, cfg.card_type.title())

    def _component_names(self, cfg: CardConfig) -> dict[str, str | None]:
        is_ancient = cfg.rarity.lower() == "ancient"
        type_name = cfg.card_type.lower()
        char_key = self._char_key(cfg.character)
        return {
            "frame": "card_frame_ancient_s.tres" if is_ancient else f"card_frame_{type_name}_s.tres",
            "portrait_border": None if is_ancient else f"card_portrait_border_{type_name}_s.tres",
            "banner": "ancient_banner.tres" if is_ancient else "card_banner.tres",
            "energy": f"energy_{char_key}.tres",
        }

    def _normalize_special_pool(self, cfg: CardConfig) -> CardConfig:
        out = CardConfig(**cfg.__dict__)
        if out.character == "quest":
            out.card_type = "skill"
            out.rarity = "quest"
        elif out.character == "status":
            out.card_type = "skill"
            out.rarity = "status"
        elif out.character == "curse":
            out.card_type = "skill"
            out.rarity = "curse"
        return out

    def render(self, cfg: CardConfig) -> Image.Image:
        cfg = self._normalize_special_pool(cfg)
        ly = self.layout
        is_ancient = cfg.rarity.lower() == "ancient"

        canvas = Image.new("RGBA", (self.assets.out_w, self.assets.out_h), (0, 0, 0, 0))
        card = Image.new("RGBA", (self.assets.card_w, self.assets.card_h), (0, 0, 0, 0))
        offx = (self.assets.out_w - self.assets.card_w) // 2 + ly.canvas_offset_x
        offy = (self.assets.out_h - self.assets.card_h) // 2 + ly.canvas_offset_y

        names = self._component_names(cfg)
        banner_hsv = self.assets.banner_hsv.get(cfg.rarity.lower(), DEFAULT_BANNER_HSV.get(cfg.rarity.lower(), DEFAULT_BANNER_HSV["common"]))
        frame_hsv = self.assets.frame_hsv.get(self._char_key(cfg.character), self.assets.frame_hsv.get("ironclad", {"h": 1.0, "s": 1.0, "v": 1.0}))

        # 1) art
        if cfg.portrait_path and cfg.portrait_path.exists():
            art_img = Image.open(cfg.portrait_path).convert("RGBA")
            x, y, w, h = ly.ancient_art_box if is_ancient else ly.user_art_box
            art_resized = self._cover_resize(art_img, w, h)
            art_layer = Image.new("RGBA", (self.assets.card_w, self.assets.card_h), (0, 0, 0, 0))
            art_layer.alpha_composite(art_resized, (x, y))
            if is_ancient:
                art_layer.putalpha(self._rounded_mask((self.assets.card_w, self.assets.card_h), ly.ancient_clip_radius))
            card.alpha_composite(art_layer)
        else:
            # fallback block
            x, y, w, h = ly.ancient_art_box if is_ancient else ly.user_art_box
            fill = Image.new("RGBA", (w, h), (26, 26, 26, 255))
            card.alpha_composite(fill, (x, y))

        # 2) frame
        frame_atlas, frame_box = self.assets.region(str(names["frame"]))
        frame = frame_atlas.crop(frame_box).resize((self.assets.card_w, self.assets.card_h), Image.Resampling.LANCZOS)
        frame = self._apply_hsv(frame, frame_hsv["h"], frame_hsv["s"], frame_hsv["v"])
        card.alpha_composite(frame)

        # 3) portrait border
        if names["portrait_border"]:
            b_atlas, b_box = self.assets.region(str(names["portrait_border"]))
            b_x, b_y, b_w, b_h = ly.portrait_border_rect
            border = b_atlas.crop(b_box).resize((b_w, b_h), Image.Resampling.LANCZOS)
            border = self._apply_hsv(border, banner_hsv["h"], banner_hsv["s"], banner_hsv["v"])
            card.alpha_composite(border, (b_x, b_y))

        # 4) banner (draw on final canvas so ribbon overflow is not clipped by card bounds)
        ba_atlas, ba_box = self.assets.region(str(names["banner"]))
        bw_src = ba_box[2] - ba_box[0]
        bh_src = ba_box[3] - ba_box[1]
        banner_h = ly.banner_h_ancient if is_ancient else ly.banner_h
        banner_w = int((bw_src * banner_h / bh_src) * ly.banner_w_scale)
        banner = ba_atlas.crop(ba_box).resize((banner_w, banner_h), Image.Resampling.LANCZOS)
        if not is_ancient:
            banner = self._apply_hsv(banner, banner_hsv["h"], banner_hsv["s"], banner_hsv["v"])
        banner_x = offx + (self.assets.card_w - banner_w) // 2
        banner_y = ly.banner_y_normal
        banner_y = offy + banner_y

        draw = ImageDraw.Draw(card)
        canvas_draw = ImageDraw.Draw(canvas)

        # 5) energy (draw on final canvas so top-left overflow is preserved)
        no_energy = cfg.character in {"quest", "curse"}
        energy: Image.Image | None = None
        energy_x = 0
        energy_y = 0
        cost_text = ""
        cost_tx = 0
        cost_ty = 0
        if (cfg.cost or "").strip() and not no_energy:
            e_atlas, e_box = self.assets.region(str(names["energy"]))
            energy = e_atlas.crop(e_box).resize((ly.energy_size, ly.energy_size), Image.Resampling.LANCZOS)
            energy_x = offx + ly.energy_pos[0]
            energy_y = offy + ly.energy_pos[1]

            cost_text = (cfg.cost or "")[:2]
            bbox = canvas_draw.textbbox((0, 0), cost_text, font=self.assets.font_cost)
            tw = bbox[2] - bbox[0]
            cost_tx = energy_x + ly.energy_size // 2 - tw // 2 - 3
            cost_ty = energy_y + ly.energy_size // 2 - 40 + ly.cost_y_offset

        # 6) type plaque + label
        px, py, pw, ph = ly.type_plaque_rect
        plaque = self.assets.type_plaque.resize((pw, ph), Image.Resampling.LANCZOS)
        plaque = self._apply_hsv(plaque, banner_hsv["h"], banner_hsv["s"], banner_hsv["v"])
        card.alpha_composite(plaque, (px, py))
        type_text = self._type_label(cfg)
        tb = draw.textbbox((0, 0), type_text, font=self.assets.font_type)
        tw = tb[2] - tb[0]
        draw.text(((self.assets.card_w - tw) // 2, py + ph // 2 - 19), type_text, font=self.assets.font_type, fill=(13, 13, 13, 225))

        # 7) description (simple parser)
        raw = (cfg.description or " ").replace("\\n", "\n")
        raw = re.sub(r"(\{singleStarIcon\})+", lambda m: "{Stars:starIcons(%d)}" % (len(re.findall(r"\{singleStarIcon\}", m.group(0)))), raw)

        lines = raw.split("\n")[:8]
        block_top = int(ly.desc_center_y - ((len(lines) - 1) * ly.desc_line_h) / 2)

        for i, line in enumerate(lines):
            y = block_top + i * ly.desc_line_h
            self._draw_desc_line(draw, card, line, y, ly.desc_max_width, self.assets.font_regular, cfg)

        canvas.alpha_composite(card, (offx, offy))
        canvas.alpha_composite(banner, (banner_x, banner_y))
        if (cfg.cost or "").strip() and not no_energy and energy is not None:
            canvas.alpha_composite(energy, (energy_x, energy_y))
            cost_fill = (127, 255, 0, 255) if cfg.cost_green else (255, 252, 242, 255)
            cost_stroke = (50, 80, 0, 255) if cfg.cost_green else (97, 59, 26, 255)
            self._draw_text_with_stroke_shadow(
                canvas_draw,
                (cost_tx, cost_ty),
                cost_text,
                self.assets.font_cost,
                cost_fill,
                cost_stroke,
                6,
                shadow_offset=(5, 5),
                shadow_color=(0, 0, 0, 77),
            )

        # Draw title last so it always stays above banner.
        title = (cfg.card_name or "Card").strip()
        if cfg.upgraded:
            title += "+"
        tbox = canvas_draw.textbbox((0, 0), title, font=self.assets.font_bold)
        tw = tbox[2] - tbox[0]
        tx = offx + (self.assets.card_w - tw) // 2
        ty = offy + ly.title_y_normal
        fill = (127, 255, 0, 255) if cfg.upgraded else (255, 247, 237, 255)
        self._draw_text_with_stroke_shadow(
            canvas_draw,
            (tx, ty),
            title,
            self.assets.font_bold,
            fill,
            (20,20,20,230),
            5,
            shadow_offset=(0, 0),
        )
        return canvas

    def _draw_desc_line(
        self,
        draw: ImageDraw.ImageDraw,
        card: Image.Image,
        line: str,
        y: int,
        max_width: int,
        font: ImageFont.FreeTypeFont,
        cfg: CardConfig,
    ) -> None:
        segs: list[dict[str, Any]] = []
        i = 0
        buf = ""
        green = False
        gold = False
        yellow = False

        def active_style() -> str:
            if green:
                return "green"
            if gold:
                return "gold"
            if yellow:
                return "yellow"
            return "normal"

        def flush() -> None:
            nonlocal buf
            if buf:
                segs.append({"kind": "text", "text": buf, "style": active_style()})
                buf = ""

        while i < len(line):
            rest = line[i:]
            if rest[:7].lower() == "[green]":
                flush()
                green = True
                i += 7
                continue
            if rest[:8].lower() == "[/green]":
                flush()
                green = False
                i += 8
                continue
            if rest[:6].lower() == "[gold]":
                flush()
                gold = True
                i += 6
                continue
            if rest[:7].lower() == "[/gold]":
                flush()
                gold = False
                i += 7
                continue
            if rest.startswith("{singleStarIcon}"):
                flush()
                segs.append({"kind": "star", "count": 1})
                i += len("{singleStarIcon}")
                continue

            m_energy = re.match(r"^\{(\w+):energyIcons(?:\((\d*)\))?\}", rest)
            if m_energy:
                flush()
                raw_count = m_energy.group(2)
                count = max(1, int(raw_count)) if raw_count else 1
                segs.append({"kind": "energy", "count": count})
                i += len(m_energy.group(0))
                continue

            m_star = re.match(r"^\{(\w+):starIcons(?:\((\d*)\))?\}", rest)
            if m_star:
                flush()
                raw_count = m_star.group(2)
                count = max(1, int(raw_count)) if raw_count else 1
                segs.append({"kind": "star", "count": count})
                i += len(m_star.group(0))
                continue

            if line[i] == "{":
                flush()
                yellow = True
                i += 1
                continue
            if line[i] == "}":
                flush()
                yellow = False
                i += 1
                continue

            buf += line[i]
            i += 1

        flush()

        energy_icon = self.assets.icons[self._char_key(cfg.character)].resize((ENERGY_ICON_SIZE, ENERGY_ICON_SIZE), Image.Resampling.LANCZOS)
        star_icon = self.assets.icons["star"].resize((STAR_ICON_SIZE, STAR_ICON_SIZE), Image.Resampling.LANCZOS)

        total_w = 0
        for seg in segs:
            if seg["kind"] == "text":
                tb = draw.textbbox((0, 0), seg["text"], font=font)
                total_w += tb[2] - tb[0]
            elif seg["kind"] == "energy":
                count = int(seg["count"])
                if count >= 4:
                    num = str(count)
                    tb = draw.textbbox((0, 0), num, font=font)
                    total_w += (tb[2] - tb[0]) + ENERGY_ICON_GAP + ENERGY_ICON_SIZE
                else:
                    total_w += count * ENERGY_ICON_SIZE + max(0, count - 1) * ENERGY_ICON_GAP
            elif seg["kind"] == "star":
                count = int(seg["count"])
                total_w += count * STAR_ICON_SIZE + max(0, count - 1) * STAR_ICON_GAP

        total_w = min(total_w, max_width)
        x = (self.assets.card_w - total_w) // 2

        for seg in segs:
            kind = seg["kind"]
            if kind == "energy":
                count = int(seg["count"])
                if count >= 4:
                    num = str(count)
                    self._draw_text_with_stroke_shadow(
                        draw,
                        (x, y),
                        num,
                        font,
                        (255, 247, 237, 255),
                        (60, 55, 50, 255),
                        0,
                        shadow_offset=(0, 0),
                        shadow_color=(0, 0, 0, 64),
                    )
                    tb = draw.textbbox((x, y), num, font=font)
                    x = tb[2] + ENERGY_ICON_GAP
                    card.alpha_composite(energy_icon, (x, y + DESC_ICON_TOP_OFFSET))
                    x += ENERGY_ICON_SIZE
                else:
                    for idx in range(count):
                        card.alpha_composite(energy_icon, (x, y + DESC_ICON_TOP_OFFSET))
                        x += ENERGY_ICON_SIZE + (ENERGY_ICON_GAP if idx < count - 1 else 0)
                continue
            if kind == "star":
                count = int(seg["count"])
                for idx in range(count):
                    card.alpha_composite(star_icon, (x, y + DESC_ICON_TOP_OFFSET))
                    x += STAR_ICON_SIZE + (STAR_ICON_GAP if idx < count - 1 else 0)
                continue

            style = seg["style"]
            fill = (255, 247, 237, 255)
            if style == "green":
                fill = (127, 255, 0, 255)
            elif style in {"gold", "yellow"}:
                fill = (255, 225, 80, 255)

            text = seg["text"]
            stroke = (60, 55, 50, 255)
            if style == "green":
                stroke = (50, 80, 0, 255)
            elif style in {"gold", "yellow"}:
                stroke = (89, 64, 10, 255)
            self._draw_text_with_stroke_shadow(
                draw,
                (x, y),
                text,
                font,
                fill,
                stroke,
                0,
                shadow_offset=(0, 0),
                shadow_color=(0, 0, 0, 64),
            )
            tb = draw.textbbox((x, y), text, font=font)
            x = tb[2]


def save_card_image(img: Image.Image, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
