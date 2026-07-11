# Graph.py - Graphing Calculator for Picoware
# Originally translated from https://github.com/lazerduck/PicoCalc_Dashboard/blob/main/graph/graph.py
#
# Features:
#   - Up to 4 simultaneous functions Y1..Y4, each drawn in its own color
#   - Pan (arrows), zoom (+/-), reset (R) with adaptive 1-2-5 axis ticks
#   - Trace mode (T): move a cursor along a curve and read off (x, y)
#   - Parametric mode (F1): x(t), y(t) with the same pan/zoom/trace support
#
# Modes:
#   EDIT  - type expressions; Up/Down select slot, Tab toggles a slot
#           on/off, F3 clears the line, Enter plots, F2 toggles parametric
#   GRAPH - arrows pan, +/- zoom, R resets window, T trace, Enter edits
#   TRACE - Left/Right move cursor, Up/Down switch function, Enter done
#
# Note: keys are read from view_manager.button (the ViewManager consumes
# input_manager.button itself and auto-resets it each frame). HOME and F1
# are intercepted globally by the ViewManager (exit-to-desktop and
# screenshot), so this app avoids binding them.

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
    BUTTON_BACKSPACE,
    BUTTON_TAB,
    BUTTON_END,
    BUTTON_F2,
    BUTTON_F3,
    BUTTON_PLUS,
    BUTTON_EQUAL,
    BUTTON_MINUS,
    BUTTON_UNDERSCORE,
    BUTTON_E,
    BUTTON_R,
    BUTTON_T,
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
    TFT_DARKGREY,
    TFT_LIGHTGREY,
)

MODE_EDIT = 0
MODE_GRAPH = 1
MODE_TRACE = 2

NSLOTS = 4
SLOT_COLORS = (TFT_GREEN, TFT_YELLOW, TFT_CYAN, TFT_MAGENTA)
DEF_WIN = (-10.0, 10.0, -10.0, 10.0)
TMIN, TMAX = -10.0, 10.0
MIN_SPAN = 1e-6
MAX_SPAN = 1e12
NAN = float("nan")

DEFAULT_EXPRS = ("sin(x)*cos(x/2)+exp(-x**2/10)", "", "", "")
DEFAULT_PARAM = ("cos(2*t)*(1+0.5*sin(5*t))", "sin(2*t)*(1+0.5*sin(5*t))")

# Runtime state (reset in start/stop)
_slots = None  # list of {"buf","cur","on","code","err"}
_pslots = None  # two slots for x(t), y(t)
_param = False
_cur_slot = 0
_win = None  # [xmin, xmax, ymin, ymax]
_samples = None  # per-slot array('f') of y values, or None
_psamples = None  # (array of x, array of y) for parametric, or None
_trace_fn = 0
_trace_i = 0
_state = MODE_EDIT
_env = None
_plot_dirty = False
_draw_dirty = False

# Layout (physical pixels, computed in start)
_W = 320
_H = 320
_CW = 6  # character cell width
_CH = 8  # character cell height
_ROW = 11  # text row height in panels


def _new_slot(text):
    return {"buf": list(text), "cur": len(text), "on": True, "code": None, "err": None}


def _build_env():
    """Whitelisted eval environment shared by all expressions."""
    env = {
        "abs": abs,
        "min": min,
        "max": max,
        "pow": pow,
        "round": round,
        "int": int,
        "float": float,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "atan2": math.atan2,
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
        "math": math,
        "x": 0.0,
        "t": 0.0,
    }
    return env


# ---------------------------------------------------------------- mapping


def _px2x(px):
    return _win[0] + px * (_win[1] - _win[0]) / (_W - 1)


def _x2px(x):
    return (x - _win[0]) / (_win[1] - _win[0]) * (_W - 1)


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


def _fmt(v):
    """Compact number label."""
    if v == 0:
        return "0"
    if abs(v) < 1e7 and v == int(v):
        return "%d" % int(v)
    return "%.4g" % v


# ---------------------------------------------------------------- drawing


def _plot_height():
    if _state == MODE_EDIT:
        rows = 4 if not _param else 2
        return _H - ((rows + 2) * _ROW + 4)
    return _H - (2 * _ROW + 4)


