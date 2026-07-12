# GraphingOS.py - A TI-84-style graphing calculator OS for Picoware
# (successor of the old Graph.py app)
#
# Screens (soft keys work everywhere, letters work on non-typing screens):
#   HOME    calculation screen: type an expression, Enter evaluates.
#           History above, results right-aligned like a TI-84.
#           "Ans" holds the last result and leading +,*,/,^ chain onto it.
#           Store with "->": e.g. "42->a" then "a*2".  Up/Down recall
#           previous entries.  Empty Enter repeats the last entry.
#   Y=      function editor: Y1..Y6 (function mode), X1T/Y1T..X3T/Y3T
#           (parametric) or r1..r3 (polar).  Tab toggles a slot on/off,
#           Del/F10 clears the line.
#   WINDOW  Xmin/Xmax/Xscl/Ymin/Ymax/Yscl (+ Tmin/Tmax/Tstep for
#           parametric & polar).  Values are expressions: "pi/2" works.
#   ZOOM    ZBox, Zoom In/Out, ZStandard, ZSquare, ZTrig, ZDecimal, ZoomFit
#   GRAPH   free-moving crosshair cursor; window pans when the cursor
#           crosses an edge; +/- zoom about the cursor; R = ZStandard
#   TRACE   cursor rides the curve; Up/Down switch curves; typing a
#           number jumps to X= (or T=); Enter re-centers (quick zoom)
#   CALC    value, zero, minimum, maximum, intersect, dy/dx, integral
#           (function mode; bounds are picked with the trace cursor)
#   TABLE   table of values; Up/Down scroll, +/- halve/double the step,
#           typing a number sets the start
#   MODE    Radian/Degree, Function/Parametric/Polar, Grid, Axes, Labels
#
# Key map:
#   F2:Y=  F3:WINDOW  F4:ZOOM  F5:TRACE  F6:GRAPH  F7:TABLE  F8:MODE
#   F9: CATALOG while editing (inserts a function), CALC menu on a graph
#   Esc: back to HOME, and from HOME exits the app.  On screens without
#   text entry the letters y/w/z/t/g/b/m/c/h jump between screens.
#   (HOME and F1 are reserved by the ViewManager: exit and screenshot.)
#
# Expressions are Python with a math whitelist plus TI conveniences:
# ^ means power, implicit multiplication ("2x", "3(x+1)", "2pi") and
# single-letter variables a-z.  In Degree mode sin/cos/tan take degrees
# and asin/acos/atan return degrees.  State (functions, window, vars,
# history, mode) persists to SD between runs.

from array import array
import math

from picoware.system.buttons import (
    BUTTON_NONE,
    BUTTON_BACK,
    BUTTON_UP,
    BUTTON_DOWN,
    BUTTON_LEFT,
    BUTTON_RIGHT,
    BUTTON_CENTER,
    BUTTON_ENTER,
    BUTTON_BACKSPACE,
    BUTTON_DELETE,
    BUTTON_TAB,
    BUTTON_END,
    BUTTON_F2,
    BUTTON_F3,
    BUTTON_F4,
    BUTTON_F5,
    BUTTON_F6,
    BUTTON_F7,
    BUTTON_F8,
    BUTTON_F9,
    BUTTON_F10,
    BUTTON_PLUS,
    BUTTON_EQUAL,
    BUTTON_MINUS,
    BUTTON_UNDERSCORE,
    BUTTON_1,
    BUTTON_B,
    BUTTON_C,
    BUTTON_G,
    BUTTON_H,
    BUTTON_M,
    BUTTON_R,
    BUTTON_T,
    BUTTON_W,
    BUTTON_Y,
    BUTTON_Z,
)
from picoware.system.colors import (
    TFT_BLACK,
    TFT_WHITE,
    TFT_BLUE,
    TFT_RED,
    TFT_GREEN,
    TFT_YELLOW,
    TFT_CYAN,
    TFT_MAGENTA,
    TFT_ORANGE,
    TFT_SKYBLUE,
    TFT_DARKGREY,
    TFT_LIGHTGREY,
    TFT_DARKGREEN,
)

# ---------------------------------------------------------------- constants

SCR_HOME = 0
SCR_YEQ = 1
SCR_WINDOW = 2
SCR_ZOOM = 3
SCR_GRAPH = 4
SCR_TRACE = 5
SCR_TABLE = 6
SCR_MODE = 7
SCR_CALC_MENU = 8
SCR_CALC = 9
SCR_CATALOG = 10
SCR_MENU = 11

MODE_FUNC = 0
MODE_PAR = 1
MODE_POL = 2

NFUNC = 6  # Y1..Y6
NPAIR = 3  # parametric pairs
NPOL = 3  # polar functions

SLOT_COLORS = (TFT_GREEN, TFT_YELLOW, TFT_CYAN, TFT_MAGENTA, TFT_ORANGE, TFT_SKYBLUE)
DEF_WIN = (-10.0, 10.0, -10.0, 10.0)
MIN_SPAN = 1e-6
MAX_SPAN = 1e12
NAN = float("nan")
TWO_PI = 2.0 * math.pi
D2R = math.pi / 180.0
R2D = 180.0 / math.pi
MAX_TSAMP = 481  # cap on parametric/polar sample count
MAX_HIST = 24
STATE_FILE = "picoware/settings/graphingos.json"

# names that may be followed by "(" without implicit multiplication
_FUNC_NAMES = (
    "abs",
    "min",
    "max",
    "pow",
    "round",
    "int",
    "float",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "atan2",
    "sinh",
    "cosh",
    "tanh",
    "ln",
    "log",
    "log10",
    "exp",
    "sqrt",
    "floor",
    "ceil",
    "degrees",
    "radians",
    "fact",
    "fmod",
)

# (text inserted, description) pairs for the F9 catalog
_CATALOG = (
    ("sin(", "sine"),
    ("cos(", "cosine"),
    ("tan(", "tangent"),
    ("asin(", "arcsine"),
    ("acos(", "arccosine"),
    ("atan(", "arctangent"),
    ("atan2(", "atan2(y,x)"),
    ("sinh(", "hyperbolic sine"),
    ("cosh(", "hyperbolic cosine"),
    ("tanh(", "hyperbolic tangent"),
    ("ln(", "natural log"),
    ("log(", "natural log"),
    ("log10(", "base-10 log"),
    ("exp(", "e^x"),
    ("sqrt(", "square root"),
    ("abs(", "absolute value"),
    ("floor(", "round down"),
    ("ceil(", "round up"),
    ("round(", "round(x[,n])"),
    ("min(", "minimum"),
    ("max(", "maximum"),
    ("fact(", "factorial"),
    ("fmod(", "fmod(x,y)"),
    ("degrees(", "rad to deg"),
    ("radians(", "deg to rad"),
    ("pi", "3.14159..."),
    ("e", "2.71828..."),
    ("ans", "last answer"),
    ("->", "store: 5->a"),
)

_ZOOM_ITEMS = (
    "1:ZBox",
    "2:Zoom In",
    "3:Zoom Out",
    "4:ZStandard",
    "5:ZSquare",
    "6:ZTrig",
    "7:ZDecimal",
    "8:ZoomFit",
)

_CALC_ITEMS = (
    "1:value",
    "2:zero",
    "3:minimum",
    "4:maximum",
    "5:intersect",
    "6:dy/dx",
    "7:integral f(x)dx",
)

_MODE_ROWS = (
    ("ANGLE", ("RADIAN", "DEGREE")),
    ("TYPE", ("FUNCTION", "PARAMETRIC", "POLAR")),
    ("GRID", ("ON", "OFF")),
    ("AXES", ("ON", "OFF")),
    ("LABELS", ("ON", "OFF")),
)

_MENU_ITEMS = (
    ("Y= editor", SCR_YEQ),
    ("Window", SCR_WINDOW),
    ("Zoom", SCR_ZOOM),
    ("Graph", SCR_GRAPH),
    ("Trace", SCR_TRACE),
    ("Table", SCR_TABLE),
    ("Mode", SCR_MODE),
    ("Catalog", SCR_CATALOG),
)

# ---------------------------------------------------------------- state

_scr = SCR_HOME
_env = None
_vm = None

# mode settings
_deg = False
_gmode = MODE_FUNC
_grid = True
_axes = True
_labels = True

# home screen
_hist = None  # list of [entry, result, is_err]
_hed = None  # edit buffer dict {"b": [chars], "c": cursor, "v": virgin}
_hrecall = -1

# Y= slots (per graph mode)
_fslots = None
_pslots = None
_rslots = None
_ysel = 0

# window
_win = None  # [xmin, xmax, ymin, ymax]
_xscl = 1.0
_yscl = 1.0
_tmin = 0.0
_tmax = TWO_PI
_tstep = 0.05
_wsel = 0
_weds = None  # list of edit dicts, one per field
_werr = -1

# samples
_fsamps = None  # per func slot: array('f') of y per pixel column
_xysamps = None  # per par/pol curve: (xs, ys) arrays

# graph / trace / calc
_gpx = 0  # free cursor, pixels
_gpy = 0
_tr_fn = 0
_tr_i = 0
_zsel = 0
_pzoom = 0.0  # pending Zoom In/Out factor (0 = none)
_zbox = None  # None or [stage, px0, py0]
_csel = 0
_calc_op = ""
_calc_stage = 0
_calc_x1 = 0.0
_calc_fn2 = 0
_calc_msg = ""
_calc_mark = None  # (x, y) result marker
_calc_shade = None  # (fn, px0, px1) integral shading
_calc_tan = None  # (x, y, slope) tangent line

# table
_tbl_start = 0.0
_tbl_step = 1.0

# catalog / menu popups
_cat_sel = 0
_cat_from = SCR_HOME
_menu_sel = 0
_msel = 0  # MODE screen row

# text prompt overlay: {"label","ed","cb"} or None
_prompt = None

# flags
_plot_dirty = False
_draw_dirty = False
_flash = ""  # transient one-line message on graph screens

# layout (physical pixels, computed in start)
_W = 320
_H = 320
_CW = 6
_CH = 8
_ROW = 11


# ---------------------------------------------------------------- helpers


def _new_ed(text=""):
    return {"b": list(text), "c": len(text), "v": False}


def _ed_text(ed):
    return "".join(ed["b"])


def _ed_set(ed, text, virgin=False):
    ed["b"] = list(text)
    ed["c"] = len(ed["b"])
    ed["v"] = virgin


def _new_slot(text=""):
    return {"ed": _new_ed(text), "on": True, "code": None, "err": None}


def _fmt(v):
    """Compact number label for axes."""
    if v == 0:
        return "0"
    if abs(v) < 1e7 and v == int(v):
        return "%d" % int(v)
    return "%.4g" % v


def _fmt_val(v):
    """Result formatting, TI-style 10 significant digits."""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v:
            return "undef"
        if abs(v) < 1e15 and v == int(v):
            return "%d" % int(v)
        return "%.10g" % v
    return str(v)


