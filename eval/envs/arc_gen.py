"""ARC-AGI Stream — self-contained procedural generator (borrowed from paper5:
"Useful Memories Become Faulty When Continuously Updated by LLMs", arXiv 2605.12978).

The paper decomposes an ARC-style task along TWO independent latent axes:
  - FAMILY = a selection rule: WHICH connected non-background objects participate.
  - SKILL  = a fixed transformation applied uniformly to every selected object.
The output is built on a BLANK canvas from the selected-and-transformed objects only
(paper's `apply_op_per_object`); non-selected objects are dropped. A task is a few-shot
program-synthesis episode: the solver sees K input->output demonstrations and must write
`def solve(grid)` that reproduces them (and generalizes to held-out test inputs).

WHY we borrowed this (session-15 gate hunt): it is the one regime with BOTH
  (a) a PRECISE, executable correctness signal (run the program, exact grid match) ->
      un-blinds the reference-free gate (vs dyck's blind NL self-critique), AND
  (b) genuine SHARED-PROCEDURE family structure -> a per-family skill can transfer to
      every instance, so the promotion gate finally has a robustly-beneficial skill to
      ACTIVATE (not reject). See docs/PROGRESS.md session-15.

Self-contained: pure Python 3.9 + numpy, NO ARC-GEN dependency, NO Docker, NO network.
We re-derive the family/skill decomposition from the paper's Tables 5-6 + App. B.2 helpers.

v1 scope: 7 skills x 3 families {color_property, largest, group_by_shape}. The paper's
other three families {detect_inside_frame_relation, detect_key_marker_rule (conditional),
compose_horizontal (2-panel)} are DEFERRED to v2 (noted at FAMILIES). 3 families x 7 skills
= 21 latent rules is already ample shared-procedure structure for the gate experiment.

`apply_rule()` IS the ground truth; `reference_solver_src()` emits a self-contained program
that reproduces it (used by the unit tests to prove every generated task is program-solvable
and that the exec runner agrees) -- the generator validates itself.
"""
from collections import Counter, deque

import numpy as np

BG = 0                              # background / black, per ARC convention
PALETTE = list(range(1, 10))        # object colors 1..9

# A small fixed shape library (cells normalized to a top-left origin). group_by_shape needs a
# well-defined "mode" shape, so shapes are drawn from this canonical set (not free-form blobs).
SHAPE_LIB = [
    frozenset({(0, 0)}),                                   # dot
    frozenset({(0, 0), (0, 1)}),                           # domino
    frozenset({(0, 0), (1, 0), (0, 1)}),                   # L-tromino
    frozenset({(0, 0), (0, 1), (0, 2)}),                   # 3-line
    frozenset({(0, 0), (0, 1), (1, 0), (1, 1)}),           # 2x2 square
    frozenset({(0, 1), (1, 0), (1, 1), (1, 2)}),           # T-tetromino
    frozenset({(0, 0), (0, 1), (0, 2), (1, 1)}),           # plus-ish
]


# --------------------------------------------------------------------------- objects
def extract_objects(grid):
    """4-connected components of equal NON-background color. grid: np.ndarray[int].

    Returns a list of dicts: {cells:[(r,c)...], color:int, bbox:(top,left,bottom,right),
    size:int}. 4-connectivity, matching the paper's App. B.2 `extract_objects`.
    """
    g = np.asarray(grid)
    h, w = g.shape
    seen = np.zeros((h, w), dtype=bool)
    objs = []
    for r in range(h):
        for c in range(w):
            if g[r, c] != BG and not seen[r, c]:
                color = int(g[r, c])
                cells = []
                dq = deque([(r, c)])
                seen[r, c] = True
                while dq:
                    y, x = dq.popleft()
                    cells.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and g[ny, nx] == color:
                            seen[ny, nx] = True
                            dq.append((ny, nx))
                ys = [y for y, _ in cells]
                xs = [x for _, x in cells]
                objs.append({"cells": cells, "color": color,
                             "bbox": (min(ys), min(xs), max(ys), max(xs)), "size": len(cells)})
    return objs


def _shape_key(obj):
    """Translation-normalized cell set -> a hashable shape identity (for group_by_shape)."""
    t, l, _, _ = obj["bbox"]
    return frozenset((r - t, c - l) for (r, c) in obj["cells"])


