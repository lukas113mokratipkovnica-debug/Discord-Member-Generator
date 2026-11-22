from os import get_terminal_size as _terminal_size

# Credit to billythegoat356 - PyStyle


class _MakeColors:
    @staticmethod
    def _makeansi(col: str, text: str) -> str:
        return f"\033[38;2;{col}m{text}\033[38;2;255;255;255m"

    @staticmethod
    def _rmansi(col: str) -> str:
        return (
            col.replace("\033[38;2;", "")
            .replace("m", "")
            .replace("50m", "")
            .replace("\x1b[38", "")
        )

    @staticmethod
    def _start(color: str) -> str:
        return f"\033[38;2;{color}m"

    @staticmethod
    def _end() -> str:
        return "\033[38;2;255;255;255m"

    @staticmethod
    def _maketext(color: str, text: str, end: bool = False) -> str:
        ending = _MakeColors._end() if end else ""
        return f"{color}{text}{ending}"

    @staticmethod
    def _getspaces(text: str) -> int:
        return len(text) - len(text.lstrip())


class Colors:
    @staticmethod
    def StaticMIX(colors: list[str], _start: bool = True) -> str:
        rgb: list[list[int]] = []
        for col in colors:
            cleaned = _MakeColors._rmansi(col=col)
            parts = cleaned.split(";")
            if len(parts) < 3:
                continue
            try:
                r = int(float(parts[0]))
                g = int(float(parts[1]))
                b = int(float(parts[2]))
                rgb.append([r, g, b])
            except ValueError:
                continue

        if not rgb:
            return _MakeColors._start("255;255;255") if _start else "255;255;255"

        count = len(rgb)
        avg_r = round(sum(c[0] for c in rgb) / count)
        avg_g = round(sum(c[1] for c in rgb) / count)
        avg_b = round(sum(c[2] for c in rgb) / count)
        mixed = f"{avg_r};{avg_g};{avg_b}"
        return _MakeColors._start(mixed) if _start else mixed

    red_to_purple: list[str] = ["255;0;m"]
    col = (list, str)

    dynamic_colors: list[list[str]] = [
        red_to_purple,
    ]

    for _color_group in dynamic_colors:
        if not _color_group:
            continue
        _col = 20
        reversed_col = 220

        dbl_col = 20
        dbl_reversed_col = 220

        _template = _color_group.pop(0)

        for _ in range(12):
            if "m" in _template:
                _color_group.append(_template.replace("m", str(_col)))
            elif "n" in _template:
                _color_group.append(_template.replace("n", str(reversed_col)))
            _col += 20
            reversed_col -= 20

        for _ in range(12):
            if "m" in _template:
                _color_group.append(_template.replace("m", str(dbl_reversed_col)))
            elif "n" in _template:
                _color_group.append(_template.replace("n", str(dbl_col)))
            dbl_col += 20
            dbl_reversed_col -= 20

    all_colors: list[list[str]] = [group for group in dynamic_colors]


class Colorate:
    @staticmethod
    def Color(color: str, text: str, end: bool = True) -> str:
        return _MakeColors._maketext(color=color, text=text, end=end)

    @staticmethod
    def Diagonal(color: list[str], text: str, speed: int = 1, cut: int = 0) -> str:
        sliced = color[cut:] if cut >= 0 else list(color)
        if not sliced:
            return text

        step = max(1, int(speed))
        lines = text.splitlines()
        out_lines: list[str] = []
        color_n = 0

        for line in lines:
            chars = list(line)
            built_line = ""
            for ch in chars:
                current_color = sliced[color_n % len(sliced)]
                spaces = " " * _MakeColors._getspaces(ch)
                built_line += spaces + _MakeColors._makeansi(current_color, ch.strip())
                color_n = (color_n + step) % len(sliced)
            out_lines.append(built_line)

        return "\n".join(out_lines).rstrip()


class Center:
    @staticmethod
    def XCenter(text: str, spaces: int | None = None, icon: str = " ") -> str:
        if spaces is None:
            spaces = Center._xspaces(text=text)
        pad = icon * max(0, spaces)
        return "\n".join(f"{pad}{line}" for line in text.splitlines())

    @staticmethod
    def _xspaces(text: str, fallback_columns: int = 80) -> int:
        try:
            cols = _terminal_size().columns
        except OSError:
            cols = fallback_columns
        lines = text.splitlines()
        longest = max((len(line) for line in lines if line.strip()), default=0)
        return max(0, int((cols - longest) / 2))

    @staticmethod
    def _yspaces(text: str, fallback_lines: int = 24) -> int:
        try:
            rows = _terminal_size().lines
        except OSError:
            rows = fallback_lines
        lines = text.splitlines()
        return max(0, int((rows - len(lines)) / 2))