def _fmt_short(v):
    if v != v:
        return "undef"
    return "%.6g" % v


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _alnum(ch):
    # MicroPython's str has no isalnum()
    return ch.isalpha() or ch.isdigit()


# ---------------------------------------------------------------- expression engine


def _build_env():
    env = {
        "abs": abs,
        "min": min,
        "max": max,
        "pow": pow,
        "round": round,
        "int": int,
        "float": float,
        "atan2": math.atan2,
        "ln": math.log,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "sqrt": math.sqrt,
        "pi": math.pi,
        "e": math.e,
        "floor": math.floor,
        "ceil": math.ceil,
        "sinh": math.sinh,
        "cosh": math.cosh,
        "tanh": math.tanh,
        "degrees": math.degrees,
        "radians": math.radians,
        "fmod": math.fmod,
        "math": math,
        "ans": 0.0,
    }
    fact = getattr(math, "factorial", None)
    if fact is None:
        fact = getattr(math, "gamma", None)
        if fact is not None:
            gamma = fact

            def fact(n):
                return gamma(n + 1.0)

    if fact is not None:
        env["fact"] = fact
    for c in "abcdfghijklmnopqrstuvwxyz":  # e stays Euler's number
        env[c] = 0.0
    env["theta"] = 0.0
    return env


def _set_angle_env():
    """Install radian or degree trig into the shared environment."""
    if _deg:
        _env["sin"] = lambda v: math.sin(v * D2R)
        _env["cos"] = lambda v: math.cos(v * D2R)
        _env["tan"] = lambda v: math.tan(v * D2R)
        _env["asin"] = lambda v: math.asin(v) * R2D
        _env["acos"] = lambda v: math.acos(v) * R2D
        _env["atan"] = lambda v: math.atan(v) * R2D
    else:
        _env["sin"] = math.sin
        _env["cos"] = math.cos
        _env["tan"] = math.tan
        _env["asin"] = math.asin
        _env["acos"] = math.acos
        _env["atan"] = math.atan


def _preprocess(text):
    """TI conveniences: ^ power and implicit multiplication."""
    text = text.replace("^", "**")
    out = []
    n = len(text)
    for i in range(n):
        ch = text[i]
        if out and (ch == "(" or ch.isalpha() or ch.isdigit()):
            p = out[-1]
            if p == ")":
                if ch == "(" or ch.isalpha() or ch.isdigit():
                    out.append("*")
            elif p.isdigit() and (ch == "(" or ch.isalpha()):
                # "2x" -> "2*x" but "log10(" stays a function call and
                # "1e5" stays scientific notation
                sci = (
                    ch in "eE"
                    and i + 1 < n
                    and (text[i + 1].isdigit() or text[i + 1] in "+-")
                )
                j = len(out) - 1
                pure_number = True
                while j >= 0 and (_alnum(out[j]) or out[j] in "._"):
                    if out[j].isalpha() or out[j] == "_":
                        pure_number = False
                        break
                    j -= 1
                if pure_number and not sci:
                    out.append("*")
            elif p.isalpha() and ch == "(":
                # "x(" -> "x*(" unless a known function name precedes
                j = len(out) - 1
                ident = []
                while j >= 0 and (_alnum(out[j]) or out[j] == "_"):
                    ident.append(out[j])
                    j -= 1
                name = "".join(reversed(ident))
                if name not in _FUNC_NAMES:
                    out.append("*")
        out.append(ch)
    return "".join(out)


def _err_name(exc):
    if isinstance(exc, SyntaxError):
        return "ERR:SYNTAX"
    if isinstance(exc, ZeroDivisionError):
        return "ERR:DIVIDE BY 0"
    if isinstance(exc, ValueError):
        return "ERR:DOMAIN"
    if isinstance(exc, NameError):
        return "ERR:UNDEFINED"
    if isinstance(exc, OverflowError):
        return "ERR:OVERFLOW"
    if isinstance(exc, TypeError):
        return "ERR:DATA TYPE"
    return "ERR:" + exc.__class__.__name__


def _eval_number(text):
    """Evaluate an expression to a finite float. Returns (value, err)."""
    text = text.strip()
    if not text:
        return None, "ERR:SYNTAX"
    try:
        v = eval(_preprocess(text), _env)
        v = float(v)
        if not math.isfinite(v):
            return None, "ERR:OVERFLOW"
        return v, None
    except Exception as exc:
        return None, _err_name(exc)


def _home_eval(text):
    """Evaluate a HOME entry (with -> store). Returns (result, is_err)."""
    text = text.strip()
    # leading operator chains onto Ans, like a TI
    if text and text[0] in "+*/^":
        text = "ans" + text
    # store: "expr->a"
    target = None
    pos = text.rfind("->")
    if pos >= 0:
        target = text[pos + 2 :].strip()
        expr = text[:pos].strip()
        if len(target) != 1 or not target.isalpha():
            return "ERR:STORE TARGET", True
        if target == "e":
            return "ERR:RESERVED NAME", True
        text = expr
    try:
        v = eval(_preprocess(text), _env)
    except Exception as exc:
        return _err_name(exc), True
    if isinstance(v, (int, float, bool)):
        _env["ans"] = float(v)
        if target:
            _env[target] = float(v)
        return _fmt_val(v), False
    return _fmt_val(v), False


# ---------------------------------------------------------------- slots


def _slots_for_mode():
    if _gmode == MODE_PAR:
        return _pslots
    if _gmode == MODE_POL:
        return _rslots
    return _fslots