def _grid(fb, ph):
    xmin, xmax, ymin, ymax = _win

    # vertical gridlines + x tick labels
    step = _nice_step(xmax - xmin)
    tick = math.ceil(xmin / step) * step
    last_label_end = -1
    while tick <= xmax:
        px = int(_x2px(tick))
        if 0 <= px < _W:
            fb._line(px, 0, px, ph - 1, TFT_DARKGREY)
            label = _fmt(tick)
            lx = px + 2
            if lx > last_label_end and lx + len(label) * _CW < _W:
                fb._text(lx, ph - _CH - 1, label, TFT_LIGHTGREY)
                last_label_end = lx + len(label) * _CW + 2
        tick += step

    # horizontal gridlines + y tick labels
    step = _nice_step(ymax - ymin)
    tick = math.ceil(ymin / step) * step
    while tick <= ymax:
        py = int(_y2py(tick, ph))
        if 0 <= py < ph:
            fb._line(0, py, _W - 1, py, TFT_DARKGREY)
            if tick != 0:
                fb._text(2, py + 1, _fmt(tick), TFT_LIGHTGREY)
        tick += step

    # axes
    if xmin <= 0.0 <= xmax:
        px = int(_x2px(0.0))
        fb._line(px, 0, px, ph - 1, TFT_BLUE)
    if ymin <= 0.0 <= ymax:
        py = int(_y2py(0.0, ph))
        fb._line(0, py, _W - 1, py, TFT_BLUE)

    fb._rectangle(0, 0, _W, ph, TFT_BLUE)


def _draw_segment(fb, px0, py0, px1, py1, ph, color):
    """Draw one curve segment, skipping discontinuities and clipping."""
    if py0 != py0 or py1 != py1:  # NaN sample
        return
    if abs(py1 - py0) > ph:  # discontinuity (e.g. tan asymptote)
        return
    if (py0 < 0 and py1 < 0) or (py0 >= ph and py1 >= ph):
        return
    py0 = 0 if py0 < 0 else (ph - 1 if py0 >= ph else int(py0))
    py1 = 0 if py1 < 0 else (ph - 1 if py1 >= ph else int(py1))
    fb._line(px0, py0, px1, py1, color)


def _curves(fb, ph):
    if _param:
        if not _psamples:
            return
        xs, ys = _psamples
        n = len(xs)
        prev = None
        for i in range(n):
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
                    _draw_segment(fb, px0, prev[1], px1, pt[1], ph, TFT_GREEN)
            prev = pt
        return

    for i in range(NSLOTS):
        arr = _samples[i]
        if arr is None or not _slots[i]["on"]:
            continue
        color = SLOT_COLORS[i]
        for px in range(1, _W):
            _draw_segment(
                fb, px - 1, _y2py(arr[px - 1], ph), px, _y2py(arr[px], ph), ph, color
            )


def _legend(fb):
    if _param:
        return
    labels = []
    for i in range(NSLOTS):
        slot = _slots[i]
        if not slot["on"] or not slot["buf"] or slot["code"] is None:
            continue
        label = "Y%d" % (i + 1)
        if _state == MODE_TRACE and i == _trace_fn:
            label = ">" + label
        labels.append((label, SLOT_COLORS[i]))
    # right-aligned so the y-axis tick labels on the left stay readable
    x = _W - 2 - sum((len(l) + 1) * _CW for l, _ in labels)
    for label, color in labels:
        fb._text(x, 2, label, color)
        x += (len(label) + 1) * _CW


def _row_text(fb, y, prefix, slot, selected, color):
    """One editable expression row with horizontal scroll and cursor."""
    maxchars = (_W - 4) // _CW - len(prefix)
    cur = slot["cur"]
    start = 0
    if cur > maxchars - 1:
        start = cur - (maxchars - 1)
    text = "".join(slot["buf"][start : start + maxchars])
    fb._text(4, y, prefix, color)
    tx = 4 + len(prefix) * _CW
    fb._text(tx, y, text, TFT_WHITE if slot["on"] else TFT_DARKGREY)
    if selected:
        cx = tx + (cur - start) * _CW
        fb._fill_rectangle(cx, y + _CH, _CW, 2, TFT_WHITE)