# --------------------------------------------------------------------------- skills
# Each skill maps a selected object -> a list of (row, col, color) cells to paint onto the
# blank output canvas. Non-selected objects contribute nothing (dropped). Out-of-bounds cells
# are clipped by the painter. Skill PARAMS (new color, offset, markers) are fixed per task.

def skill_keep(obj, p):
    return [(r, c, obj["color"]) for (r, c) in obj["cells"]]


def skill_recolor(obj, p):
    return [(r, c, p["new_color"]) for (r, c) in obj["cells"]]


def skill_translate(obj, p):
    dy, dx = p["offset"]
    return [(r + dy, c + dx, obj["color"]) for (r, c) in obj["cells"]]


def skill_flip_horizontal(obj, p):
    _, l, _, rgt = obj["bbox"]
    return [(r, l + rgt - c, obj["color"]) for (r, c) in obj["cells"]]


def skill_border(obj, p):
    """Keep the object and draw a one-cell border ring just outside its bounding box."""
    t, l, b, rgt = obj["bbox"]
    bc = p["border_color"]
    out = [(r, c, obj["color"]) for (r, c) in obj["cells"]]
    for c in range(l - 1, rgt + 2):
        out.append((t - 1, c, bc))
        out.append((b + 1, c, bc))
    for r in range(t - 1, b + 2):
        out.append((r, l - 1, bc))
        out.append((r, rgt + 1, bc))
    return out


def skill_mark_center(obj, p):
    """Keep the object and mark its bbox-center cell with a marker color."""
    t, l, b, rgt = obj["bbox"]
    cr, cc = (t + b) // 2, (l + rgt) // 2
    out = [(r, c, obj["color"]) for (r, c) in obj["cells"]]
    out.append((cr, cc, p["marker_color"]))
    return out