def _slot_label(i):
    if _gmode == MODE_PAR:
        return ("X%dT=" if i % 2 == 0 else "Y%dT=") % (i // 2 + 1)
    if _gmode == MODE_POL:
        return "r%d=" % (i + 1)
    return "Y%d=" % (i + 1)


def _slot_color(i):
    if _gmode == MODE_PAR:
        return SLOT_COLORS[i // 2]
    return SLOT_COLORS[i]


def _compile_slots():
    """Compile all slots of the current mode; record per-slot errors."""
    for i, slot in enumerate(_slots_for_mode()):
        slot["code"] = None
        slot["err"] = None
        text = _ed_text(slot["ed"]).strip()
        if not text:
            continue
        try:
            slot["code"] = compile(_preprocess(text), _slot_label(i), "eval")
        except SyntaxError:
            slot["err"] = "syntax error"
        except Exception as exc:
            slot["err"] = str(exc)


def _curve_list():
    """Indices of curves that currently have samples to draw/trace."""
    out = []
    if _gmode == MODE_FUNC:
        for i in range(NFUNC):
            if _fsamps[i] is not None and _fslots[i]["on"]:
                out.append(i)
    else:
        for i in range(len(_xysamps)):
            if _xysamps[i] is not None:
                out.append(i)
    return out


# ---------------------------------------------------------------- mapping


def _plot_h():
    return _H - (2 * _ROW + 4)


def _px2x(px):
    return _win[0] + px * (_win[1] - _win[0]) / (_W - 1)


def _x2px(x):
    return (x - _win[0]) / (_win[1] - _win[0]) * (_W - 1)


def _py2y(py, ph):
    return _win[3] - py * (_win[3] - _win[2]) / (ph - 1)


def _y2py(y, ph):
    return (_win[3] - y) / (_win[3] - _win[2]) * (ph - 1)


def _nice_step(span):
    """1-2-5 tick step so the window shows roughly 6 intervals."""
    raw = span / 6.0
    mag = 10.0 ** math.floor(math.log10(raw))
    n = raw / mag
    if n < 1.5:
        s = 1.0
    elif n < 3.5:
        s = 2.0
    elif n < 7.5:
        s = 5.0
    else:
        s = 10.0
    return s * mag


# ---------------------------------------------------------------- sampling


def _t_samples():
    if _tstep <= 0:
        return 2
    n = int((_tmax - _tmin) / _tstep) + 1
    return _clamp(n, 2, MAX_TSAMP)


def _recompute():
    """Re-evaluate every enabled curve over the current window."""
    global _xysamps
    env = _env
    if _gmode == MODE_FUNC:
        for s in range(NFUNC):
            slot = _fslots[s]
            if slot["code"] is None or not slot["on"]:
                _fsamps[s] = None
                continue
            arr = _fsamps[s]
            if arr is None:
                arr = array("f", bytes(4 * _W))
                _fsamps[s] = arr
            code = slot["code"]
            for px in range(_W):
                env["x"] = _px2x(px)
                try:
                    y = eval(code, env)
                    if isinstance(y, (int, float)) and math.isfinite(y):
                        arr[px] = y
                    else:
                        arr[px] = NAN
                except Exception:
                    arr[px] = NAN
        return

    n = _t_samples()
    span = _tmax - _tmin
    curves = []
    if _gmode == MODE_PAR:
        for p in range(NPAIR):
            sx = _pslots[2 * p]
            sy = _pslots[2 * p + 1]
            if (
                sx["code"] is None
                or sy["code"] is None
                or not sx["on"]
                or not sy["on"]
            ):
                curves.append(None)
                continue
            xs = array("f", bytes(4 * n))
            ys = array("f", bytes(4 * n))
            for i in range(n):
                t = _tmin + span * i / (n - 1)
                env["t"] = t
                env["theta"] = t
                try:
                    x = eval(sx["code"], env)
                    y = eval(sy["code"], env)
                    if (
                        isinstance(x, (int, float))
                        and isinstance(y, (int, float))
                        and math.isfinite(x)
                        and math.isfinite(y)
                    ):
                        xs[i] = x
                        ys[i] = y
                    else:
                        xs[i] = NAN
                        ys[i] = NAN
                except Exception:
                    xs[i] = NAN
                    ys[i] = NAN
            curves.append((xs, ys))
    else:  # polar
        for p in range(NPOL):
            slot = _rslots[p]
            if slot["code"] is None or not slot["on"]:
                curves.append(None)
                continue
            xs = array("f", bytes(4 * n))
            ys = array("f", bytes(4 * n))
            for i in range(n):
                t = _tmin + span * i / (n - 1)
                env["t"] = t
                env["theta"] = t
                try:
                    r = eval(slot["code"], env)
                    if isinstance(r, (int, float)) and math.isfinite(r):
                        a = t * D2R if _deg else t
                        xs[i] = r * math.cos(a)
                        ys[i] = r * math.sin(a)
                    else:
                        xs[i] = NAN
                        ys[i] = NAN
                except Exception:
                    xs[i] = NAN
                    ys[i] = NAN
            curves.append((xs, ys))
    _xysamps = curves


def _feval(fn, x):
    """Evaluate function slot fn at x; returns float or None."""
    slot = _fslots[fn]
    if slot["code"] is None:
        return None
    _env["x"] = x
    try:
        y = eval(slot["code"], _env)
        if isinstance(y, (int, float)) and math.isfinite(y):
            return float(y)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- plot rendering


def _draw_grid(fb, ph):
    xmin, xmax, ymin, ymax = _win

    if _grid:
        step = _nice_step(xmax - xmin)
        tick = math.ceil(xmin / step) * step
        last_end = -1
        while tick <= xmax:
            px = int(_x2px(tick))
            if 0 <= px < _W:
                fb._line(px, 0, px, ph - 1, TFT_DARKGREY)
                if _labels:
                    label = _fmt(tick)
                    lx = px + 2
                    if lx > last_end and lx + len(label) * _CW < _W:
                        fb._text(lx, ph - _CH - 1, label, TFT_LIGHTGREY)
                        last_end = lx + len(label) * _CW + 2
            tick += step

        step = _nice_step(ymax - ymin)
        tick = math.ceil(ymin / step) * step
        while tick <= ymax:
            py = int(_y2py(tick, ph))
            if 0 <= py < ph:
                fb._line(0, py, _W - 1, py, TFT_DARKGREY)
                if _labels and tick != 0:
                    fb._text(2, py + 1, _fmt(tick), TFT_LIGHTGREY)
            tick += step

    if _axes:
        if xmin <= 0.0 <= xmax:
            px = int(_x2px(0.0))
            fb._line(px, 0, px, ph - 1, TFT_BLUE)
            # y tick marks every Yscl
            if _yscl > 0 and (ymax - ymin) / _yscl < 200:
                tick = math.ceil(ymin / _yscl) * _yscl
                while tick <= ymax:
                    py = int(_y2py(tick, ph))
                    if 0 <= py < ph:
                        fb._line(px - 2, py, px + 2, py, TFT_BLUE)
                    tick += _yscl
        if ymin <= 0.0 <= ymax:
            py = int(_y2py(0.0, ph))
            fb._line(0, py, _W - 1, py, TFT_BLUE)
            if _xscl > 0 and (xmax - xmin) / _xscl < 200:
                tick = math.ceil(xmin / _xscl) * _xscl
                while tick <= xmax:
                    px = int(_x2px(tick))
                    if 0 <= px < _W:
                        fb._line(px, py - 2, px, py + 2, TFT_BLUE)
                    tick += _xscl

    fb._rectangle(0, 0, _W, ph, TFT_BLUE)


def _draw_segment(fb, px0, py0, px1, py1, ph, color):
    """One curve segment, skipping discontinuities and clipping."""
    if py0 != py0 or py1 != py1:  # NaN sample
        return
    if abs(py1 - py0) > ph:  # discontinuity (e.g. tan asymptote)
        return
    if (py0 < 0 and py1 < 0) or (py0 >= ph and py1 >= ph):
        return
    py0 = 0 if py0 < 0 else (ph - 1 if py0 >= ph else int(py0))
    py1 = 0 if py1 < 0 else (ph - 1 if py1 >= ph else int(py1))
    fb._line(px0, py0, px1, py1, color)


def _draw_curves(fb, ph):
    if _gmode == MODE_FUNC:
        for i in range(NFUNC):
            arr = _fsamps[i]
            if arr is None or not _fslots[i]["on"]:
                continue
            color = SLOT_COLORS[i]
            for px in range(1, _W):
                _draw_segment(
                    fb,
                    px - 1,
                    _y2py(arr[px - 1], ph),
                    px,
                    _y2py(arr[px], ph),
                    ph,
                    color,
                )
        return
    for ci in range(len(_xysamps)):
        cur = _xysamps[ci]
        if cur is None:
            continue
        xs, ys = cur
        color = SLOT_COLORS[ci]
        prev = None
        for i in range(len(xs)):
            x = xs[i]
            y = ys[i]
            if x != x or y != y:
                prev = None
                continue
            pt = (_x2px(x), _y2py(y, ph))
            if prev is not None:
                px0 = int(prev[0])
                px1 = int(pt[0])
                if 0 <= px0 < _W and 0 <= px1 < _W:
                    _draw_segment(fb, px0, prev[1], px1, pt[1], ph, color)
            prev = pt


def _legend(fb):
    labels = []
    curves = _curve_list()
    for i in curves:
        if _gmode == MODE_PAR:
            label = "P%d" % (i + 1)
            color = SLOT_COLORS[i]
        elif _gmode == MODE_POL:
            label = "r%d" % (i + 1)
            color = SLOT_COLORS[i]
        else:
            label = "Y%d" % (i + 1)
            color = SLOT_COLORS[i]
        if _scr in (SCR_TRACE, SCR_CALC) and i == _tr_fn:
            label = ">" + label
        labels.append((label, color))
    x = _W - 2 - sum((len(l) + 1) * _CW for l, _ in labels)
    for label, color in labels:
        fb._text(x, 2, label, color)
        x += (len(label) + 1) * _CW


def _crosshair(fb, px, py, ph, color):
    if not (0 <= px < _W):
        return
    py = _clamp(py, 0, ph - 1)
    fb._line(px - 5, py, px + 5, py, color)
    fb._line(px, py - 5, px, py + 5, color)


def _trace_pos():
    """Current trace cursor -> (x, y, indep) in graph coords."""
    if _gmode == MODE_FUNC:
        x = _px2x(_tr_i)
        arr = _fsamps[_tr_fn]
        y = arr[_tr_i] if arr is not None else NAN
        return x, y, x
    cur = _xysamps[_tr_fn] if _tr_fn < len(_xysamps) else None
    if cur is None:
        return NAN, NAN, NAN
    xs, ys = cur
    n = len(xs)
    i = _clamp(_tr_i, 0, n - 1)
    t = _tmin + (_tmax - _tmin) * i / (n - 1)
    return xs[i], ys[i], t


def _panel(fb, ph, line1, line2, color1=TFT_WHITE, color2=TFT_DARKGREY):
    fb._fill_rectangle(0, ph, _W, _H - ph, TFT_BLACK)
    fb._text(4, ph + 2, line1[: (_W - 8) // _CW], color1)
    fb._text(4, ph + 2 + _ROW, line2[: (_W - 8) // _CW], color2)


def _win_status():
    return "x[%s,%s] y[%s,%s]" % (
        _fmt(_win[0]),
        _fmt(_win[1]),
        _fmt(_win[2]),
        _fmt(_win[3]),
    )


# ---------------------------------------------------------------- text UI helpers


def _bar(fb):
    """Top status bar; returns content start y."""
    fb._fill_rectangle(0, 0, _W, _ROW, TFT_DARKGREY)
    titles = {
        SCR_HOME: "GraphingOS",
        SCR_YEQ: "Y= EDITOR",
        SCR_WINDOW: "WINDOW",
        SCR_ZOOM: "ZOOM",
        SCR_TABLE: "TABLE",
        SCR_MODE: "MODE",
        SCR_CALC_MENU: "CALCULATE",
        SCR_CATALOG: "CATALOG",
        SCR_MENU: "MENU",
    }
    fb._text(4, 2, titles.get(_scr, "GraphingOS"), TFT_WHITE)
    right = ("FUNC", "PAR", "POL")[_gmode] + (" DEG" if _deg else " RAD")
    fb._text(_W - 2 - len(right) * _CW, 2, right, TFT_YELLOW)
    return _ROW + 2


def _hint(fb, text):
    y = _H - _ROW
    fb._fill_rectangle(0, y, _W, _ROW, TFT_BLACK)
    fb._line(0, y, _W - 1, y, TFT_DARKGREY)
    fb._text(2, y + 2, text[: (_W - 4) // _CW], TFT_DARKGREY)


def _edit_row(fb, y, prefix, ed, selected, color, text_color=TFT_WHITE):
    """One editable row with horizontal scroll and cursor."""
    maxchars = (_W - 8) // _CW - len(prefix)
    cur = ed["c"]
    start = 0
    if selected and cur > maxchars - 1:
        start = cur - (maxchars - 1)
    text = "".join(ed["b"][start : start + maxchars])
    fb._text(4, y, prefix, color)
    tx = 4 + len(prefix) * _CW
    fb._text(tx, y, text, text_color)
    if selected:
        cx = tx + (cur - start) * _CW
        fb._fill_rectangle(cx, y + _CH, _CW, 2, TFT_WHITE)


def _edit_key(ed, btn, inp):
    """Shared line-editing keys. Returns True if the key was consumed."""
    if btn == BUTTON_LEFT:
        if ed["c"] > 0:
            ed["c"] -= 1
        ed["v"] = False
        return True
    if btn == BUTTON_RIGHT:
        if ed["c"] < len(ed["b"]):
            ed["c"] += 1
        ed["v"] = False
        return True
    if btn == BUTTON_END:
        ed["c"] = len(ed["b"])
        ed["v"] = False
        return True
    if btn == BUTTON_BACKSPACE:
        if ed["v"]:
            _ed_set(ed, "")
        elif ed["c"] > 0:
            ed["b"].pop(ed["c"] - 1)
            ed["c"] -= 1
        return True
    if btn in (BUTTON_DELETE, BUTTON_F10):
        _ed_set(ed, "")
        return True
    ch = inp.button_to_char(btn)
    if ch and ch != "\n":
        if ed["v"]:
            _ed_set(ed, "")
        ed["b"].insert(ed["c"], ch)
        ed["c"] += 1
        return True
    return False


def _ed_insert(ed, text):
    if ed["v"]:
        _ed_set(ed, "")
    for ch in text:
        ed["b"].insert(ed["c"], ch)
        ed["c"] += 1


# ---------------------------------------------------------------- screen renderers


def _render_home(fb):
    y0 = _bar(fb)
    bottom = _H - _ROW
    # build display lines: entry left / result right for each history item
    lines = []
    for item in _hist:
        lines.append(("L", item[0], TFT_WHITE))
        lines.append(("R", item[1], TFT_RED if item[2] else TFT_LIGHTGREY))
    nrows = (bottom - y0) // _ROW - 1  # keep one row for the edit line
    lines = lines[-nrows:] if nrows > 0 else []
    y = y0
    maxchars = (_W - 8) // _CW
    for side, text, color in lines:
        if len(text) > maxchars:
            text = text[: maxchars - 1] + "~"
        if side == "L":
            fb._text(4, y, text, color)
        else:
            fb._text(_W - 4 - len(text) * _CW, y, text, color)
        y += _ROW
    _edit_row(fb, y, "", _hed, True, TFT_WHITE)
    _hint(fb, "F2:Y= F3:WIN F4:ZOOM F6:GRPH F7:TABL F8:MODE F9:CAT")


def _render_yeq(fb):
    y0 = _bar(fb)
    slots = _slots_for_mode()
    y = y0
    err = None
    for i, slot in enumerate(slots):
        color = _slot_color(i) if slot["on"] else TFT_DARKGREY
        text_color = TFT_WHITE if slot["on"] else TFT_DARKGREY
        _edit_row(fb, y, _slot_label(i), slot["ed"], i == _ysel, color, text_color)
        if err is None and slot["err"]:
            err = "%s %s" % (_slot_label(i), slot["err"])
        y += _ROW
    if err:
        fb._text(4, y + 2, err[: (_W - 8) // _CW], TFT_RED)
    _hint(fb, "Tab:on/off Del:clear F9:cat Enter/F6:graph")


def _win_fields():
    if _gmode == MODE_FUNC:
        return ("Xmin=", "Xmax=", "Xscl=", "Ymin=", "Ymax=", "Yscl=")
    return (
        "Tmin=",
        "Tmax=",
        "Tstep=",
        "Xmin=",
        "Xmax=",
        "Xscl=",
        "Ymin=",
        "Ymax=",
        "Yscl=",
    )


def _win_values():
    if _gmode == MODE_FUNC:
        return (_win[0], _win[1], _xscl, _win[2], _win[3], _yscl)
    return (_tmin, _tmax, _tstep, _win[0], _win[1], _xscl, _win[2], _win[3], _yscl)


def _win_apply(idx, val):
    """Store a committed WINDOW field. Returns error string or None."""
    global _xscl, _yscl, _tmin, _tmax, _tstep
    names = _win_fields()
    name = names[idx]
    if name == "Xmin=":
        if val >= _win[1]:
            return "Xmin must be < Xmax"
        _win[0] = val
    elif name == "Xmax=":
        if val <= _win[0]:
            return "Xmax must be > Xmin"
        _win[1] = val
    elif name == "Ymin=":
        if val >= _win[3]:
            return "Ymin must be < Ymax"
        _win[2] = val
    elif name == "Ymax=":
        if val <= _win[2]:
            return "Ymax must be > Ymin"
        _win[3] = val
    elif name == "Xscl=":
        _xscl = abs(val)
    elif name == "Yscl=":
        _yscl = abs(val)
    elif name == "Tmin=":
        _tmin = val
    elif name == "Tmax=":
        _tmax = val
    elif name == "Tstep=":
        if val <= 0:
            return "Tstep must be > 0"
        _tstep = val
    return None


def _win_editors():
    """(Re)build the WINDOW edit buffers from current values."""
    global _weds, _wsel, _werr
    _weds = [_new_ed(_fmt_val(v)) for v in _win_values()]
    for ed in _weds:
        ed["v"] = True  # first keystroke replaces the value
    _wsel = 0
    _werr = -1


def _win_commit(idx):
    """Evaluate + apply one WINDOW field. Returns True on success."""
    global _werr
    text = _ed_text(_weds[idx])
    val, err = _eval_number(text)
    if err is not None:
        _werr = idx
        return False
    err = _win_apply(idx, val)
    if err is not None:
        _werr = idx
        return False
    if _werr == idx:
        _werr = -1
    _ed_set(_weds[idx], _fmt_val(_win_values()[idx]), True)
    return True


def _render_window(fb):
    y0 = _bar(fb)
    names = _win_fields()
    y = y0
    for i, name in enumerate(names):
        color = TFT_RED if i == _werr else (TFT_CYAN if i == _wsel else TFT_LIGHTGREY)
        _edit_row(fb, y, name, _weds[i], i == _wsel, color)
        y += _ROW
    if _werr >= 0:
        fb._text(4, y + 2, "invalid value", TFT_RED)
    _hint(fb, "Up/Dn:field  type value (pi/2 ok)  Enter:set")


def _render_list(fb, items, sel):
    y0 = _bar(fb)
    y = y0
    for i, item in enumerate(items):
        if i == sel:
            fb._fill_rectangle(0, y - 1, _W, _ROW, TFT_BLUE)
        fb._text(6, y, item, TFT_WHITE if i == sel else TFT_LIGHTGREY)
        y += _ROW


def _render_zoom(fb):
    _render_list(fb, _ZOOM_ITEMS, _zsel)
    _hint(fb, "Up/Dn+Enter or press 1-8")


def _render_calc_menu(fb):
    _render_list(fb, _CALC_ITEMS, _csel)
    _hint(fb, "Up/Dn+Enter or press 1-7")


def _render_menu(fb):
    _render_list(fb, [item[0] for item in _MENU_ITEMS], _menu_sel)
    _hint(fb, "Up/Dn+Enter  Esc:home")


def _render_catalog(fb):
    y0 = _bar(fb)
    bottom = _H - _ROW
    nrows = (bottom - y0) // _ROW
    top = _clamp(_cat_sel - nrows + 1, 0, max(0, len(_CATALOG) - nrows))
    if _cat_sel < top:
        top = _cat_sel
    y = y0
    for i in range(top, min(len(_CATALOG), top + nrows)):
        ins, desc = _CATALOG[i]
        if i == _cat_sel:
            fb._fill_rectangle(0, y - 1, _W, _ROW, TFT_BLUE)
        fb._text(6, y, ins, TFT_WHITE)
        fb._text(_W // 2, y, desc, TFT_LIGHTGREY)
        y += _ROW
    _hint(fb, "Enter:insert  Esc:cancel")


def _render_mode(fb):
    y0 = _bar(fb)
    current = (
        1 if _deg else 0,
        _gmode,
        0 if _grid else 1,
        0 if _axes else 1,
        0 if _labels else 1,
    )
    y = y0 + _ROW // 2
    for i, (name, opts) in enumerate(_MODE_ROWS):
        fb._text(6, y, name, TFT_CYAN if i == _msel else TFT_LIGHTGREY)
        x = 6 + 8 * _CW
        for j, opt in enumerate(opts):
            chosen = j == current[i]
            if chosen:
                fb._fill_rectangle(x - 2, y - 1, len(opt) * _CW + 4, _ROW, TFT_BLUE)
            color = TFT_WHITE if chosen else TFT_DARKGREY
            fb._text(x, y, opt, color)
            x += (len(opt) + 2) * _CW
        y += _ROW + 4
    _hint(fb, "Up/Dn:row  Left/Right:change  Esc:home")


def _tbl_cols():
    """Table columns -> (indep_label, [(header, fn)]). fn maps t->value."""
    if _gmode == MODE_FUNC:
        cols = []
        for i in range(NFUNC):
            slot = _fslots[i]
            if slot["on"] and slot["code"] is not None:
                cols.append(("Y%d" % (i + 1), i))
            if len(cols) == 3:
                break
        return "X", cols
    if _gmode == MODE_PAR:
        cols = []
        for p in range(NPAIR):
            sx = _pslots[2 * p]
            sy = _pslots[2 * p + 1]
            if sx["on"] and sy["on"] and sx["code"] and sy["code"]:
                cols.append(("X%dT" % (p + 1), 2 * p))
                cols.append(("Y%dT" % (p + 1), 2 * p + 1))
            if len(cols) >= 2:
                break
        return "T", cols
    cols = []
    for p in range(NPOL):
        slot = _rslots[p]
        if slot["on"] and slot["code"] is not None:
            cols.append(("r%d" % (p + 1), p))
        if len(cols) == 3:
            break
    return "T", cols


def _tbl_eval(fn, t):
    if _gmode == MODE_FUNC:
        return _feval(fn, t)
    _env["t"] = t
    _env["theta"] = t
    if _gmode == MODE_PAR:
        slot = _pslots[fn]
    else:
        slot = _rslots[fn]
    if slot["code"] is None:
        return None
    try:
        v = eval(slot["code"], _env)
        if isinstance(v, (int, float)) and math.isfinite(v):
            return float(v)
    except Exception:
        pass
    return None


def _render_table(fb):
    y0 = _bar(fb)
    bottom = _H - _ROW
    indep, cols = _tbl_cols()
    ncols = 1 + len(cols)
    colw = _W // max(2, ncols)
    chars = colw // _CW - 1
    # header
    fb._fill_rectangle(0, y0 - 1, _W, _ROW, TFT_DARKGREEN)
    fb._text(4, y0, indep, TFT_WHITE)
    for j, (hdr, fn) in enumerate(cols):
        color = SLOT_COLORS[fn // 2] if _gmode == MODE_PAR else SLOT_COLORS[fn]
        fb._text(4 + (j + 1) * colw, y0, hdr, color)
    y = y0 + _ROW
    nrows = (bottom - y) // _ROW
    for r in range(nrows):
        t = _tbl_start + r * _tbl_step
        fb._text(4, y, _fmt_short(t)[:chars], TFT_LIGHTGREY)
        for j, (hdr, fn) in enumerate(cols):
            v = _tbl_eval(fn, t)
            text = "undef" if v is None else _fmt_short(v)
            fb._text(4 + (j + 1) * colw, y, text[:chars], TFT_WHITE)
        y += _ROW
    if not cols:
        fb._text(4, y0 + 2 * _ROW, "no functions on (see Y=)", TFT_RED)
    _hint(
        fb,
        "Up/Dn:scroll +/-:step=%s digit:start Esc:home" % _fmt_short(_tbl_step),
    )


def _render_graph_screens(fb):
    """GRAPH / TRACE / CALC share the plot; only the overlay differs."""
    ph = _plot_h()
    _draw_grid(fb, ph)
    _draw_curves(fb, ph)
    _legend(fb)

    if _calc_shade is not None:
        fn, pxa, pxb = _calc_shade
        arr = _fsamps[fn]
        if arr is not None:
            py0 = int(_clamp(_y2py(0.0, ph), 0, ph - 1))
            for px in range(pxa, pxb + 1, 2):
                y = arr[px]
                if y == y:
                    py = int(_clamp(_y2py(y, ph), 0, ph - 1))
                    fb._line(px, py0, px, py, TFT_DARKGREEN)

    if _calc_tan is not None:
        x0, y0, slope = _calc_tan
        xa = _px2x(0)
        xb = _px2x(_W - 1)
        _draw_segment(
            fb,
            0,
            _y2py(y0 + slope * (xa - x0), ph),
            _W - 1,
            _y2py(y0 + slope * (xb - x0), ph),
            ph,
            TFT_ORANGE,
        )

    if _calc_mark is not None:
        mx, my = _calc_mark
        _crosshair(fb, int(_x2px(mx)), int(_y2py(my, ph)), ph, TFT_RED)

    if _scr == SCR_GRAPH:
        if _zbox is not None and _zbox[0] == 2:
            x = min(_zbox[1], _gpx)
            y = min(_zbox[2], _gpy)
            w = abs(_gpx - _zbox[1]) + 1
            h = abs(_gpy - _zbox[2]) + 1
            fb._rectangle(x, y, w, h, TFT_WHITE)
        _crosshair(fb, _gpx, _gpy, ph, TFT_WHITE)
        if _zbox is not None:
            line1 = "ZBox: corner %d  X=%s Y=%s" % (
                _zbox[0],
                _fmt_short(_px2x(_gpx)),
                _fmt_short(_py2y(_gpy, ph)),
            )
            line2 = "move + Enter to mark, Esc cancels"
        elif _pzoom:
            line1 = ("Zoom In" if _pzoom < 1.0 else "Zoom Out") + ": Enter at cursor"
            line2 = "arrows move, Enter zooms, Esc cancels"
        else:
            if _flash:
                line1 = _flash
            else:
                line1 = "X=%s Y=%s  %s" % (
                    _fmt_short(_px2x(_gpx)),
                    _fmt_short(_py2y(_gpy, ph)),
                    _win_status(),
                )
            line2 = "arrows +/- zoom R:std T:trace C:calc F2:Y="
        _panel(fb, ph, line1, line2)
        return

    # TRACE / CALC cursor rides the traced curve
    x, y, indep = _trace_pos()
    if x == x and y == y:
        px = int(_x2px(x))
        py = int(_y2py(y, ph))
        _crosshair(fb, px, py, ph, TFT_WHITE)
        if 0 <= px < _W and 0 <= py < ph:
            fb._circle(px, py, 3, TFT_WHITE)
    elif _gmode == MODE_FUNC:
        fb._line(_tr_i, 0, _tr_i, ph - 1, TFT_WHITE)

    if _scr == SCR_TRACE:
        color = _slot_color(_tr_fn)
        if _gmode == MODE_FUNC:
            line1 = "Y%d: X=%s Y=%s" % (
                _tr_fn + 1,
                _fmt_short(x),
                _fmt_short(y),
            )
        else:
            name = "P%d" % (_tr_fn + 1) if _gmode == MODE_PAR else "r%d" % (_tr_fn + 1)
            line1 = "%s: T=%s X=%s Y=%s" % (
                name,
                _fmt_short(indep),
                _fmt_short(x),
                _fmt_short(y),
            )
        _panel(fb, ph, line1, "</>:move Up/Dn:fn digit:goto Enter:center", color)
        return

    # SCR_CALC
    _panel(fb, ph, _calc_msg, "Enter:next  Esc:cancel", TFT_WHITE)


def _render_prompt(fb):
    """Bottom text-entry overlay (X=?, TblStart=?, ...)."""
    y = _H - 2 * _ROW
    fb._fill_rectangle(0, y, _W, 2 * _ROW, TFT_DARKGREY)
    fb._line(0, y, _W - 1, y, TFT_WHITE)
    _edit_row(fb, y + 4, _prompt["label"], _prompt["ed"], True, TFT_YELLOW)


def _render(fb):
    fb.fill_screen(TFT_BLACK)
    if _scr == SCR_HOME:
        _render_home(fb)
    elif _scr == SCR_YEQ:
        _render_yeq(fb)
    elif _scr == SCR_WINDOW:
        _render_window(fb)
    elif _scr == SCR_ZOOM:
        _render_zoom(fb)
    elif _scr == SCR_TABLE:
        _render_table(fb)
    elif _scr == SCR_MODE:
        _render_mode(fb)
    elif _scr == SCR_CALC_MENU:
        _render_calc_menu(fb)
    elif _scr == SCR_CATALOG:
        _render_catalog(fb)
    elif _scr == SCR_MENU:
        _render_menu(fb)
    else:
        _render_graph_screens(fb)
    if _prompt is not None:
        _render_prompt(fb)
    fb.swap()


# ---------------------------------------------------------------- navigation


def _goto(scr):
    """Switch screens, compiling/recomputing when entering a plot."""
    global _scr, _plot_dirty, _tr_fn, _tr_i, _flash, _zbox, _pzoom
    global _calc_mark, _calc_shade, _calc_tan
    if scr in (SCR_GRAPH, SCR_TRACE, SCR_TABLE):
        _compile_slots()
        _plot_dirty = True
    if scr in (SCR_GRAPH, SCR_TRACE):
        _flash = ""
        if scr == SCR_GRAPH and _scr not in (SCR_GRAPH, SCR_TRACE, SCR_CALC):
            _zbox = None
            _pzoom = 0.0
            _calc_mark = None
            _calc_shade = None
            _calc_tan = None
    if scr == SCR_WINDOW:
        _win_editors()
    if scr == SCR_TRACE:
        # will be validated after recompute in run()
        _tr_i = _clamp(_tr_i, 0, _W - 1)
    _scr = scr


def _trace_targets_ok():
    """Snap _tr_fn/_tr_i to a valid traced curve; False if none exist."""
    global _tr_fn, _tr_i
    curves = _curve_list()
    if not curves:
        return False
    if _tr_fn not in curves:
        _tr_fn = curves[0]
    if _gmode == MODE_FUNC:
        _tr_i = _clamp(_tr_i, 0, _W - 1)
    else:
        cur = _xysamps[_tr_fn]
        _tr_i = _clamp(_tr_i, 0, len(cur[0]) - 1)
    return True


def _global_key(btn):
    """Soft keys available on every screen. Returns True if handled."""
    global _flash
    if btn == BUTTON_F2:
        _goto(SCR_YEQ)
    elif btn == BUTTON_F3:
        _goto(SCR_WINDOW)
    elif btn == BUTTON_F4:
        _goto(SCR_ZOOM)
    elif btn == BUTTON_F5:
        _compile_slots()
        _force_recompute()
        if _trace_targets_ok():
            _goto(SCR_TRACE)
        else:
            _goto(SCR_GRAPH)
            _flash = "nothing to trace (check Y=)"
    elif btn == BUTTON_F6:
        _goto(SCR_GRAPH)
    elif btn == BUTTON_F7:
        _goto(SCR_TABLE)
    elif btn == BUTTON_F8:
        _goto(SCR_MODE)
    else:
        return False
    return True


def _recompute_now():
    global _plot_dirty
    if _plot_dirty:
        _recompute()
        _plot_dirty = False


def _force_recompute():
    global _plot_dirty
    _recompute()
    _plot_dirty = False


# ---------------------------------------------------------------- prompts


def _open_prompt(label, cb, seed=""):
    global _prompt
    _prompt = {"label": label, "ed": _new_ed(seed), "cb": cb}


def _prompt_key(btn, inp):
    """Route input to the active prompt. Returns True while active."""
    global _prompt, _tr_i, _tbl_start, _plot_dirty, _calc_stage, _calc_msg
    global _calc_mark, _flash
    if btn == BUTTON_BACK:
        _prompt = None
        if _scr == SCR_CALC and _calc_op == "value":
            _goto(SCR_GRAPH)
        return True
    if btn in (BUTTON_CENTER, BUTTON_ENTER):
        val, err = _eval_number(_ed_text(_prompt["ed"]))
        if err is not None:
            _prompt["label"] = err + " "
            _ed_set(_prompt["ed"], "", False)
            return True
        cb = _prompt["cb"]
        _prompt = None
        if cb == "tblstart":
            _tbl_start = val
        elif cb == "goto":
            _trace_goto(val)
        elif cb == "value":
            _calc_value(val)
        return True
    _edit_key(_prompt["ed"], btn, inp)
    return True


def _trace_goto(val):
    """Jump the trace cursor to X= (func) or T= (par/pol)."""
    global _tr_i, _plot_dirty
    if _gmode == MODE_FUNC:
        if not (_win[0] <= val <= _win[1]):
            # pan the window so val is centered
            span = _win[1] - _win[0]
            _win[0] = val - span / 2.0
            _win[1] = val + span / 2.0
            _plot_dirty = True
        _tr_i = int(_clamp(round(_x2px(val)), 0, _W - 1))
    else:
        if _tmax > _tmin:
            frac = (val - _tmin) / (_tmax - _tmin)
            cur = _xysamps[_tr_fn] if _tr_fn < len(_xysamps) else None
            n = len(cur[0]) if cur else _t_samples()
            _tr_i = int(_clamp(round(frac * (n - 1)), 0, n - 1))


# ---------------------------------------------------------------- input: editors


def _handle_home(btn, inp):
    global _hrecall, _hist
    if btn in (BUTTON_CENTER, BUTTON_ENTER):
        text = _ed_text(_hed).strip()
        if not text:
            if _hist:
                text = _hist[-1][0]  # empty Enter repeats the last entry
            else:
                return
        result, is_err = _home_eval(text)
        _hist.append([text, result, is_err])
        if len(_hist) > MAX_HIST:
            _hist.pop(0)
        _ed_set(_hed, "")
        _hrecall = -1
        return
    if btn == BUTTON_UP:
        if _hist:
            if _hrecall < 0:
                _hrecall = len(_hist) - 1
            elif _hrecall > 0:
                _hrecall -= 1
            _ed_set(_hed, _hist[_hrecall][0])
        return
    if btn == BUTTON_DOWN:
        if _hist and _hrecall >= 0:
            if _hrecall < len(_hist) - 1:
                _hrecall += 1
                _ed_set(_hed, _hist[_hrecall][0])
            else:
                _hrecall = -1
                _ed_set(_hed, "")
        return
    if btn == BUTTON_F9:
        _open_catalog(SCR_HOME)
        return
    if btn == BUTTON_TAB:
        _open_menu()
        return
    _edit_key(_hed, btn, inp)


def _handle_yeq(btn, inp):
    global _ysel
    slots = _slots_for_mode()
    slot = slots[_ysel]
    if btn == BUTTON_UP:
        _ysel = (_ysel - 1) % len(slots)
    elif btn == BUTTON_DOWN:
        _ysel = (_ysel + 1) % len(slots)
    elif btn == BUTTON_TAB:
        slot["on"] = not slot["on"]
        if _gmode == MODE_PAR:  # pairs toggle together
            slots[_ysel ^ 1]["on"] = slot["on"]
    elif btn in (BUTTON_CENTER, BUTTON_ENTER):
        _compile_slots()
        bad = None
        for i, s in enumerate(slots):
            if s["err"] and s["on"]:
                bad = i
                break
        if bad is None:
            _goto(SCR_GRAPH)
        else:
            _ysel = bad
    elif btn == BUTTON_F9:
        _open_catalog(SCR_YEQ)
    else:
        if _edit_key(slot["ed"], btn, inp):
            slot["err"] = None
            slot["code"] = None


def _handle_window(btn, inp):
    global _wsel
    n = len(_weds)
    if btn == BUTTON_UP:
        if _win_commit(_wsel):
            _wsel = (_wsel - 1) % n
    elif btn == BUTTON_DOWN:
        if _win_commit(_wsel):
            _wsel = (_wsel + 1) % n
    elif btn in (BUTTON_CENTER, BUTTON_ENTER):
        if _win_commit(_wsel):
            _wsel = (_wsel + 1) % n
    elif btn == BUTTON_F9:
        _open_catalog(SCR_WINDOW)
    else:
        _edit_key(_weds[_wsel], btn, inp)


def _handle_mode(btn):
    global _msel, _deg, _gmode, _grid, _axes, _labels, _ysel, _tr_fn, _tr_i
    global _plot_dirty
    if btn == BUTTON_UP:
        _msel = (_msel - 1) % len(_MODE_ROWS)
        return
    if btn == BUTTON_DOWN:
        _msel = (_msel + 1) % len(_MODE_ROWS)
        return
    if btn not in (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_CENTER, BUTTON_ENTER):
        return
    step = -1 if btn == BUTTON_LEFT else 1
    if _msel == 0:
        _deg = not _deg
        _set_angle_env()
    elif _msel == 1:
        _gmode = (_gmode + step) % 3
        _ysel = 0
        _tr_fn = 0
        _tr_i = 0
    elif _msel == 2:
        _grid = not _grid
    elif _msel == 3:
        _axes = not _axes
    else:
        _labels = not _labels
    _plot_dirty = True


# ---------------------------------------------------------------- input: menus


def _handle_zoom(btn):
    global _zsel
    n = len(_ZOOM_ITEMS)
    if btn == BUTTON_UP:
        _zsel = (_zsel - 1) % n
    elif btn == BUTTON_DOWN:
        _zsel = (_zsel + 1) % n
    elif btn in (BUTTON_CENTER, BUTTON_ENTER):
        _zoom_action(_zsel)
    else:
        ch = None
        for d in range(n):
            if btn == BUTTON_1 + d:
                ch = d
                break
        if ch is not None:
            _zoom_action(ch)


def _handle_calc_menu(btn):
    global _csel
    n = len(_CALC_ITEMS)
    if btn == BUTTON_UP:
        _csel = (_csel - 1) % n
    elif btn == BUTTON_DOWN:
        _csel = (_csel + 1) % n
    elif btn in (BUTTON_CENTER, BUTTON_ENTER):
        _calc_start(_csel)
    else:
        for d in range(n):
            if btn == BUTTON_1 + d:
                _calc_start(d)
                break


def _open_menu():
    global _menu_sel, _scr
    _menu_sel = 0
    _scr = SCR_MENU


def _handle_menu(btn):
    global _menu_sel
    n = len(_MENU_ITEMS)
    if btn == BUTTON_UP:
        _menu_sel = (_menu_sel - 1) % n
    elif btn == BUTTON_DOWN:
        _menu_sel = (_menu_sel + 1) % n
    elif btn in (BUTTON_CENTER, BUTTON_ENTER):
        target = _MENU_ITEMS[_menu_sel][1]
        if target == SCR_CATALOG:
            _open_catalog(SCR_HOME)
        else:
            _goto(target)


def _open_catalog(from_scr):
    global _cat_sel, _cat_from, _scr
    _cat_from = from_scr
    _scr = SCR_CATALOG


def _handle_catalog(btn):
    global _cat_sel, _scr
    n = len(_CATALOG)
    if btn == BUTTON_UP:
        _cat_sel = (_cat_sel - 1) % n
    elif btn == BUTTON_DOWN:
        _cat_sel = (_cat_sel + 1) % n
    elif btn in (BUTTON_CENTER, BUTTON_ENTER):
        text = _CATALOG[_cat_sel][0]
        if _cat_from == SCR_YEQ:
            _ed_insert(_slots_for_mode()[_ysel]["ed"], text)
        elif _cat_from == SCR_WINDOW:
            _ed_insert(_weds[_wsel], text)
        else:
            _ed_insert(_hed, text)
        _scr = _cat_from


# ---------------------------------------------------------------- input: graph


def _zoom_about(fx, fy, factor):
    """Zoom the window about graph point (fx, fy)."""
    global _plot_dirty
    xspan = (_win[1] - _win[0]) * factor
    yspan = (_win[3] - _win[2]) * factor
    xspan = _clamp(xspan, MIN_SPAN, MAX_SPAN)
    yspan = _clamp(yspan, MIN_SPAN, MAX_SPAN)
    # keep the anchor point at the same relative position
    rx = (fx - _win[0]) / (_win[1] - _win[0])
    ry = (fy - _win[2]) / (_win[3] - _win[2])
    _win[0] = fx - rx * xspan
    _win[1] = _win[0] + xspan
    _win[2] = fy - ry * yspan
    _win[3] = _win[2] + yspan
    _plot_dirty = True


def _set_win(xmin, xmax, ymin, ymax):
    global _plot_dirty
    if xmax - xmin < MIN_SPAN:
        xmax = xmin + MIN_SPAN
    if ymax - ymin < MIN_SPAN:
        ymax = ymin + MIN_SPAN
    _win[0], _win[1], _win[2], _win[3] = xmin, xmax, ymin, ymax
    _plot_dirty = True


def _zoom_action(idx):
    """Apply a ZOOM menu selection."""
    global _zbox, _pzoom, _xscl, _yscl, _tmin, _tmax, _tstep, _gpx, _gpy
    global _flash
    ph = _plot_h()
    if idx == 0:  # ZBox
        _goto(SCR_GRAPH)
        _zbox = [1, 0, 0]
        return
    if idx == 1:  # Zoom In
        _goto(SCR_GRAPH)
        _pzoom = 0.5
        return
    if idx == 2:  # Zoom Out
        _goto(SCR_GRAPH)
        _pzoom = 2.0
        return
    if idx == 3:  # ZStandard
        _xscl = 1.0
        _yscl = 1.0
        if _gmode != MODE_FUNC:
            _tmin = 0.0
            _tmax = 360.0 if _deg else TWO_PI
            _tstep = 2.0 if _deg else 0.05
        _set_win(-10.0, 10.0, -10.0, 10.0)
    elif idx == 4:  # ZSquare: equal units per pixel, x expands
        yspan = _win[3] - _win[2]
        xspan = yspan * (_W - 1) / (ph - 1)
        cx = (_win[0] + _win[1]) / 2.0
        _set_win(cx - xspan / 2.0, cx + xspan / 2.0, _win[2], _win[3])
    elif idx == 5:  # ZTrig
        if _deg:
            _xscl = 90.0
            _set_win(-360.0, 360.0, -4.0, 4.0)
        else:
            _xscl = math.pi / 2.0
            _set_win(-TWO_PI, TWO_PI, -4.0, 4.0)
        _yscl = 1.0
    elif idx == 6:  # ZDecimal: 0.05 units per pixel
        hx = (_W - 1) * 0.025
        hy = (ph - 1) * 0.025
        _xscl = 1.0
        _yscl = 1.0
        _set_win(-hx, hx, -hy, hy)
    elif idx == 7:  # ZoomFit
        _compile_slots()
        _recompute()
        lo = None
        hi = None
        if _gmode == MODE_FUNC:
            for i in _curve_list():
                arr = _fsamps[i]
                for px in range(_W):
                    y = arr[px]
                    if y == y:
                        if lo is None or y < lo:
                            lo = y
                        if hi is None or y > hi:
                            hi = y
        else:
            for i in _curve_list():
                xs, ys = _xysamps[i]
                for k in range(len(ys)):
                    y = ys[k]
                    if y == y:
                        if lo is None or y < lo:
                            lo = y
                        if hi is None or y > hi:
                            hi = y
        if lo is None:
            _goto(SCR_GRAPH)
            _flash = "ZoomFit: nothing plotted"
            return
        if hi - lo < MIN_SPAN:
            lo -= 1.0
            hi += 1.0
        margin = (hi - lo) * 0.05
        _set_win(_win[0], _win[1], lo - margin, hi + margin)
    _goto(SCR_GRAPH)
    _gpx = _W // 2
    _gpy = _plot_h() // 2


def _pan(dx_px, dy_px):
    """Shift the window by a pixel delta."""
    global _plot_dirty
    dx = dx_px * (_win[1] - _win[0]) / (_W - 1)
    dy = dy_px * (_win[3] - _win[2]) / (_plot_h() - 1)
    _win[0] += dx
    _win[1] += dx
    _win[2] += dy
    _win[3] += dy
    _plot_dirty = True


def _handle_graph(btn):
    global _gpx, _gpy, _zbox, _pzoom, _flash
    ph = _plot_h()
    step = max(2, _W // 80)
    _flash = ""

    if btn == BUTTON_LEFT:
        _gpx -= step
        if _gpx < 0:
            _pan(-(_W // 4), 0)
            _gpx = 0
    elif btn == BUTTON_RIGHT:
        _gpx += step
        if _gpx >= _W:
            _pan(_W // 4, 0)
            _gpx = _W - 1
    elif btn == BUTTON_UP:
        _gpy -= step
        if _gpy < 0:
            _pan(0, ph // 4)
            _gpy = 0
    elif btn == BUTTON_DOWN:
        _gpy += step
        if _gpy >= ph:
            _pan(0, -(ph // 4))
            _gpy = ph - 1
    elif btn in (BUTTON_CENTER, BUTTON_ENTER):
        if _zbox is not None:
            if _zbox[0] == 1:
                _zbox = [2, _gpx, _gpy]
            else:
                xa = _px2x(min(_zbox[1], _gpx))
                xb = _px2x(max(_zbox[1], _gpx))
                ya = _py2y(max(_zbox[2], _gpy), ph)
                yb = _py2y(min(_zbox[2], _gpy), ph)
                _zbox = None
                if xb - xa > 0 and yb - ya > 0:
                    _set_win(xa, xb, ya, yb)
                    _gpx = _W // 2
                    _gpy = ph // 2
        elif _pzoom:
            _zoom_about(_px2x(_gpx), _py2y(_gpy, ph), _pzoom)
            _pzoom = 0.0
    elif btn in (BUTTON_PLUS, BUTTON_EQUAL):
        _zoom_about(_px2x(_gpx), _py2y(_gpy, ph), 0.5)
    elif btn in (BUTTON_MINUS, BUTTON_UNDERSCORE):
        _zoom_about(_px2x(_gpx), _py2y(_gpy, ph), 2.0)
    elif btn == BUTTON_R:
        _zoom_action(3)
    elif btn == BUTTON_T:
        _recompute_now()
        if _trace_targets_ok():
            _goto(SCR_TRACE)
        else:
            _flash = "nothing to trace (check Y=)"
    elif btn == BUTTON_C:
        _open_calc()
    elif btn == BUTTON_Y:
        _goto(SCR_YEQ)
    elif btn == BUTTON_W:
        _goto(SCR_WINDOW)
    elif btn == BUTTON_Z:
        _goto(SCR_ZOOM)
    elif btn == BUTTON_B:
        _goto(SCR_TABLE)
    elif btn == BUTTON_M:
        _goto(SCR_MODE)
    elif btn == BUTTON_H:
        _goto(SCR_HOME)


def _trace_move(delta):
    """Move the trace cursor, panning the window in function mode."""
    global _tr_i, _plot_dirty
    if _gmode == MODE_FUNC:
        _tr_i += delta
        if _tr_i < 0:
            _pan(-(_W // 4), 0)
            _tr_i = 0
        elif _tr_i >= _W:
            _pan(_W // 4, 0)
            _tr_i = _W - 1
    else:
        cur = _xysamps[_tr_fn] if _tr_fn < len(_xysamps) else None
        n = len(cur[0]) if cur else 1
        _tr_i = _clamp(_tr_i + delta, 0, n - 1)


def _trace_switch(step):
    global _tr_fn
    curves = _curve_list()
    if not curves:
        return
    if _tr_fn not in curves:
        _tr_fn = curves[0]
        return
    k = curves.index(_tr_fn)
    _tr_fn = curves[(k + step) % len(curves)]


def _handle_trace(btn, inp):
    global _plot_dirty
    if btn == BUTTON_LEFT:
        _trace_move(-1)
    elif btn == BUTTON_RIGHT:
        _trace_move(1)
    elif btn == BUTTON_UP:
        _trace_switch(-1)
    elif btn == BUTTON_DOWN:
        _trace_switch(1)
    elif btn == BUTTON_END:
        _trace_move(_W)
    elif btn in (BUTTON_CENTER, BUTTON_ENTER):
        # quick zoom: center the window on the cursor
        x, y, indep = _trace_pos()
        if x == x and y == y:
            xspan = _win[1] - _win[0]
            yspan = _win[3] - _win[2]
            _set_win(x - xspan / 2.0, x + xspan / 2.0, y - yspan / 2.0, y + yspan / 2.0)
            if _gmode == MODE_FUNC:
                _tr_i = _W // 2
    elif btn == BUTTON_T:
        _goto(SCR_GRAPH)
    elif btn == BUTTON_C:
        _open_calc()
    else:
        ch = inp.button_to_char(btn)
        if ch and (ch.isdigit() or ch in "-."):
            label = "X=" if _gmode == MODE_FUNC else "T="
            _open_prompt(label, "goto", ch)


def _handle_table(btn, inp):
    global _tbl_start, _tbl_step
    if btn == BUTTON_UP:
        _tbl_start -= _tbl_step
    elif btn == BUTTON_DOWN:
        _tbl_start += _tbl_step
    elif btn in (BUTTON_PLUS, BUTTON_EQUAL):
        _tbl_step *= 2.0
    elif btn in (BUTTON_MINUS, BUTTON_UNDERSCORE):
        _tbl_step /= 2.0
    elif btn in (BUTTON_CENTER, BUTTON_ENTER):
        _open_prompt("TblStart=", "tblstart")
    else:
        ch = inp.button_to_char(btn)
        if ch and (ch.isdigit() or ch in "-."):
            _open_prompt("TblStart=", "tblstart", ch)


# ---------------------------------------------------------------- CALC operations


def _open_calc():
    global _csel, _scr, _flash
    if _gmode != MODE_FUNC:
        _goto(SCR_GRAPH)
        _flash = "CALC needs FUNCTION mode (F8)"
        return
    _recompute_now()
    if not _trace_targets_ok():
        _goto(SCR_GRAPH)
        _flash = "nothing plotted (check Y=)"
        return
    _csel = 0
    _scr = SCR_CALC_MENU


def _calc_start(idx):
    global _scr, _calc_op, _calc_stage, _calc_msg, _calc_fn2
    global _calc_mark, _calc_shade, _calc_tan
    _calc_mark = None
    _calc_shade = None
    _calc_tan = None
    _calc_fn2 = 0
    _calc_stage = 0
    ops = ("value", "zero", "min", "max", "isect", "dydx", "int")
    _calc_op = ops[idx]
    _scr = SCR_CALC
    if _calc_op == "value":
        _calc_msg = "value"
        _open_prompt("X=", "value")
    elif _calc_op == "zero":
        _calc_msg = "zero: Left Bound? (Enter)"
    elif _calc_op == "min":
        _calc_msg = "minimum: Left Bound? (Enter)"
    elif _calc_op == "max":
        _calc_msg = "maximum: Left Bound? (Enter)"
    elif _calc_op == "isect":
        _calc_msg = "intersect: First curve? (Up/Dn, Enter)"
    elif _calc_op == "dydx":
        _calc_msg = "dy/dx: move to X, then Enter"
    else:
        _calc_msg = "integral: Lower Limit? (Enter)"


def _calc_value(x):
    """CALC 1:value at X=x."""
    global _calc_msg, _calc_mark, _calc_stage, _tr_i, _plot_dirty
    if not (_win[0] <= x <= _win[1]):
        span = _win[1] - _win[0]
        _win[0] = x - span / 2.0
        _win[1] = x + span / 2.0
        _plot_dirty = True
    _tr_i = int(_clamp(round(_x2px(x)), 0, _W - 1))
    y = _feval(_tr_fn, x)
    if y is None:
        _calc_msg = "Y%d(%s) undefined" % (_tr_fn + 1, _fmt_short(x))
    else:
        _calc_msg = "Y%d(%s)=%s" % (_tr_fn + 1, _fmt_short(x), _fmt_val(y))
        _calc_mark = (x, y)
    _calc_stage = 9


def _find_zero(f, a, b):
    """Sign-change scan + bisection. Returns x or None."""
    n = 64
    fa = f(a)
    if fa is None:
        fa = NAN
    x0 = a
    for k in range(1, n + 1):
        x1 = a + (b - a) * k / n
        f1 = f(x1)
        if f1 is None:
            f1 = NAN
        if fa == fa and f1 == f1:
            if fa == 0.0:
                return x0
            if fa * f1 < 0.0:
                lo, hi, flo = x0, x1, fa
                for _ in range(60):
                    mid = (lo + hi) / 2.0
                    fm = f(mid)
                    if fm is None:
                        break
                    if fm == 0.0:
                        return mid
                    if flo * fm < 0.0:
                        hi = mid
                    else:
                        lo = mid
                        flo = fm
                return (lo + hi) / 2.0
        x0, fa = x1, f1
    if fa == 0.0:
        return b
    return None


def _find_extreme(f, a, b, sign):
    """Scan + ternary refine. sign=+1 max, -1 min. Returns (x, y) or None."""
    n = 96
    best_k = -1
    best = None
    for k in range(n + 1):
        x = a + (b - a) * k / n
        y = f(x)
        if y is None:
            continue
        v = y * sign
        if best is None or v > best:
            best = v
            best_k = k
    if best_k < 0:
        return None
    lo = a + (b - a) * max(0, best_k - 1) / n
    hi = a + (b - a) * min(n, best_k + 1) / n
    for _ in range(60):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        f1 = f(m1)
        f2 = f(m2)
        if f1 is None or f2 is None:
            break
        if f1 * sign < f2 * sign:
            lo = m1
        else:
            hi = m2
    x = (lo + hi) / 2.0
    y = f(x)
    if y is None:
        return None
    return (x, y)


def _simpson(f, a, b, n=128):
    """Composite Simpson integral; treats undefined samples as 0."""
    if n % 2:
        n += 1
    h = (b - a) / n
    total = 0.0
    for k in range(n + 1):
        y = f(a + k * h)
        if y is None:
            y = 0.0
        if k == 0 or k == n:
            total += y
        elif k % 2:
            total += 4.0 * y
        else:
            total += 2.0 * y
    return total * h / 3.0


def _calc_finish():
    """Run the computation once both bounds are picked."""
    global _calc_msg, _calc_mark, _calc_shade, _calc_tan, _calc_stage
    global _tr_i
    a = min(_calc_x1, _px2x(_tr_i))
    b = max(_calc_x1, _px2x(_tr_i))
    fn = _tr_fn

    def f(x):
        return _feval(fn, x)

    if _calc_op == "zero":
        x = _find_zero(f, a, b)
        if x is None:
            _calc_msg = "no sign change in bounds"
        else:
            _calc_msg = "ZERO  X=%s Y=0" % _fmt_val(x)
            _calc_mark = (x, 0.0)
            _tr_i = int(_clamp(round(_x2px(x)), 0, _W - 1))
    elif _calc_op in ("min", "max"):
        sign = 1.0 if _calc_op == "max" else -1.0
        res = _find_extreme(f, a, b, sign)
        if res is None:
            _calc_msg = "undefined in bounds"
        else:
            x, y = res
            name = "MAXIMUM" if _calc_op == "max" else "MINIMUM"
            _calc_msg = "%s X=%s Y=%s" % (name, _fmt_short(x), _fmt_val(y))
            _calc_mark = (x, y)
            _tr_i = int(_clamp(round(_x2px(x)), 0, _W - 1))
    elif _calc_op == "isect":
        fn2 = _calc_fn2

        def h(x):
            y1 = _feval(fn, x)
            y2 = _feval(fn2, x)
            if y1 is None or y2 is None:
                return None
            return y1 - y2

        x = _find_zero(h, a, b)
        if x is None:
            _calc_msg = "no intersection in bounds"
        else:
            y = _feval(fn, x)
            _calc_msg = "INTERSECT X=%s Y=%s" % (_fmt_val(x), _fmt_short(y if y is not None else NAN))
            if y is not None:
                _calc_mark = (x, y)
            _tr_i = int(_clamp(round(_x2px(x)), 0, _W - 1))
    elif _calc_op == "int":
        area = _simpson(f, a, b)
        _calc_msg = "INTEGRAL(%s,%s)=%s" % (_fmt_short(a), _fmt_short(b), _fmt_val(area))
        pxa = int(_clamp(round(_x2px(a)), 0, _W - 1))
        pxb = int(_clamp(round(_x2px(b)), 0, _W - 1))
        _calc_shade = (fn, pxa, pxb)
    _calc_stage = 9


def _handle_calc(btn):
    global _calc_stage, _calc_msg, _calc_x1, _calc_fn2, _calc_tan, _calc_mark
    global _tr_fn
    if _calc_stage == 9:  # showing a result
        if btn in (BUTTON_CENTER, BUTTON_ENTER):
            _goto(SCR_GRAPH)
        return

    if btn == BUTTON_LEFT:
        _trace_move(-1)
        return
    if btn == BUTTON_RIGHT:
        _trace_move(1)
        return
    if btn == BUTTON_UP or btn == BUTTON_DOWN:
        # switching curves is allowed while picking curves / first bound
        if _calc_stage == 0 or (_calc_op == "isect" and _calc_stage <= 1):
            _trace_switch(-1 if btn == BUTTON_UP else 1)
        return
    if btn not in (BUTTON_CENTER, BUTTON_ENTER):
        return

    x = _px2x(_tr_i)
    if _calc_op == "dydx":
        y = _feval(_tr_fn, x)
        span = _win[1] - _win[0]
        h = span / 1000.0
        y1 = _feval(_tr_fn, x - h)
        y2 = _feval(_tr_fn, x + h)
        if y is None or y1 is None or y2 is None:
            _calc_msg = "undefined at X=%s" % _fmt_short(x)
        else:
            slope = (y2 - y1) / (2.0 * h)
            _calc_msg = "dy/dx=%s at X=%s" % (_fmt_val(slope), _fmt_short(x))
            _calc_tan = (x, y, slope)
            _calc_mark = (x, y)
        _calc_stage = 9
        return

    if _calc_op == "isect":
        if _calc_stage == 0:
            _calc_stage = 1
            _calc_msg = "Second curve? (Up/Dn, Enter)"
            _calc_fn2 = _tr_fn
            _trace_switch(1)
            return
        if _calc_stage == 1:
            # first pick was stored in fn2; swap so fn=first, fn2=second
            first = _calc_fn2
            _calc_fn2 = _tr_fn
            _tr_fn = first
            _calc_stage = 2
            _calc_msg = "Left Bound? (Enter)"
            return
        if _calc_stage == 2:
            _calc_x1 = _px2x(_tr_i)
            _calc_stage = 3
            _calc_msg = "Right Bound? (Enter)"
            return
        _calc_finish()
        return

    # zero / min / max / int: two bounds
    if _calc_stage == 0:
        _calc_x1 = x
        _calc_stage = 1
        _calc_msg = (
            "Upper Limit? (Enter)" if _calc_op == "int" else "Right Bound? (Enter)"
        )
        return
    _calc_finish()


# ---------------------------------------------------------------- persistence


def _save_state():
    storage = _vm.storage if _vm else None
    if storage is None:
        return
    try:
        vars_out = {}
        for c in "abcdfghijklmnopqrstuvwxyz":
            v = _env.get(c, 0.0)
            if isinstance(v, float) and v != 0.0 and math.isfinite(v):
                vars_out[c] = v
        state = {
            "v": 1,
            "deg": _deg,
            "gmode": _gmode,
            "grid": _grid,
            "axes": _axes,
            "labels": _labels,
            "win": list(_win),
            "xscl": _xscl,
            "yscl": _yscl,
            "tmin": _tmin,
            "tmax": _tmax,
            "tstep": _tstep,
            "tbl": [_tbl_start, _tbl_step],
            "ans": _env.get("ans", 0.0),
            "vars": vars_out,
            "hist": [item[0] for item in _hist[-10:]],
            "func": [[_ed_text(s["ed"]), s["on"]] for s in _fslots],
            "par": [[_ed_text(s["ed"]), s["on"]] for s in _pslots],
            "pol": [[_ed_text(s["ed"]), s["on"]] for s in _rslots],
        }
        storage.deserialize(state, STATE_FILE)
    except Exception:
        pass


def _load_state():
    global _deg, _gmode, _grid, _axes, _labels, _xscl, _yscl
    global _tmin, _tmax, _tstep, _tbl_start, _tbl_step
    storage = _vm.storage if _vm else None
    if storage is None:
        return
    try:
        state = storage.serialize(STATE_FILE)
        if not isinstance(state, dict) or state.get("v") != 1:
            return
        _deg = bool(state.get("deg", False))
        _set_angle_env()  # history is replayed below with the right trig
        _gmode = _clamp(int(state.get("gmode", 0)), 0, 2)
        _grid = bool(state.get("grid", True))
        _axes = bool(state.get("axes", True))
        _labels = bool(state.get("labels", True))
        win = state.get("win")
        if isinstance(win, list) and len(win) == 4 and win[0] < win[1] and win[2] < win[3]:
            _win[0], _win[1], _win[2], _win[3] = (
                float(win[0]),
                float(win[1]),
                float(win[2]),
                float(win[3]),
            )
        _xscl = abs(float(state.get("xscl", 1.0)))
        _yscl = abs(float(state.get("yscl", 1.0)))
        _tmin = float(state.get("tmin", 0.0))
        _tmax = float(state.get("tmax", TWO_PI))
        _tstep = float(state.get("tstep", 0.05))
        if _tstep <= 0:
            _tstep = 0.05
        tbl = state.get("tbl")
        if isinstance(tbl, list) and len(tbl) == 2 and float(tbl[1]) > 0:
            _tbl_start = float(tbl[0])
            _tbl_step = float(tbl[1])
        _env["ans"] = float(state.get("ans", 0.0))
        var_in = state.get("vars", {})
        if isinstance(var_in, dict):
            for c, v in var_in.items():
                if (
                    isinstance(c, str)
                    and len(c) == 1
                    and c.isalpha()
                    and c != "e"
                    and isinstance(v, (int, float))
                ):
                    _env[c] = float(v)
        hist = state.get("hist", [])
        if isinstance(hist, list):
            for entry in hist:
                if isinstance(entry, str) and entry:
                    _hist.append([entry, "", False])
            # re-evaluate the recalled entries quietly to rebuild results
            for item in _hist:
                result, is_err = _home_eval(item[0])
                item[1] = result
                item[2] = is_err
        for key, slots in (("func", _fslots), ("par", _pslots), ("pol", _rslots)):
            data = state.get(key)
            if isinstance(data, list):
                for i in range(min(len(data), len(slots))):
                    if (
                        isinstance(data[i], list)
                        and len(data[i]) == 2
                        and isinstance(data[i][0], str)
                    ):
                        _ed_set(slots[i]["ed"], data[i][0])
                        slots[i]["on"] = bool(data[i][1])
    except Exception:
        pass


# ---------------------------------------------------------------- lifecycle


def start(view_manager) -> bool:
    """Start the app"""
    global _scr, _env, _vm, _deg, _gmode, _grid, _axes, _labels
    global _hist, _hed, _hrecall, _fslots, _pslots, _rslots, _ysel
    global _win, _xscl, _yscl, _tmin, _tmax, _tstep, _wsel, _weds, _werr
    global _fsamps, _xysamps, _gpx, _gpy, _tr_fn, _tr_i, _zsel, _pzoom, _zbox
    global _csel, _calc_op, _calc_stage, _calc_mark, _calc_shade, _calc_tan
    global _tbl_start, _tbl_step, _cat_sel, _cat_from, _menu_sel, _msel
    global _prompt, _plot_dirty, _draw_dirty, _flash
    global _W, _H, _CW, _CH, _ROW

    draw = view_manager.draw
    _vm = view_manager
    _W = int(draw.size.x)
    _H = int(draw.size.y)
    _CW = int(draw.font_size.x) or 6
    _CH = int(draw.font_size.y) or 8
    _ROW = _CH + 3

    _scr = SCR_HOME
    _deg = False
    _gmode = MODE_FUNC
    _grid = True
    _axes = True
    _labels = True
    _hist = []
    _hed = _new_ed()
    _hrecall = -1
    _fslots = [_new_slot("sin(x)")] + [_new_slot() for _ in range(NFUNC - 1)]
    _pslots = [_new_slot("8*cos(3*t)"), _new_slot("8*sin(2*t)")] + [
        _new_slot() for _ in range(2 * NPAIR - 2)
    ]
    _rslots = [_new_slot("8*sin(3*theta)")] + [_new_slot() for _ in range(NPOL - 1)]
    _ysel = 0
    _win = list(DEF_WIN)
    _xscl = 1.0
    _yscl = 1.0
    _tmin = 0.0
    _tmax = TWO_PI
    _tstep = 0.05
    _wsel = 0
    _werr = -1
    _fsamps = [None] * NFUNC
    _xysamps = [None] * NPAIR
    _gpx = _W // 2
    _gpy = _plot_h() // 2
    _tr_fn = 0
    _tr_i = _W // 2
    _zsel = 0
    _pzoom = 0.0
    _zbox = None
    _csel = 0
    _calc_op = ""
    _calc_stage = 0
    _calc_mark = None
    _calc_shade = None
    _calc_tan = None
    _tbl_start = 0.0
    _tbl_step = 1.0
    _cat_sel = 0
    _cat_from = SCR_HOME
    _menu_sel = 0
    _msel = 0
    _prompt = None
    _flash = ""

    _env = _build_env()
    _env["x"] = 0.0
    _env["t"] = 0.0
    _set_angle_env()
    _load_state()
    _set_angle_env()
    _weds = None
    _win_editors()
    _compile_slots()
    _plot_dirty = True
    _draw_dirty = True

    view_manager.input_manager.reset()
    return True


def run(view_manager) -> None:
    """Run the app"""
    global _plot_dirty, _draw_dirty, _scr

    # The ViewManager polls input_manager.button once per loop and resets
    # it after this call, so read the cached value instead of polling again
    # (a second poll would consume the next queued key).
    btn = view_manager.button
    inp = view_manager.input_manager

    if btn != BUTTON_NONE:
        _draw_dirty = True
        if _prompt is not None:
            _prompt_key(btn, inp)
        elif btn == BUTTON_BACK:
            if _scr == SCR_HOME:
                view_manager.back()  # stop() saves the state
                return
            if _scr == SCR_CATALOG:
                _scr = _cat_from
            elif _scr in (SCR_CALC, SCR_CALC_MENU):
                _goto(SCR_GRAPH)
            elif _scr == SCR_GRAPH and (_zbox is not None or _pzoom):
                _cancel_graph_tools()
            else:
                _goto(SCR_HOME)
        elif _scr not in (SCR_CATALOG, SCR_MENU) and _global_key(btn):
            pass
        elif _scr == SCR_HOME:
            _handle_home(btn, inp)
        elif _scr == SCR_YEQ:
            _handle_yeq(btn, inp)
        elif _scr == SCR_WINDOW:
            _handle_window(btn, inp)
        elif _scr == SCR_ZOOM:
            _handle_zoom(btn)
        elif _scr == SCR_MODE:
            _handle_mode(btn)
        elif _scr == SCR_TABLE:
            _handle_table(btn, inp)
        elif _scr == SCR_CALC_MENU:
            _handle_calc_menu(btn)
        elif _scr == SCR_CALC:
            _handle_calc(btn)
        elif _scr == SCR_CATALOG:
            _handle_catalog(btn)
        elif _scr == SCR_MENU:
            _handle_menu(btn)
        elif _scr == SCR_GRAPH:
            _handle_graph(btn)
        elif _scr == SCR_TRACE:
            _handle_trace(btn, inp)

    if _plot_dirty and _scr in (SCR_GRAPH, SCR_TRACE, SCR_CALC, SCR_TABLE):
        _recompute()
        _plot_dirty = False
        if _scr == SCR_TRACE and not _trace_targets_ok():
            _scr = SCR_GRAPH
        _draw_dirty = True

    if _draw_dirty:
        _render(view_manager.draw)
        _draw_dirty = False


def _cancel_graph_tools():
    global _zbox, _pzoom
    _zbox = None
    _pzoom = 0.0


def stop(view_manager) -> None:
    """Stop the app"""
    from gc import collect

    global _env, _vm, _hist, _hed, _fslots, _pslots, _rslots, _win, _weds
    global _fsamps, _xysamps, _prompt, _calc_mark, _calc_shade, _calc_tan

    _save_state()
    _env = None
    _vm = None
    _hist = None
    _hed = None
    _fslots = None
    _pslots = None
    _rslots = None
    _win = None
    _weds = None
    _fsamps = None
    _xysamps = None
    _prompt = None
    _calc_mark = None
    _calc_shade = None
    _calc_tan = None

    collect()