def _panel_edit(fb, ph):
    fb._fill_rectangle(0, ph, _W, _H - ph, TFT_BLACK)
    y = ph + 2
    err = None
    if _param:
        prefixes = ("x(t)=", "y(t)=")
        for i in range(2):
            slot = _pslots[i]
            _row_text(fb, y, prefixes[i], slot, i == _cur_slot, TFT_GREEN)
            if err is None and slot["err"]:
                err = slot["err"]
            y += _ROW
    else:
        for i in range(NSLOTS):
            slot = _slots[i]
            color = SLOT_COLORS[i] if slot["on"] else TFT_DARKGREY
            _row_text(fb, y, "Y%d=" % (i + 1), slot, i == _cur_slot, color)
            if err is None and slot["err"]:
                err = "Y%d: %s" % (i + 1, slot["err"])
            y += _ROW
    if err:
        fb._text(4, y, err[: (_W - 8) // _CW], TFT_RED)
    y += _ROW
    fb._text(4, y, "Ent:plot Tab:on/off F2:param F3:clr", TFT_DARKGREY)


def _panel_graph(fb, ph):
    fb._fill_rectangle(0, ph, _W, _H - ph, TFT_BLACK)
    status = "x[%s,%s] y[%s,%s]" % (
        _fmt(_win[0]),
        _fmt(_win[1]),
        _fmt(_win[2]),
        _fmt(_win[3]),
    )
    fb._text(4, ph + 2, status, TFT_WHITE)
    fb._text(
        4, ph + 2 + _ROW, "Arrows:pan +/-:zoom R:reset T:trace Ent:edit", TFT_DARKGREY
    )


def _panel_trace(fb, ph):
    fb._fill_rectangle(0, ph, _W, _H - ph, TFT_BLACK)
    if _param:
        xs, ys = _psamples
        n = len(xs)
        t = TMIN + (TMAX - TMIN) * _trace_i / (n - 1)
        x = xs[_trace_i]
        y = ys[_trace_i]
        if x != x or y != y:
            status = "t=%s x=undef y=undef" % _fmt(t)
        else:
            status = "t=%s x=%s y=%s" % (_fmt(t), _fmt(x), _fmt(y))
        color = TFT_GREEN
    else:
        x = _px2x(_trace_i)
        y = _samples[_trace_fn][_trace_i]
        if y != y:
            status = "Y%d: x=%s y=undef" % (_trace_fn + 1, _fmt(x))
        else:
            status = "Y%d: x=%s y=%s" % (_trace_fn + 1, _fmt(x), _fmt(y))
        color = SLOT_COLORS[_trace_fn]
    fb._text(4, ph + 2, status, color)
    fb._text(4, ph + 2 + _ROW, "</>:move Up/Dn:fn Ent:done", TFT_DARKGREY)


def _trace_cursor(fb, ph):
    if _param:
        xs, ys = _psamples
        x = xs[_trace_i]
        y = ys[_trace_i]
        if x != x or y != y:
            return
        px = int(_x2px(x))
        py = int(_y2py(y, ph))
    else:
        y = _samples[_trace_fn][_trace_i]
        px = _trace_i
        if y != y:
            fb._line(px, 0, px, ph - 1, TFT_WHITE)
            return
        py = int(_y2py(y, ph))
    if not (0 <= px < _W):
        return
    py = 0 if py < 0 else (ph - 1 if py >= ph else py)
    fb._line(px - 5, py, px + 5, py, TFT_WHITE)
    fb._line(px, py - 5, px, py + 5, TFT_WHITE)
    fb._circle(px, py, 3, TFT_WHITE)


def _render(fb):
    fb.fill_screen(TFT_BLACK)
    ph = _plot_height()
    _grid(fb, ph)
    _curves(fb, ph)
    _legend(fb)
    if _state == MODE_EDIT:
        _panel_edit(fb, ph)
    elif _state == MODE_GRAPH:
        _panel_graph(fb, ph)
    else:
        _trace_cursor(fb, ph)
        _panel_trace(fb, ph)
    fb.swap()


# ---------------------------------------------------------------- evaluation


def _compile_all():
    """Compile enabled expressions; returns True if all compiled."""
    ok = True
    slots = _pslots if _param else _slots
    for i, slot in enumerate(slots):
        slot["code"] = None
        slot["err"] = None
        text = "".join(slot["buf"]).strip()
        if not text:
            if _param:
                slot["err"] = "empty"
                ok = False
            continue
        if not _param and not slot["on"]:
            continue
        try:
            name = ("x(t)", "y(t)")[i] if _param else "Y%d" % (i + 1)
            slot["code"] = compile(text, name, "eval")
        except SyntaxError:
            slot["err"] = "syntax error"
            ok = False
        except Exception as e:
            slot["err"] = str(e)
            ok = False
    return ok


def _recompute():
    """Evaluate all compiled expressions over the current window."""
    global _psamples
    env = _env
    if _param:
        cx = _pslots[0]["code"]
        cy = _pslots[1]["code"]
        if cx is None or cy is None:
            _psamples = None
            return
        n = _W
        if _psamples is None:
            _psamples = (array("f", [NAN] * n), array("f", [NAN] * n))
        xs, ys = _psamples
        for i in range(n):
            env["t"] = TMIN + (TMAX - TMIN) * i / (n - 1)
            try:
                x = eval(cx, env)
                y = eval(cy, env)
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
        return

    for s in range(NSLOTS):
        slot = _slots[s]
        if slot["code"] is None or not slot["on"]:
            _samples[s] = None
            continue
        arr = _samples[s]
        if arr is None:
            arr = array("f", [NAN] * _W)
            _samples[s] = arr
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


def _traceable():
    """First slot index that has a plotted curve, or -1."""
    if _param:
        return 0 if _psamples else -1
    for i in range(NSLOTS):
        if _samples[i] is not None and _slots[i]["on"]:
            return i
    return -1


# ---------------------------------------------------------------- input


def _handle_edit(btn, inp):
    global _cur_slot, _param, _state, _plot_dirty
    slots = _pslots if _param else _slots
    nrows = len(slots)
    slot = slots[_cur_slot]

    if btn == BUTTON_UP:
        _cur_slot = (_cur_slot - 1) % nrows
    elif btn == BUTTON_DOWN:
        _cur_slot = (_cur_slot + 1) % nrows
    elif btn == BUTTON_LEFT:
        if slot["cur"] > 0:
            slot["cur"] -= 1
    elif btn == BUTTON_RIGHT:
        if slot["cur"] < len(slot["buf"]):
            slot["cur"] += 1
    elif btn == BUTTON_END:
        slot["cur"] = len(slot["buf"])
    elif btn == BUTTON_BACKSPACE:
        if slot["cur"] > 0:
            slot["buf"].pop(slot["cur"] - 1)
            slot["cur"] -= 1
            slot["err"] = None
    elif btn == BUTTON_F3:
        slot["buf"] = []
        slot["cur"] = 0
        slot["err"] = None
    elif btn == BUTTON_TAB:
        if not _param:
            slot["on"] = not slot["on"]
    elif btn == BUTTON_F2:
        _param = not _param
        _cur_slot = 0
        _compile_all()
        _plot_dirty = True
    elif btn == BUTTON_CENTER:
        if _compile_all():
            _state = MODE_GRAPH
        _plot_dirty = True
    else:
        ch = inp.button_to_char(btn)
        if ch and ch != "\n":
            slot["buf"].insert(slot["cur"], ch)
            slot["cur"] += 1
            slot["err"] = None


def _handle_graph(btn):
    global _state, _plot_dirty, _trace_fn, _trace_i
    dx = (_win[1] - _win[0]) / 8.0
    dy = (_win[3] - _win[2]) / 8.0

    if btn == BUTTON_LEFT:
        _win[0] -= dx
        _win[1] -= dx
        _plot_dirty = True
    elif btn == BUTTON_RIGHT:
        _win[0] += dx
        _win[1] += dx
        _plot_dirty = True
    elif btn == BUTTON_UP:
        _win[2] += dy
        _win[3] += dy
        _plot_dirty = True
    elif btn == BUTTON_DOWN:
        _win[2] -= dy
        _win[3] -= dy
        _plot_dirty = True
    elif btn in (BUTTON_PLUS, BUTTON_EQUAL):
        _zoom(0.5)
        _plot_dirty = True
    elif btn in (BUTTON_MINUS, BUTTON_UNDERSCORE):
        _zoom(2.0)
        _plot_dirty = True
    elif btn == BUTTON_R:
        _win[0], _win[1], _win[2], _win[3] = DEF_WIN
        _plot_dirty = True
    elif btn == BUTTON_T:
        fn = _traceable()
        if fn >= 0:
            _trace_fn = fn
            _trace_i = _W // 2
            _state = MODE_TRACE
    elif btn in (BUTTON_CENTER, BUTTON_E):
        _state = MODE_EDIT


def _zoom(factor):
    cx = (_win[0] + _win[1]) / 2.0
    cy = (_win[2] + _win[3]) / 2.0
    hx = (_win[1] - _win[0]) / 2.0 * factor
    hy = (_win[3] - _win[2]) / 2.0 * factor
    hx = max(MIN_SPAN / 2.0, min(MAX_SPAN / 2.0, hx))
    hy = max(MIN_SPAN / 2.0, min(MAX_SPAN / 2.0, hy))
    _win[0], _win[1] = cx - hx, cx + hx
    _win[2], _win[3] = cy - hy, cy + hy


def _handle_trace(btn):
    global _state, _trace_i, _trace_fn
    n = len(_psamples[0]) if _param else _W

    if btn == BUTTON_LEFT:
        if _trace_i > 0:
            _trace_i -= 1
    elif btn == BUTTON_RIGHT:
        if _trace_i < n - 1:
            _trace_i += 1
    elif btn == BUTTON_END:
        _trace_i = n - 1
    elif btn in (BUTTON_UP, BUTTON_DOWN) and not _param:
        step = -1 if btn == BUTTON_UP else 1
        fn = _trace_fn
        for _ in range(NSLOTS):
            fn = (fn + step) % NSLOTS
            if _samples[fn] is not None and _slots[fn]["on"]:
                break
        _trace_fn = fn
    elif btn in (BUTTON_CENTER, BUTTON_T):
        _state = MODE_GRAPH


# ---------------------------------------------------------------- lifecycle


def start(view_manager) -> bool:
    """Start the app"""
    global _slots, _pslots, _param, _cur_slot, _win, _samples, _psamples
    global _trace_fn, _trace_i, _state, _env, _plot_dirty, _draw_dirty
    global _W, _H, _CW, _CH, _ROW

    draw = view_manager.draw
    _W = int(draw.size.x)
    _H = int(draw.size.y)
    _CW = int(draw.font_size.x) or 6
    _CH = int(draw.font_size.y) or 8
    _ROW = _CH + 3

    _slots = [_new_slot(text) for text in DEFAULT_EXPRS]
    _pslots = [_new_slot(text) for text in DEFAULT_PARAM]
    _param = False
    _cur_slot = 0
    _win = list(DEF_WIN)
    _samples = [None] * NSLOTS
    _psamples = None
    _trace_fn = 0
    _trace_i = _W // 2
    _state = MODE_EDIT
    _env = _build_env()
    _compile_all()
    _plot_dirty = True
    _draw_dirty = True

    view_manager.input_manager.reset()
    return True


def run(view_manager) -> None:
    """Run the app"""
    global _plot_dirty, _draw_dirty

    # The ViewManager polls input_manager.button once per loop and resets
    # it after this call, so read the cached value instead of polling again
    # (a second poll would consume the next queued key).
    btn = view_manager.button

    if btn == BUTTON_BACK:
        view_manager.back()
        return

    if btn != BUTTON_NONE:
        if _state == MODE_EDIT:
            _handle_edit(btn, view_manager.input_manager)
        elif _state == MODE_GRAPH:
            _handle_graph(btn)
        else:
            _handle_trace(btn)
        _draw_dirty = True

    if _plot_dirty:
        _recompute()
        _plot_dirty = False
        _draw_dirty = True

    if _draw_dirty:
        _render(view_manager.draw)
        _draw_dirty = False


def stop(view_manager) -> None:
    """Stop the app"""
    from gc import collect

    global _slots, _pslots, _param, _cur_slot, _win, _samples, _psamples
    global _trace_fn, _trace_i, _state, _env, _plot_dirty, _draw_dirty

    _slots = None
    _pslots = None
    _param = False
    _cur_slot = 0
    _win = None
    _samples = None
    _psamples = None
    _trace_fn = 0
    _trace_i = 0
    _state = MODE_EDIT
    _env = None
    _plot_dirty = False
    _draw_dirty = False

    collect()
