#!/usr/bin/env python3
"""Burn a removable-source watermark onto album images.

Originals stay in images/; outputs go to images_watermark/.
Re-run anytime; delete images_watermark/ to discard watermarked copies.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "images"
DST = ROOT / "images_watermark"

LINE1 = "fengweidiezhen"
LINE2 = "蜂围蝶阵"

# Hand-drawn album files (Illori excluded on purpose)
HAND_DRAWN = [
    "makima.jpeg",
    "kafka.jpeg",
    "ganyu.jpeg",
    "octopus.jpeg",
    "amiya.jpeg",
    "kamado.jpeg",
    "kuromi.jpeg",
]


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),  # 微软雅黑 — Chinese OK
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def process_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()
    with Image.open(src) as im:
        result = watermark(im)
        if suffix in {".jpg", ".jpeg"}:
            result.convert("RGB").save(dst, quality=92, optimize=True)
        else:
            result.save(dst)
    print(f"ok  {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")


def watermark(img: Image.Image) -> Image.Image:
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(12, min(base.width, base.height) // 52)
    font = load_font(font_size)
    line_gap = max(2, font_size // 6)
    margin = max(10, font_size)

    bbox1 = draw.textbbox((0, 0), LINE1, font=font)
    bbox2 = draw.textbbox((0, 0), LINE2, font=font)
    w1, h1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
    w2, h2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
    block_w = max(w1, w2)
    block_h = h1 + line_gap + h2

    x = base.width - block_w - margin
    y = base.height - block_h - margin

    # 透明度约 85% → 不透明度约 15%（alpha ≈ 38）
    shadow = (0, 0, 0, 20)
    fill = (255, 255, 255, 38)
    draw.text((x + 1, y + 1), LINE1, font=font, fill=shadow)
    draw.text((x + 1, y + h1 + line_gap + 1), LINE2, font=font, fill=shadow)
    draw.text((x, y), LINE1, font=font, fill=fill)
    draw.text((x, y + h1 + line_gap), LINE2, font=font, fill=fill)

    return Image.alpha_composite(base, overlay)


def main() -> int:
    count = 0

    for name in HAND_DRAWN:
        src = SRC / name
        if not src.is_file():
            print(f"skip missing {src}")
            continue
        process_file(src, DST / name)
        count += 1

    ai_src = SRC / "ai-art"
    if ai_src.is_dir():
        for src in sorted(ai_src.glob("*.png")):
            process_file(src, DST / "ai-art" / src.name)
            count += 1
        # Videos: copy as-is (no burn-in for now)
        vid_src = ai_src / "videos"
        if vid_src.is_dir():
            import shutil

            for src in sorted(vid_src.glob("*.mp4")):
                dst = DST / "ai-art" / "videos" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"copy {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")
                count += 1

    print(f"done: {count} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
