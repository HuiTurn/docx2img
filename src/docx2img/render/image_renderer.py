"""Image rendering helpers."""

from __future__ import annotations

from PIL import Image, ImageDraw


class ImageRenderer:
    """Paste images onto the page canvas."""

    def draw_image(
        self,
        canvas: Image.Image,
        img: Image.Image,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        knockout_white: bool = False,
        white_threshold: int = 245,
    ) -> ImageDraw.ImageDraw:
        if img is None or w <= 0 or h <= 0:
            return ImageDraw.Draw(canvas)
        resized = img.resize((max(1, int(round(w))), max(1, int(round(h)))), Image.LANCZOS)

        if knockout_white:
            resized = self._knockout_near_white(resized, white_threshold)

        if resized.mode in ("RGBA", "LA") or (resized.mode == "P" and "transparency" in resized.info):
            canvas.paste(resized, (int(round(x)), int(round(y))), resized.convert("RGBA"))
        else:
            canvas.paste(resized.convert(canvas.mode), (int(round(x)), int(round(y))))
        return ImageDraw.Draw(canvas)

    @staticmethod
    def _knockout_near_white(img: Image.Image, threshold: int = 245) -> Image.Image:
        """Make near-white pixels transparent.

        Cover banners / decorative floats are often saved as opaque RGB with a
        white page-matching backdrop. Layout lets body text tuck under that
        padding (via content-bbox height), so rendering must not paint the
        white over the text.
        """
        rgba = img.convert("RGBA")
        thr = max(0, min(255, int(threshold)))
        # Split channels and build alpha mask in one pass (faster than per-pixel).
        r, g, b, a = rgba.split()
        # Near-white where all of R,G,B >= thr
        mask_r = r.point(lambda p: 255 if p >= thr else 0)
        mask_g = g.point(lambda p: 255 if p >= thr else 0)
        mask_b = b.point(lambda p: 255 if p >= thr else 0)
        # white_mask is 255 where near-white
        white_mask = Image.composite(mask_r, Image.new("L", rgba.size, 0), mask_g)
        white_mask = Image.composite(white_mask, Image.new("L", rgba.size, 0), mask_b)
        # Keep original alpha where not white; zero alpha where white
        # new_a = a where white_mask==0, else 0
        new_a = Image.composite(Image.new("L", rgba.size, 0), a, white_mask)
        rgba.putalpha(new_a)
        return rgba