def skill_hollow(obj, p):
    """Erase the interior of the object, leaving only its outer border (cells with a
    non-object 4-neighbor, or on the grid edge)."""
    cellset = set(obj["cells"])
    out = []
    for (r, c) in obj["cells"]:
        nbrs = [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
        if all(n in cellset for n in nbrs):
            continue                                   # interior -> erased
        out.append((r, c, obj["color"]))
    return out


SKILLS = {
    "keep": skill_keep,
    "recolor": skill_recolor,
    "translate": skill_translate,
    "flip_horizontal": skill_flip_horizontal,
    "border": skill_border,
    "mark_center": skill_mark_center,
    "hollow": skill_hollow,
}


# --------------------------------------------------------------------------- families
# A family selects WHICH objects participate. Returns the selected sub-list.

def fam_color_property(objs, g, p):
    return [o for o in objs if o["color"] == p["target_color"]]


def fam_largest(objs, g, p):
    if not objs:
        return []
    m = max(o["size"] for o in objs)
    return [o for o in objs if o["size"] == m]


def fam_group_by_shape(objs, g, p):
    if not objs:
        return []
    counts = Counter(_shape_key(o) for o in objs)
    mode_shape, _ = counts.most_common(1)[0]
    return [o for o in objs if _shape_key(o) == mode_shape]


FAMILIES = {
    "color_property": fam_color_property,
    "largest": fam_largest,
    "group_by_shape": fam_group_by_shape,
    # v2 (deferred): "inside_frame" (needs a hollow-frame object), "key_marker" (conditional
    # all-or-none gated by grid[0,0]), "compose_horizontal" (two-panel input). See module docstring.
}


def apply_rule(grid, family, skill, params):
    """THE GROUND TRUTH. Select objects by `family`, transform each by `skill`, composite onto
    a blank canvas of the same shape. Returns np.ndarray[int]."""
    g = np.asarray(grid)
    objs = extract_objects(g)
    selected = FAMILIES[family](objs, g, params)
    canvas = np.zeros_like(g)
    h, w = canvas.shape
    for o in selected:
        for (r, c, col) in SKILLS[skill](o, params):
            if 0 <= r < h and 0 <= c < w:
                canvas[r, c] = col
    return canvas


# --------------------------------------------------------------------------- scene synthesis
def _place_objects(h, w, shapes, colors, rng):
    """Place each (shape, color) on an h x w grid as a SEPARATE 4-connected component: every
    placed shape keeps a >=1-cell halo from the border and from every other shape (so nothing
    merges and border/translate have room). Returns the grid, or None if placement failed."""
    g = np.zeros((h, w), dtype=int)
    blocked = np.zeros((h, w), dtype=bool)            # cells that must stay empty (objects + halo)
    for shape, color in zip(shapes, colors):
        rs = [r for r, _ in shape]
        cs = [c for _, c in shape]
        sh, sw = max(rs) + 1, max(cs) + 1
        placed = False
        for _ in range(60):
            top = rng.integers(1, max(2, h - sh - 1))
            left = rng.integers(1, max(2, w - sw - 1))
            cells = [(top + r, left + c) for (r, c) in shape]
            if any(not (0 <= r < h and 0 <= c < w) for r, c in cells):
                continue
            if any(blocked[r, c] for r, c in cells):
                continue
            for (r, c) in cells:
                g[r, c] = color
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w:
                            blocked[nr, nc] = True
            placed = True
            break
        if not placed:
            return None
    return g


def _sample_params(family, skill, rng):
    """Task-level params, decided ONCE and held stable across all demos+tests (this IS the
    latent rule the solver must infer)."""
    p = {}
    if skill == "recolor":
        p["new_color"] = int(rng.choice(PALETTE))
    elif skill == "translate":
        p["offset"] = (int(rng.integers(-2, 3)), int(rng.integers(-2, 3)))
        if p["offset"] == (0, 0):
            p["offset"] = (1, 1)
    elif skill == "border":
        p["border_color"] = int(rng.choice(PALETTE))
    elif skill == "mark_center":
        p["marker_color"] = int(rng.choice(PALETTE))
    if family == "color_property":
        # the target color is a FIXED part of the rule -> every scene must carry it.
        cols = list(rng.choice(PALETTE, size=2, replace=False))
        p["target_color"] = int(cols[0])
        p["_contrast_color"] = int(cols[1])
    return p


def _gen_scene(family, rng, params):
    """One random grid whose structure makes `family`'s selection NON-TRIVIAL (selects some but
    not all objects, with an inferable rule) and is CONSISTENT with the task-level `params`
    (e.g. color_property scenes always contain the fixed target color). Returns the grid or None."""
    h = int(rng.integers(12, 17))
    w = int(rng.integers(12, 17))
    n = int(rng.integers(3, 6))
    if family == "color_property":
        # >=1 object of the FIXED target color + >=1 of the contrast color (so selection is real).
        tgt, other = params["target_color"], params["_contrast_color"]
        n_t = int(rng.integers(1, max(2, n - 1)))
        colors = [tgt] * n_t + [other] * (n - n_t)
        rng.shuffle(colors)
        shapes = [SHAPE_LIB[int(rng.integers(0, len(SHAPE_LIB)))] for _ in range(n)]
    elif family == "largest":
        # distinct shapes sorted by size -> a (near-)unique largest object.
        idx = list(rng.choice(len(SHAPE_LIB), size=min(n, len(SHAPE_LIB)), replace=False))
        shapes = sorted((SHAPE_LIB[i] for i in idx), key=len)
        colors = [int(rng.choice(PALETTE)) for _ in shapes]
    elif family == "group_by_shape":
        # one shape is the strict MODE (appears most), plus a couple of distractor shapes.
        mode = SHAPE_LIB[int(rng.integers(0, len(SHAPE_LIB)))]
        k_mode = int(rng.integers(2, 4))
        others = [s for s in SHAPE_LIB if s != mode]
        distract = [others[int(rng.integers(0, len(others)))] for _ in range(max(1, n - k_mode))]
        shapes = [mode] * k_mode + distract
        rng.shuffle(shapes)
        colors = [int(rng.choice(PALETTE)) for _ in shapes]
    else:
        raise ValueError("unknown family %s" % family)
    return _place_objects(h, w, shapes, colors, rng)


def gen_task(family, skill, rng, n_demos=4, n_tests=2, max_tries=200):
    """Synthesize one task: K demos + M held-out tests sharing ONE latent (family, skill, params)
    rule. Returns a dict {family, skill, params, demos:[(in,out)...], tests:[(in,out)...]} with
    grids as list[list[int]]. Rejects degenerate scenes (empty selection / output == input /
    out-of-bounds) and retries. Raises RuntimeError if it cannot build enough clean examples."""
    params = _sample_params(family, skill, rng)
    pairs = []
    tries = 0
    need = n_demos + n_tests
    while len(pairs) < need and tries < max_tries:
        tries += 1
        grid = _gen_scene(family, rng, params)
        if grid is None:
            continue
        objs = extract_objects(grid)
        selected = FAMILIES[family](objs, grid, params)
        if not selected:
            continue
        out = apply_rule(grid, family, skill, params)
        if np.array_equal(out, np.asarray(grid)):
            continue                                     # trivial (identity) -> reject
        if out.sum() == 0:
            continue                                     # everything clipped away -> reject
        pairs.append((np.asarray(grid).tolist(), out.tolist()))
    if len(pairs) < need:
        raise RuntimeError("gen_task(%s,%s): only %d/%d clean examples" % (family, skill, len(pairs), need))
    # drop private generator-only keys (prefixed _) from the persisted rule
    clean = {k: v for k, v in params.items() if not k.startswith("_")}
    return {"family": family, "skill": skill, "params": clean,
            "demos": pairs[:n_demos], "tests": pairs[n_demos:need]}


# --------------------------------------------------------------------------- reference solver
def reference_solver_src(family, skill, params):
    """Emit a SELF-CONTAINED `solve(grid)` Python source that reproduces apply_rule for this
    (family, skill, params). Used by the unit tests to prove the task is program-solvable and
    that the exec runner agrees with the generator. NOT shown to the agent."""
    return (
        "from collections import Counter, deque\n"
        "PARAMS = %r\nFAMILY = %r\nSKILL = %r\n" % (params, family, skill)
        + _SOLVER_BODY
    )


# The body re-implements extract_objects + the 7 skills + 3 families, then solve().
_SOLVER_BODY = '''
def _objs(g):
    h=len(g); w=len(g[0]) if h else 0
    seen=[[False]*w for _ in range(h)]; out=[]
    for r in range(h):
        for c in range(w):
            if g[r][c]!=0 and not seen[r][c]:
                col=g[r][c]; cells=[]; dq=deque([(r,c)]); seen[r][c]=True
                while dq:
                    y,x=dq.popleft(); cells.append((y,x))
                    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny,nx=y+dy,x+dx
                        if 0<=ny<h and 0<=nx<w and not seen[ny][nx] and g[ny][nx]==col:
                            seen[ny][nx]=True; dq.append((ny,nx))
                ys=[y for y,_ in cells]; xs=[x for _,x in cells]
                out.append({"cells":cells,"color":col,"bbox":(min(ys),min(xs),max(ys),max(xs)),"size":len(cells)})
    return out

def _shape(o):
    t,l,_,_=o["bbox"]; return frozenset((r-t,c-l) for r,c in o["cells"])

def _select(objs,g):
    if FAMILY=="color_property":
        return [o for o in objs if o["color"]==PARAMS["target_color"]]
    if FAMILY=="largest":
        if not objs: return []
        m=max(o["size"] for o in objs); return [o for o in objs if o["size"]==m]
    if FAMILY=="group_by_shape":
        if not objs: return []
        cnt=Counter(_shape(o) for o in objs); mode=cnt.most_common(1)[0][0]
        return [o for o in objs if _shape(o)==mode]
    return []

def _paint(o):
    col=o["color"]; t,l,b,r=o["bbox"]; cells=o["cells"]
    if SKILL=="keep": return [(y,x,col) for y,x in cells]
    if SKILL=="recolor": return [(y,x,PARAMS["new_color"]) for y,x in cells]
    if SKILL=="translate":
        dy,dx=PARAMS["offset"]; return [(y+dy,x+dx,col) for y,x in cells]
    if SKILL=="flip_horizontal": return [(y,l+r-x,col) for y,x in cells]
    if SKILL=="border":
        bc=PARAMS["border_color"]; res=[(y,x,col) for y,x in cells]
        for x in range(l-1,r+2): res.append((t-1,x,bc)); res.append((b+1,x,bc))
        for y in range(t-1,b+2): res.append((y,l-1,bc)); res.append((y,r+1,bc))
        return res
    if SKILL=="mark_center":
        cr,cc=(t+b)//2,(l+r)//2; res=[(y,x,col) for y,x in cells]; res.append((cr,cc,PARAMS["marker_color"])); return res
    if SKILL=="hollow":
        cs=set(cells); res=[]
        for y,x in cells:
            if all((y+dy,x+dx) in cs for dy,dx in ((1,0),(-1,0),(0,1),(0,-1))): continue
            res.append((y,x,col))
        return res
    return []

def solve(grid):
    g=[list(row) for row in grid]; h=len(g); w=len(g[0]) if h else 0
    objs=_objs(g); sel=_select(objs,g)
    out=[[0]*w for _ in range(h)]
    for o in sel:
        for y,x,col in _paint(o):
            if 0<=y<h and 0<=x<w: out[y][x]=col
    return out
'''
