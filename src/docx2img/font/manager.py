"""Font manager - Load and cache fonts"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple
from PIL import ImageFont

from ..config import Config


class FontManager:
    """Manage font loading and caching.

    Lookup order:
      1. Config font_paths
      2. Project fonts/ directory
      3. System font directories
      4. Fallback chain / default
    """

    FONT_FALLBACKS = {
        "Times New Roman": ["times", "Times", "DejaVu Serif", "Liberation Serif", "serif"],
        "Arial": ["arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "sans-serif"],
        "SimSun": ["simsun", "宋体", "新宋体", "NSimSun", "nsimsun", "WenQuanYi Micro Hei", "Noto Sans CJK SC"],
        "SimHei": ["simhei", "黑体", "Microsoft YaHei", "msyh", "WenQuanYi Zen Hei"],
        "Microsoft YaHei": ["msyh", "微软雅黑", "Microsoft YaHei UI", "SimHei", "simhei"],
        "Microsoft YaHei Light": ["msyhl", "微软雅黑 Light", "Microsoft YaHei", "msyh"],
        "KaiTi": ["kaiti", "楷体", "STKaiti", "stkaiti", "华文楷体"],
        "FangSong": ["fangsong", "仿宋", "STFangsong"],
        "Calibri": ["calibri", "Arial", "arial", "Helvetica", "sans-serif"],
        "Courier New": ["cour", "Courier New", "DejaVu Sans Mono", "Liberation Mono"],
    }

    # Localized / alternate family names → canonical English family
    FAMILY_ALIASES = {
        "宋体": "SimSun",
        "新宋体": "SimSun",
        "细明体": "SimSun",
        "黑体": "SimHei",
        "微软雅黑": "Microsoft YaHei",
        "微软雅黑 ui": "Microsoft YaHei",
        "楷体": "KaiTi",
        "楷体_gb2312": "KaiTi",
        "仿宋": "FangSong",
        "仿宋_gb2312": "FangSong",
        "华文宋体": "SimSun",
        "华文黑体": "SimHei",
        "等线": "Microsoft YaHei",
        "方正小标宋简体": "SimSun",
        # 兰亭黑 series → SimHei: tighter metrics (1.0em vs YaHei 1.32em)
        # keep line heights close to the original Founder fonts, and the
        # heiti look is visually closer than YaHei.
        "方正兰亭粗黑简体": "SimHei",
        "方正兰亭黑简体": "SimHei",
        "方正兰亭中黑简体": "SimHei",
        "方正兰亭纤黑简体": "SimHei",
        "方正黑体简体": "SimHei",
        "华文细黑": "Microsoft YaHei",
        "华文楷体": "KaiTi",
        "华文中宋": "SimSun",
        "微软雅黑 light": "Microsoft YaHei Light",
        "microsoft yahei light": "Microsoft YaHei Light",
        "ｍｓ 明朝": "SimSun",
        "ｍｓ ゴシック": "SimHei",
        "ms mincho": "SimSun",
        "ms gothic": "SimHei",
        "ＭＳ 明朝": "SimSun",
        "ＭＳ ゴシック": "SimHei",
    }

    # Common Windows filename aliases (stem → family)
    WINDOWS_ALIASES = {
        "times": "Times New Roman",
        "timesbd": "Times New Roman",
        "timesi": "Times New Roman",
        "timesbi": "Times New Roman",
        "arial": "Arial",
        "arialbd": "Arial",
        "ariali": "Arial",
        "arialbi": "Arial",
        "simsun": "SimSun",
        "nsimsun": "SimSun",
        "simhei": "SimHei",
        "msyh": "Microsoft YaHei",
        "msyhbd": "Microsoft YaHei",
        "msyhl": "Microsoft YaHei Light",
        "simkai": "KaiTi",
        "kaiti": "KaiTi",
        "stkaiti": "KaiTi",
        "simfang": "FangSong",
        "fangsong": "FangSong",
        "calibri": "Calibri",
        "cour": "Courier New",
        "consola": "Consolas",
        "tahoma": "Tahoma",
        "verdana": "Verdana",
        "segoeui": "Segoe UI",
    }

    # When a Windows font file is found, also register these local names
    STEM_LOCAL_NAMES = {
        "simsun": ["宋体", "新宋体"],
        "nsimsun": ["新宋体", "宋体"],
        "simhei": ["黑体"],
        "msyh": ["微软雅黑"],
        "msyhbd": ["微软雅黑"],
        "msyhl": ["微软雅黑 Light", "Microsoft YaHei Light"],
        "simkai": ["楷体", "楷体_GB2312", "华文楷体"],
        "stkaiti": ["华文楷体", "楷体"],
        "simfang": ["仿宋", "仿宋_GB2312"],
    }

    def __init__(self, config: Config):
        self.config = config
        self._cache: Dict[Tuple[str, int, bool, bool], ImageFont.ImageFont] = {}
        self._font_paths = self._discover_fonts()
        self._cmap_cache: Dict[Tuple[str, int], Optional[set]] = {}
        self._missing_log: list = []

    def font_has_char(self, font: ImageFont.ImageFont, ch: str) -> bool:
        """True if font cmap contains the codepoint (avoids .notdef tofu)."""
        if not ch or ch.isspace():
            return True
        path = getattr(font, "path", None)
        if not path:
            return True
        index = int(getattr(font, "index", 0) or 0)
        cmap = self._get_cmap(path, index)
        if cmap is None:
            return True
        return ord(ch) in cmap

    def _get_cmap(self, path: str, index: int = 0) -> Optional[set]:
        key = (path, index)
        if key in self._cmap_cache:
            return self._cmap_cache[key]
        try:
            from fontTools.ttLib import TTFont
            tt = TTFont(path, fontNumber=index, lazy=True)
            raw = tt.getBestCmap() or {}
            self._cmap_cache[key] = set(raw.keys())
            try:
                tt.close()
            except Exception:
                pass
        except Exception:
            self._cmap_cache[key] = None
        return self._cmap_cache[key]

    def clear_missing_log(self) -> None:
        self._missing_log.clear()

    def _discover_fonts(self) -> Dict[str, str]:
        """Discover available fonts. Keys are lowercase names / stems."""
        font_paths: Dict[str, str] = {}

        def register(name: str, path: str) -> None:
            key = name.lower()
            if key not in font_paths:
                font_paths[key] = path
            alias = self.WINDOWS_ALIASES.get(key)
            if alias and alias.lower() not in font_paths:
                font_paths[alias.lower()] = path
            for local in self.STEM_LOCAL_NAMES.get(key, []):
                if local.lower() not in font_paths:
                    font_paths[local.lower()] = path

        for path in self.config.font_paths:
            if os.path.isfile(path):
                register(Path(path).stem, path)

        for base in (
            Path(__file__).resolve().parent.parent.parent.parent / "fonts",
            Path(__file__).resolve().parent.parent.parent / "fonts",
            Path.cwd() / "fonts",
        ):
            if base.is_dir():
                for f in base.iterdir():
                    if f.suffix.lower() in (".ttf", ".ttc", ".otf"):
                        register(f.stem, str(f))

        system_dirs = []
        if sys.platform == "win32":
            windir = os.environ.get("WINDIR", r"C:\Windows")
            system_dirs.append(os.path.join(windir, "Fonts"))
        elif sys.platform == "darwin":
            system_dirs.extend([
                "/System/Library/Fonts",
                "/Library/Fonts",
                os.path.expanduser("~/Library/Fonts"),
            ])
        else:
            system_dirs.extend([
                "/usr/share/fonts",
                "/usr/local/share/fonts",
                os.path.expanduser("~/.fonts"),
                os.path.expanduser("~/.local/share/fonts"),
            ])

        for sys_dir in system_dirs:
            if not os.path.isdir(sys_dir):
                continue
            for root, _, files in os.walk(sys_dir):
                for f in files:
                    if f.lower().endswith((".ttf", ".ttc", ".otf")):
                        register(Path(f).stem, os.path.join(root, f))

        return font_paths

    def get_font(
        self,
        name: str,
        size: float,
        bold: bool = False,
        italic: bool = False,
    ) -> ImageFont.ImageFont:
        """Get font by family name and size (pixels)."""
        size_i = max(1, int(round(size)))
        key = (name or "", size_i, bold, italic)
        if key in self._cache:
            return self._cache[key]
        font = self._load_font(name or self.config.default_font_ascii, size_i, bold, italic)
        self._cache[key] = font
        return font

    def get_font_for_char(
        self,
        ch: str,
        props,
        size_px: float,
    ) -> ImageFont.ImageFont:
        """Pick a font that actually contains a glyph for ``ch`` (with fallback)."""
        bold = bool(getattr(props, "bold", False)) if props else False
        italic = bool(getattr(props, "italic", False)) if props else False
        size_px = max(1.0, float(size_px))

        is_cjk = bool(ch) and any(
            lo <= ord(ch[0]) <= hi
            for lo, hi in (
                (0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x3000, 0x303F),
                (0xFF00, 0xFFEF), (0x3040, 0x309F), (0x30A0, 0x30FF),
                (0xAC00, 0xD7AF),
            )
        )

        if props is None:
            names = [
                self.config.default_font_east_asia if is_cjk else self.config.default_font_ascii,
                "SimSun", "Microsoft YaHei", "Arial",
            ]
        elif is_cjk:
            names = [
                props.font_east_asia,
                self.config.default_font_east_asia,
                "SimSun", "Microsoft YaHei", "SimHei", "FangSong", "KaiTi",
            ]
        else:
            names = [
                props.font_ascii,
                props.font_h_ansi,
                props.font_east_asia,
                self.config.default_font_ascii,
                "Arial", "Calibri", "Times New Roman",
                "Segoe UI Symbol", "seguisym",
                "SimSun", "Microsoft YaHei",
            ]

        requested = next((n for n in names if n), "Arial")
        for name in names:
            if not name:
                continue
            font = self.get_font(name, size_px, bold, italic)
            if self.font_has_char(font, ch):
                if name != requested and ch.strip():
                    self._missing_log.append((ch, requested, name, getattr(font, "path", "")))
                return font

        font = self.get_font(requested, size_px, bold, italic)
        if ch.strip():
            self._missing_log.append((ch, requested, None, getattr(font, "path", "")))
        return font

    def _load_font(
        self, name: str, size: int, bold: bool, italic: bool
    ) -> ImageFont.ImageFont:
        # Prefer bold YaHei file when name suggests 粗黑 / Bold
        if any(k in (name or "") for k in ("粗黑", "粗体", "Bold", "Heavy")):
            bold = True
        # Normalize localized family names (宋体 → SimSun)
        canonical = name
        for alias_key, target in self.FAMILY_ALIASES.items():
            if alias_key.lower() == (name or "").lower():
                canonical = target
                break

        candidates = [name, canonical]
        candidates.extend(self.FONT_FALLBACKS.get(canonical, []))
        candidates.extend(self.FONT_FALLBACKS.get(name, []))
        candidates.append((canonical or name).replace(" ", ""))

        seen = set()
        uniq = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                uniq.append(c)

        for candidate in uniq:
            path = self._resolve_path(candidate, bold, italic)
            if path:
                try:
                    return ImageFont.truetype(path, size)
                except (IOError, OSError, ValueError):
                    continue

        # Fuzzy match
        name_l = (canonical or name or "").lower()
        for font_name, font_path in self._font_paths.items():
            if name_l and (name_l in font_name or font_name in name_l):
                try:
                    return ImageFont.truetype(font_path, size)
                except (IOError, OSError, ValueError):
                    continue

        # Prefer CJK-capable defaults when the requested name looks East-Asian
        defaults = self._default_font_paths(prefer_cjk=self._looks_cjk_family(name or canonical))
        for fallback_path in defaults:
            if os.path.isfile(fallback_path):
                try:
                    return ImageFont.truetype(fallback_path, size)
                except (IOError, OSError, ValueError):
                    continue

        return ImageFont.load_default()

    @staticmethod
    def _looks_cjk_family(name: str) -> bool:
        if not name:
            return False
        if any("\u4e00" <= ch <= "\u9fff" for ch in name):
            return True
        return name.lower() in {
            "simsun", "simhei", "microsoft yahei", "kaiti", "fangsong",
            "nsimsun", "stsong", "stheiti",
        }

    def _resolve_path(self, name: str, bold: bool, italic: bool) -> Optional[str]:
        """Resolve a font name to a file path, preferring style variants."""
        key = name.lower()
        # Style-suffixed stems on Windows
        style_keys = []
        if bold and italic:
            style_keys = [key + "bi", key + "z", key + "bdital"]
        elif bold:
            style_keys = [key + "bd", key + "b", key + "bold", "msyhbd", "simhei"]
        elif italic:
            style_keys = [key + "i", key + "ital", key + "it"]

        # Family-specific bold files
        if bold:
            if "yahei" in key or "微软雅黑" in key:
                style_keys = ["msyhbd", "msyhbd.ttc", "microsoft yahei bold"] + style_keys
            if "simsun" in key or "宋体" in key:
                style_keys = ["simhei", "msyhbd"] + style_keys

        for sk in style_keys:
            # Do not steal YaHei Bold for unrelated families (e.g. SimHei/兰亭粗黑).
            if sk in ("msyhbd", "msyhbd.ttc", "microsoft yahei bold") and not (
                "yahei" in key or "微软雅黑" in key or key in ("msyh", "msyhbd", "msyhl")
            ):
                continue
            if sk in self._font_paths:
                return self._font_paths[sk]

        if key in self._font_paths:
            return self._font_paths[key]
        # Light variant stem
        if "light" in key and "msyhl" in self._font_paths:
            return self._font_paths["msyhl"]
        return None

    def _default_font_paths(self, prefer_cjk: bool = False) -> list:
        if sys.platform == "win32":
            windir = os.environ.get("WINDIR", r"C:\Windows")
            fonts = os.path.join(windir, "Fonts")
            cjk = [
                os.path.join(fonts, "simsun.ttc"),
                os.path.join(fonts, "msyh.ttc"),
                os.path.join(fonts, "simhei.ttf"),
            ]
            latin = [
                os.path.join(fonts, "arial.ttf"),
                os.path.join(fonts, "times.ttf"),
                os.path.join(fonts, "calibri.ttf"),
            ]
            return cjk + latin if prefer_cjk else latin + cjk
        if sys.platform == "darwin":
            return [
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
                "/Library/Fonts/Arial.ttf",
            ]
        return [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

    def clear_cache(self) -> None:
        self._cache.clear()
