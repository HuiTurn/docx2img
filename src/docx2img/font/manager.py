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
        # Carlito is metric-compatible with Calibri (bundled with LibreOffice);
        # prefer it when installed so line breaks match Word/LO closely.
        "Calibri": ["calibri", "Carlito", "carlito", "Arial", "arial", "Helvetica", "sans-serif"],
        "Calibri Light": ["calibri light", "calibril", "Carlito", "carlito", "Calibri", "Arial"],
        # Cambria is a serif face; Caladea is its metric-compatible substitute.
        "Cambria": ["cambria", "Caladea", "caladea", "Times New Roman", "times", "Georgia", "serif"],
        "Cambria Math": ["cambria math", "Cambria", "cambria", "Times New Roman", "times"],
        "Georgia": ["georgia", "Times New Roman", "times", "serif"],
        "Garamond": ["garamond", "EB Garamond", "Georgia", "Times New Roman", "times"],
        "Book Antiqua": ["book antiqua", "Palatino", "palatino", "Times New Roman", "times"],
        "Century Gothic": ["century gothic", "Avant Garde", "Futura", "Arial", "arial"],
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
        self._metrics_cache: Dict[
            Tuple[str, int, int], Tuple[float, float, float]
        ] = {}
        self._missing_log: list = []
        # codepoint -> resolved font path (or None) for glyph-coverage scan
        self._char_font_cache: Dict[int, Optional[str]] = {}

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
            # "Family-Style" stems (e.g. Carlito-Regular, Caladea-BoldItalic):
            # register the bare family and style-suffixed keys used by
            # _resolve_path ("<family>bd", "<family>i", "<family>bi").
            if "-" in name:
                family, _, style = name.rpartition("-")
                fam_key = family.lower()
                style_key = style.lower()
                suffix = {
                    "regular": "", "book": "",
                    "bold": "bd", "italic": "i", "oblique": "i",
                    "bolditalic": "bi", "boldoblique": "bi",
                }.get(style_key)
                if suffix is not None and fam_key:
                    styled = fam_key + suffix
                    if styled not in font_paths:
                        font_paths[styled] = path

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

    def get_font_metrics(
        self,
        name: str,
        size_px: float,
        bold: bool = False,
        italic: bool = False,
    ) -> Tuple[float, float, float]:
        """Return typographic metrics for a resolved font family in pixels.

        The tuple is ``(ascent, descent, line_gap)``.  Uses the same
        font-resolution path as ``get_font`` so callers can compute the natural
        line height that LibreOffice includes in table cells (its default
        behaviour applies the font's own line gap).
        """
        size_px = max(1.0, float(size_px))
        path = self._resolve_family_path(name, bold, italic)
        font_index = 0
        if not path:
            # The requested family may be absent while rendering still found a
            # platform fallback (for example SimSun → Hiragino Sans GB on
            # macOS).  Read metrics from that same fallback instead of silently
            # returning zeros and collapsing its external leading.
            fallback = self.get_font(name, size_px, bold, italic)
            path = getattr(fallback, "path", None)
            font_index = int(getattr(fallback, "index", 0) or 0)
        if not path:
            return (0.0, 0.0, 0.0)
        key = (str(path), font_index, int(round(size_px)))
        if key in self._metrics_cache:
            return self._metrics_cache[key]
        try:
            from fontTools.ttLib import TTFont

            tt = TTFont(path, fontNumber=font_index, lazy=True)
            try:
                upem = tt["head"].unitsPerEm
                hhea = tt["hhea"]
                asc = hhea.ascender * size_px / upem
                desc = abs(hhea.descender) * size_px / upem
                gap = hhea.lineGap * size_px / upem
                res: Tuple[float, float, float] = (asc, desc, gap)
            finally:
                tt.close()
        except Exception:
            res = (0.0, 0.0, 0.0)
        self._metrics_cache[key] = res
        return res

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

        # Last resort: none of the preferred families covers this codepoint.
        # Scan every discovered font for one that does (glyph-coverage based
        # substitution, mirroring LibreOffice / browser behaviour). This keeps
        # symbols like U+2713 ✓ renderable even though the bundled Carlito /
        # Caladea faces lack them, without hardcoding any character.
        scanned = self._find_font_covering(ch, size_px, bold, italic)
        if scanned is not None:
            if ch.strip():
                self._missing_log.append(
                    (ch, requested, "*scan*", getattr(scanned, "path", ""))
                )
            return scanned

        font = self.get_font(requested, size_px, bold, italic)
        if ch.strip():
            self._missing_log.append((ch, requested, None, getattr(font, "path", "")))
        return font

    def _find_font_covering(
        self, ch: str, size_px: float, bold: bool, italic: bool
    ) -> Optional[ImageFont.ImageFont]:
        """Find any discovered font whose cmap covers ``ch``.

        Results are cached per codepoint. Only reached when every preferred
        family fails, so it never overrides normal text metrics; it merely
        rescues exotic symbols that would otherwise render as tofu / nothing.
        """
        cp = ord(ch)
        if cp in self._char_font_cache:
            path = self._char_font_cache[cp]
        else:
            path = None
            seen_paths = set()
            for fp in self._font_paths.values():
                if fp in seen_paths:
                    continue
                seen_paths.add(fp)
                cmap = self._get_cmap(fp, 0)
                if cmap and cp in cmap:
                    path = fp
                    break
            self._char_font_cache[cp] = path
        if not path:
            return None
        try:
            return ImageFont.truetype(path, max(1, int(round(size_px))))
        except (IOError, OSError, ValueError):
            return None

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

    def _resolve_family_path(
        self, name: str, bold: bool, italic: bool
    ) -> Optional[str]:
        """Resolve a family name to a font file, applying alias/fallback chains.

        Mirrors the candidate ordering used by ``_load_font`` (canonical alias,
        FONT_FALLBACKS, space-stripped stem) but returns the file path instead
        of an ImageFont, so metric readers (``get_font_metrics``) resolve the
        same physical file that rendering uses (e.g. Calibri → Carlito).
        """
        canonical = name
        for alias_key, target in self.FAMILY_ALIASES.items():
            if alias_key.lower() == (name or "").lower():
                canonical = target
                break

        candidates = [name, canonical]
        candidates.extend(self.FONT_FALLBACKS.get(canonical, []))
        candidates.extend(self.FONT_FALLBACKS.get(name, []))
        candidates.append((canonical or name or "").replace(" ", ""))

        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            path = self._resolve_path(candidate, bold, italic)
            if path:
                return path
        return None

    def _resolve_path(self, name: str, bold: bool, italic: bool) -> Optional[str]:
        """Resolve a font name to a file path, preferring style variants."""
        key = name.lower().strip()
        stem = self._windows_style_stem(key)
        # Style-suffixed stems on Windows (e.g. times → timesbd / timesi).
        style_keys = []
        stems = [stem] if stem else []
        if key and key not in stems:
            stems.append(key)

        def _style_variants(base: str) -> list:
            if bold and italic:
                return [base + "bi", base + "z", base + "bdital", base + "bold italic"]
            if bold:
                return [base + "bd", base + "b", base + "bold"]
            if italic:
                return [base + "i", base + "ital", base + "it", base + "italic"]
            return []

        for base in stems:
            style_keys.extend(_style_variants(base))

        # Family-specific bold files — CJK only. Never steal SimHei/YaHei Bold
        # for Latin families (that bug mapped Times New Roman Bold → simhei.ttf).
        if bold:
            if "yahei" in key or "微软雅黑" in key or key in ("msyh", "msyhbd", "msyhl"):
                style_keys = [
                    "msyhbd",
                    "msyhbd.ttc",
                    "microsoft yahei bold",
                ] + style_keys
            if (
                "simsun" in key
                or "宋体" in key
                or self._looks_cjk_family(name)
            ) and "yahei" not in key:
                style_keys = ["simhei"] + style_keys

        seen = set()
        for sk in style_keys:
            if not sk or sk in seen:
                continue
            seen.add(sk)
            # Do not steal YaHei Bold for unrelated families.
            if sk in ("msyhbd", "msyhbd.ttc", "microsoft yahei bold") and not (
                "yahei" in key or "微软雅黑" in key or key in ("msyh", "msyhbd", "msyhl")
            ):
                continue
            if sk in self._font_paths:
                return self._font_paths[sk]

        if key in self._font_paths:
            return self._font_paths[key]
        if stem and stem in self._font_paths:
            return self._font_paths[stem]
        # Light variant stem
        if "light" in key and "msyhl" in self._font_paths:
            return self._font_paths["msyhl"]
        return None

    @staticmethod
    def _windows_style_stem(key: str) -> Optional[str]:
        """Map a family name to the Windows short style stem (timesbd, arialbd…)."""
        if not key:
            return None
        mapping = {
            "times new roman": "times",
            "times": "times",
            "courier new": "cour",
            "courier": "cour",
            "arial": "arial",
            "georgia": "georgia",
            "verdana": "verdana",
            "tahoma": "tahoma",
            "comic sans ms": "comic",
            "trebuchet ms": "trebuc",
            "palatino linotype": "pala",
            "lucida console": "lucon",
            "lucida sans unicode": "l_10646",
            "microsoft sans serif": "micross",
            "segoe ui": "segoeui",
            "calibri": "calibri",
            "cambria": "cambria",
            "candara": "candara",
            "consolas": "consola",
            "constantia": "constan",
            "corbel": "corbel",
            "franklin gothic medium": "framd",
        }
        if key in mapping:
            return mapping[key]
        # Already a short stem like "times" / "arial".
        if " " not in key and key.isascii():
            return key
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
            cjk = [
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
            ]
            latin = [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
                "/Library/Fonts/Arial.ttf",
            ]
            return cjk + latin if prefer_cjk else latin + cjk
        return [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

    def clear_cache(self) -> None:
        self._cache.clear()
