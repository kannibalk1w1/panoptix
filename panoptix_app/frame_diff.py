from __future__ import annotations

from pathlib import Path


def image_difference_score(first: Path, second: Path) -> float:
    from PIL import Image, ImageChops, ImageStat

    with Image.open(first) as first_image, Image.open(second) as second_image:
        left = first_image.convert("L").resize((64, 36))
        right = second_image.convert("L").resize((64, 36))
        diff = ImageChops.difference(left, right)
        return float(ImageStat.Stat(diff).mean[0])


def images_are_different(first: Path, second: Path, threshold: float) -> bool:
    return image_difference_score(first, second) >= threshold
