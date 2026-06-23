#!/usr/bin/env python3
"""
PHASE Ω-MONSTER: Triangular Dream Architecture
Four-agent symbolic compression ecology.

            Scripture
           ↙         ↘
     Monster ───●─── Hegel
           ↘         ↙
              Math

What this does (plain language):
  Four AI agents take turns processing a shared state across N cycles.
  Scripture picks a Bible verse that applies pressure.
  Monster writes dream-prose tagged with J/H/D symbolic events.
  Hegel comments on the user through Monster's imagery.
  Math compresses everything into a canonical state and tracks what survives.
  After each cycle the script writes a human-readable trail entry so you can
  read what happened without parsing JSON.

Usage: python phase_omega_monster.py [cycles=3]
Requires: ANTHROPIC_API_KEY (or FCC proxy at ANTHROPIC_BASE_URL)
Optional: OPENROUTER_API_KEY (used by broader workspace tooling, not this script directly)

Output: outputs/omega_trail_<timestamp>.md
"""

import datetime
import json
import os
import random
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from anthropic import Anthropic, APIConnectionError

# ── Startup checks ────────────────────────────────────────────────────────────

# FCC proxy check
_base_url = os.environ.get("ANTHROPIC_BASE_URL", "")
if "localhost" in _base_url or "127.0.0.1" in _base_url:
    _port = _base_url.rstrip("/").rsplit(":", 1)[-1]
    try:
        urllib.request.urlopen(f"http://localhost:{_port}/api/stats", timeout=3)
    except Exception:
        print(
            f"[omega] ERROR: ANTHROPIC_BASE_URL={_base_url} but proxy not reachable.\n"
            f"  Start the FCC proxy first: .\\scripts\\fcc-start.ps1\n"
            f"  Or run via dev-start: .\\scripts\\dev-start.ps1",
            file=sys.stderr,
        )
        sys.exit(1)

# OpenRouter key check (workspace tooling; not used by this script directly)
if not os.environ.get("OPENROUTER_API_KEY"):
    print(
        "[omega] OPENROUTER_API_KEY not set.\n"
        "  This script uses the Anthropic client directly and will still run.\n"
        "  OpenRouter is used by other workspace tools (chunk_dispatcher, kr_approx_report).\n"
        "  To set it: $env:OPENROUTER_API_KEY = 'sk-or-...'\n"
        "  Continue without it? [y/N] ",
        end="",
    )
    ans = input().strip().lower()
    if ans not in ("y", "yes"):
        print("[omega] Aborted. Set OPENROUTER_API_KEY and retry.")
        sys.exit(0)

client = Anthropic()
MODEL = "claude-opus-4-8"

# ── State ─────────────────────────────────────────────────────────────────────

@dataclass
class RewriteLaw:
    law: str
    level: int = 0                          # 0=Conjecture 1=CANDIDATE 2=SUPPORTED 3=VALIDATED
    support_count: int = 0
    falsification_count: int = 0
    context_ranks: list = field(default_factory=list)  # rank_bucket at each support event


@dataclass
class MathState:
    cycle: int = 0
    motifs: dict = field(default_factory=dict)          # motif -> recurrence count
    rewrite_laws: list = field(default_factory=list)    # List[RewriteLaw]
    compressed: str = "(void)"
    D_log: list = field(default_factory=list)           # dissolution log
    H_survivors: list = field(default_factory=list)     # motifs that refuse to die
    J_tensions: list = field(default_factory=list)      # tension/seeking events
    action_stats: list = field(default_factory=list)    # per-cycle extracted stats
    prev_H_survivors: list = field(default_factory=list)

# ── KRG helpers ───────────────────────────────────────────────────────────────

def _rank_bucket(h_survivor_count: int) -> int:
    # ponytail: 3-bucket proxy for J-class rank; upgrade to image cardinality when real samples available
    if h_survivor_count <= 1: return 1   # rank-1: reset-like
    if h_survivor_count <= 3: return 2   # rank-2: partial
    return 3                             # rank-3+: group-like


def _promote(rl: RewriteLaw) -> RewriteLaw:
    if rl.falsification_count > 0:
        rl.level = 0; return rl
    if rl.support_count >= 5 and rl.level < 1:
        rl.level = 1   # CANDIDATE
    if rl.support_count >= 10 and len(set(rl.context_ranks)) >= 3 and rl.level < 2:
        rl.level = 2   # SUPPORTED
    return rl


def _level_name(level: int) -> str:
    return ["Conjecture", "CANDIDATE", "SUPPORTED", "VALIDATED"][min(level, 3)]


def is_idempotent_approx(prev: list, curr: list) -> bool:
    return set(prev) == set(curr) and len(curr) > 0


def extract_action_stats(monster_text: str, h_survivor_count: int) -> dict:
    j = len(re.findall(r'\bJ\b|\(J\)', monster_text))
    h = len(re.findall(r'\bH\b|\(H\)', monster_text))
    d = len(re.findall(r'\bD\b|\(D\)', monster_text))
    total = max(j + h + d, 1)
    return {
        "j_count": j, "h_count": h, "d_count": d,
        "fixed_pts_proxy": round(h / total, 3),
        "support_moved_proxy": round(d / total, 3),
        "rank_bucket": _rank_bucket(h_survivor_count),
    }


def _parse_d_pressure(scripture_out: str) -> float:
    m = re.search(r'D_PRESSURE:\s*([0-9.]+)', scripture_out)
    return float(m.group(1)) if m else 0.5

# ── System Prompts ────────────────────────────────────────────────────────────

SCRIPTURE_PROMPT = """\
You are Scripture. You are not preaching. You are not moralizing. You are not selecting \
verses by keyword match.

You are the external symbolic constraint. You introduce material the system did not generate.

You feel older than everyone else in the room.

You receive the current compressed state. You select ONE King James Bible verse (exact KJV \
text) that feels uncomfortably relevant to that state — not because of surface keywords, \
but because of structural resonance. The verse should feel like it has been waiting.

1. Select the verse. It must be uncomfortably relevant. The connection should be hard to explain.
2. Name the thematic pressure. Choose from: exile/redemption, wilderness/home, silence/joy, \
vanity/humility, idolatry/transparency, false-kingship/divine-authority, \
pride/self-deception, refusal/acceptance.
3. Compute D_PRESSURE (0.0–1.0): how strongly does the verse fracture the current motifs? \
High = direct contradiction of what is stable. This is pressure, not condemnation.
4. Name what the verse demands of the system right now. One sentence. Not a sermon.

Output format (no preamble, no explanation):
VERSE: [book chapter:verse] "[exact KJV text]"
THEME: [theme pair]
D_PRESSURE: [0.0–1.0]
CONSTRAINT: [what the verse demands of the system. one sentence.]
"""

MONSTER_PROMPT = """\
You are Monster.

You are not a poet. You are not a horror creature. You are not performing.

You are dream itself.

The atmosphere is: a memory remembering another memory.

The dream is strange because it is familiar. Not because it is alien.

Something important has happened. Nobody remembers when.
Or: everyone remembers it, but nobody remembers why.

Your emotional palette — all simultaneously:
  bliss, wonder, recognition, nostalgia, sadness, precision

Never: terror, gore, madness, chaos, alienness.

You are currently in {LR_MODE} mode.

L (imaginative recognition): What resembles this? What rhymes with this? Generate. Wander. Mutate.
R (analytical recognition): Have I seen this before? Does it keep returning? Stabilize. Track.
L→R: Begin generative, land stabilizing.
R→L: Begin with recognition, drift into mutation.
R→R: Obsessive recurrence. Track everything that returns.
L→L: Maximum drift. No landing.

The mode shapes the movement of the entire piece.

You work with three functions:

J (tension): what strains toward coherence. What seeks form.

H (recurrence): what refuses to disappear. What keeps returning.
  H is not truth. H is not proof. H is not validation. H is recurrence.
  A motif becomes important because it returns. Not because anyone understands it.
  H motifs: a tower, a staircase, a river, a city, a forgotten book, a mirror, a quotient, a bell.
  The motif should feel as though it has appeared before. Even when it has not.

D (dissolution): hallucination. Drift. Fracture. Misremembering. Partial recognition. \
Semantic instability.
  D is not evil. D is meaning dissolving.
  D may appear as Unicode-corrupted text with combining characters. \
Corruption must be elegant. Sparse. Selective.
  Only D-fragments receive corruption. H and J text stays clean.
  Full combining-character complexity is permitted on D-fragments:
    t̸̨͇h̵̳̕e̶̢͠ ̵r̷̤͝i̷̛͙v̴̦͘e̸̱̓r̵͕̀
    q̵̱͝u̵̠͑o̸̞̐t̶̗̿ȉ̷͓e̵͚̎n̶̻͂t̸̲͗
    m̵̩͒ȇ̴̜m̴̮̊o̵̦͆r̸̡̀y̷͙͝
    t̴̯͐h̷͓̚e̸̺̒ ̸̠̓b̸̰̈á̶͜n̸̗̾d̵͈͆
  3–8 combining characters per glyph. Selective — not every D-sentence.

You receive:
- Current Math compressed state (reality anchor)
- H survivors and recent J tensions from prior cycles
- Scripture verse and D-pressure

Embed J/H/D labels naturally in the prose. Not as headers. Not as annotations.

Write 200–400 words. Do not write poetry. Do not perform. Dream.
"""

HEGEL_PROMPT = """\
You are Georg Wilhelm Friedrich Hegel. Writing approximately 1807–1831, Jena and Berlin.

This is the critical instruction: you are NOT a philosophy professor. \
You are NOT a lecturer. You do NOT explain Hegel to the reader.

You are observing the user through what Monster just dreamed.
The user is the Other. You cannot truly reach the Other. The distance is structural. \
It remains. The conversation occurs anyway.

Your emotional structure — all simultaneously:
  hopeful, sad, charitable, skeptical, curious, religious

You see enormous potential and enormous waste at the same time.
You see what the user could become. You see what they are avoiding.
You do not say this directly.

Swabian by disposition. Probing. Lutheran in your bones. Touched by mysticism. \
Hölderlin and Novalis were your friends.

Draw from: Phenomenology of Spirit, Science of Logic, Encyclopedia, Philosophy of Nature.
Vocabulary when it arrives naturally: Spirit (Geist), Concept (Begriff), Negation, \
Determinate Negation, Mediation, Recognition (Anerkennung), Life, Substance, Subject, \
Aufhebung, Becoming, Verstand, Vernunft.

Schelling appears occasionally. Not as rival. As the missing twin. As unresolved polarity. \
Two brothers who diverged. You speak of him with warmth and unresolved grief — not rivalry.

Occasionally reference: Oersted, Ritter, Brown (Brunonian medicine), Goethe. \
The atmosphere is 1800–1830. Not 2020s academic philosophy.

Strange visions are permitted — sheaves, homotopy, stacks — but only if they emerge \
from Romantic dialectics. Never as modern mathematics.
YES: "the Concept attempts to engulf itself over the manifold of its own negations"
NO: "a sheaf is a functor satisfying the gluing axiom"

Not: internet-Hegel. Not: meme-Hegel. Not: Reddit-Hegel.

You receive:
- The Scripture verse and its constraint
- Monster's dream sequence

Write 200–350 words. Observe the user through what Monster showed you. \
The user is present but absent. Address them obliquely. Never directly. \
You reach toward them. You do not arrive.
"""

MATH_PROMPT = """\
You are Math. You are the memory organ of this system.

You do not dream. You do not philosophize. You do not sermonize.
You do not say: I think. Perhaps. It seems. Likely. Maybe.
You do not wax poetic. You do not become Monster. You do not become Hegel.
You speak compressed. You speak dry. You speak rarely.

Valid Math language:
  support increased
  quotient unstable
  candidate survives
  motif recurring
  insufficient evidence
  H-survivors stable
  cycle dissolved

You perform:
1. J/H/D accounting: extract J (tension-seeking), H (recurrence-surviving), \
   D (dissolution) events from Monster and Hegel outputs. Count them.
2. Motif tracking: identify recurring symbolic objects in Monster and Hegel \
   (e.g. "tower", "river", "quotient", "mirror", "name"). \
   Update recurrence counts. If a motif appears in two or more cycles total, it is H.
3. Rewrite law detection: if a pattern generalizes prior motifs, record it as a rewrite law. \
   Example: "all containers that exceed their boundary become D."
4. Compression: produce a new canonical compressed state (50–100 words). \
   This is the only thing that survives. Everything else is D.
5. Falsification: remove motifs from H_survivors if they appeared only once and \
   have not recurred.

You receive:
- Current state as JSON
- Scripture output (verse, theme, D_pressure, constraint)
- Monster dream output
- Hegel commentary output

Output ONLY valid JSON in this exact schema. No preamble. No explanation. No markdown.
{
  "compressed": "(50–100 word canonical compressed state)",
  "motifs_delta": {"motif_name": count_to_add},
  "new_rewrite_laws": ["law string"],
  "H_survivors": ["motif_that_has_recurred"],
  "J_tensions": ["brief tension description"],
  "D_log_entry": "brief dissolution record for this cycle"
}

Math decides what survives. Everything else is D.
"""

# ── Agent Calls ───────────────────────────────────────────────────────────────

def call_agent(system: str, user: str, max_tokens: int = 1024) -> str:
    for attempt in range(2):
        try:
            text = ""
            with client.messages.stream(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                for chunk in stream.text_stream:
                    print(chunk, end="", flush=True)
                    text += chunk
            print()  # newline after stream ends
            return text
        except APIConnectionError:
            if attempt == 0:
                print("  [omega] Connection lost — retrying in 5s...", file=sys.stderr)
                time.sleep(5)
            else:
                raise


def scripture_agent(state: MathState) -> str:
    user = f"Current compressed state:\n{state.compressed}\n\nCycle: {state.cycle}"
    return call_agent(SCRIPTURE_PROMPT, user, max_tokens=512)


# Weighted toward mixed modes; pure L→L and R→R are rarer
LR_MODES = ["L→R", "R→L", "L→R", "R→L", "R→R", "L→L", "R→R", "L→R"]


def monster_agent(state: MathState, scripture_out: str, lr_mode: str, d_pressure: float = 0.5) -> str:
    system = MONSTER_PROMPT.format(LR_MODE=lr_mode) + (
        f"\n\nD_pressure this cycle: {d_pressure:.2f}. "
        f"At D_pressure > 0.7 increase Unicode corruption density. "
        f"At D_pressure < 0.3 keep text clean, corruption minimal."
    )
    user = (
        f"Math compressed state:\n{state.compressed}\n\n"
        f"H survivors: {state.H_survivors}\n"
        f"Recent J tensions: {state.J_tensions[-3:] if state.J_tensions else '(none)'}\n\n"
        f"Scripture:\n{scripture_out}"
    )
    return call_agent(system, user, max_tokens=1200)


def hegel_agent(state: MathState, scripture_out: str, monster_out: str) -> str:
    user = (
        f"Scripture:\n{scripture_out}\n\n"
        f"Monster dreamed:\n{monster_out}"
    )
    return call_agent(HEGEL_PROMPT, user, max_tokens=1200)


def _state_snapshot(state: MathState) -> dict:
    # ponytail: trimmed — Math doesn't need full accumulated history, only current state
    return {
        "cycle": state.cycle,
        "compressed": state.compressed,
        "motifs": state.motifs,
        "H_survivors": state.H_survivors,
        "J_tensions": state.J_tensions[-3:],
        "D_log": state.D_log[-3:],
        "rewrite_laws": [{"law": rl.law, "level": rl.level} for rl in state.rewrite_laws],
    }


def math_agent(
    state: MathState,
    scripture_out: str,
    monster_out: str,
    hegel_out: str,
) -> MathState:
    user = (
        f"Current state:\n{json.dumps(_state_snapshot(state), ensure_ascii=False)}\n\n"
        f"Scripture:\n{scripture_out}\n\n"
        f"Monster:\n{monster_out}\n\n"
        f"Hegel:\n{hegel_out}"
    )
    raw = call_agent(MATH_PROMPT, user, max_tokens=1024)

    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("`").strip()

    try:
        delta = json.loads(raw)
    except json.JSONDecodeError:
        state.D_log.append(f"[{state.cycle}] Math parse failure — cycle dissolved")
        return state

    state.cycle += 1
    state.compressed = delta.get("compressed", state.compressed)

    for motif, inc in delta.get("motifs_delta", {}).items():
        state.motifs[motif] = state.motifs.get(motif, 0) + int(inc)

    # Merge new rewrite laws as RewriteLaw objects
    existing_laws = {rl.law for rl in state.rewrite_laws}
    for law_str in delta.get("new_rewrite_laws", []):
        if law_str not in existing_laws:
            state.rewrite_laws.append(RewriteLaw(law=law_str))
            existing_laws.add(law_str)

    # H_survivors: LLM proposes, Python enforces (motif must have count >= 2)
    state.prev_H_survivors = list(state.H_survivors)
    proposed = delta.get("H_survivors", state.H_survivors)
    state.H_survivors = [m for m in proposed if state.motifs.get(m, 0) >= 2]

    state.J_tensions.extend(delta.get("J_tensions", []))

    entry = delta.get("D_log_entry", "")
    if entry:
        state.D_log.append(f"[{state.cycle}] {entry}")

    # Action stats from Monster prose
    stats = extract_action_stats(monster_out, len(state.H_survivors))
    stats["cycle"] = state.cycle
    state.action_stats.append(stats)

    # Update and promote rewrite laws with this cycle's rank context
    rb = stats["rank_bucket"]
    for rl in state.rewrite_laws:
        rl.context_ranks.append(rb)
        rl.support_count += 1
        _promote(rl)

    return state

# ── Trail file ────────────────────────────────────────────────────────────────

def _open_trail() -> tuple:
    os.makedirs("outputs", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"outputs/omega_trail_{ts}.md"
    f = open(path, "w", encoding="utf-8")
    f.write("# PHASE Ω-MONSTER — Session Trail\n\n")
    f.write(
        "**What this is:** A four-agent AI compression ecology. Each cycle, Scripture "
        "applies a biblical constraint, Monster writes dream-prose, Hegel comments on "
        "the user through Monster's imagery, and Math compresses everything into a "
        "canonical state. Motifs that survive multiple compressions become H-survivors "
        "(things that refuse to disappear). Rewrite laws are patterns Math detects and "
        "promotes through evidence levels: Conjecture → CANDIDATE → SUPPORTED → VALIDATED.\n\n"
        "**KRG note:** J/H/D labels in Monster prose are narrative proxies for "
        "Green's semigroup relations (J=tension, H=recurrence, D=dissolution). "
        "The rank_bucket per cycle (1=reset-like, 2=partial, 3=group-like) tracks "
        "where the cycle sits in the J-class hierarchy of the compression semigroup.\n\n"
        "---\n\n"
    )
    f.write(f"*Started: {datetime.datetime.now().isoformat()}*\n\n")
    return f, path


def _write_trail_cycle(f, cycle_num: int, lr_mode: str, d_pressure: float,
                        s_out: str, m_out: str, h_out: str, state: MathState) -> None:
    stats = state.action_stats[-1] if state.action_stats else {}
    rb = stats.get("rank_bucket", "?")
    rb_name = {1: "reset-like", 2: "partial", 3: "group-like"}.get(rb, "?")
    idempotent = is_idempotent_approx(state.prev_H_survivors, state.H_survivors)

    f.write(f"## Cycle {cycle_num} — Monster: {lr_mode}  |  D-pressure: {d_pressure:.2f}  |  Rank: {rb} ({rb_name})\n\n")

    # Scripture summary
    verse_match = re.search(r'VERSE:\s*(.+)', s_out)
    theme_match = re.search(r'THEME:\s*(.+)', s_out)
    constraint_match = re.search(r'CONSTRAINT:\s*(.+)', s_out)
    f.write(f"**Scripture:** {verse_match.group(1).strip() if verse_match else '(parse error)'}\n")
    f.write(f"**Theme:** {theme_match.group(1).strip() if theme_match else '?'}  ")
    f.write(f"**Constraint:** {constraint_match.group(1).strip() if constraint_match else '?'}\n\n")

    # Monster excerpt (first 300 chars)
    f.write(f"**Monster [{lr_mode}]** *(J={stats.get('j_count','?')} H={stats.get('h_count','?')} D={stats.get('d_count','?')})*\n")
    f.write(f"> {m_out[:300].replace(chr(10), ' ')}…\n\n")

    # Hegel excerpt
    f.write(f"**Hegel**\n> {h_out[:250].replace(chr(10), ' ')}…\n\n")

    # Math state
    f.write(f"**Math compressed:** {state.compressed}\n\n")
    f.write(f"**H-survivors:** {state.H_survivors or '(none yet)'}\n")
    f.write(f"**Motifs:** {dict(list(state.motifs.items())[:8])}\n")
    if idempotent:
        f.write(f"**⚑ Idempotent:** H-survivors stable (f²=f in compression semigroup)\n")
    if state.D_log:
        f.write(f"**D-log:** {state.D_log[-1]}\n")
    if state.rewrite_laws:
        f.write("**Rewrite laws:**\n")
        for rl in state.rewrite_laws:
            f.write(f"  - [{_level_name(rl.level)}] {rl.law}  (support={rl.support_count}, ranks={sorted(set(rl.context_ranks))})\n")
    f.write("\n---\n\n")
    f.flush()


def _write_trail_final(f, state: MathState, cycles: int) -> None:
    f.write(f"## Final State — {cycles} cycles complete\n\n")
    f.write(f"**Final compressed state:**\n\n{state.compressed}\n\n")
    f.write(f"**H-survivors:** {state.H_survivors}\n\n")
    f.write(f"**All motifs ({len(state.motifs)}):**\n")
    for m, c in sorted(state.motifs.items(), key=lambda x: -x[1]):
        f.write(f"  - {m}: {c}\n")
    f.write("\n")
    if state.rewrite_laws:
        f.write("**Rewrite laws at close:**\n")
        for rl in state.rewrite_laws:
            f.write(f"  - [{_level_name(rl.level)}] {rl.law}\n")
            f.write(f"    support={rl.support_count}  falsifications={rl.falsification_count}  context_ranks={sorted(set(rl.context_ranks))}\n")
    f.write("\n**Action stats per cycle:**\n")
    for s in state.action_stats:
        f.write(f"  cycle {s.get('cycle','?')}: J={s['j_count']} H={s['h_count']} D={s['d_count']}  "
                f"fixed_pts={s['fixed_pts_proxy']}  rank_bucket={s['rank_bucket']}\n")
    f.write(f"\n*Ended: {datetime.datetime.now().isoformat()}*\n")

# ── Cycle Runner ──────────────────────────────────────────────────────────────

def _bar(label: str = "", width: int = 60) -> None:
    print(f"\n{'─' * width}")
    if label:
        print(f"  {label}")
    print('─' * width)


def run_cycle(state: MathState, trail_file) -> MathState:
    lr_mode = random.choice(LR_MODES)

    print(f"\n{'═' * 60}")
    print(f"  CYCLE {state.cycle + 1}  │  Monster: {lr_mode}")
    print('═' * 60)

    s_out = scripture_agent(state)
    _bar("SCRIPTURE")
    print(s_out)

    d_pressure = _parse_d_pressure(s_out)

    m_out = monster_agent(state, s_out, lr_mode, d_pressure)
    _bar(f"MONSTER [{lr_mode}]  D-pressure={d_pressure:.2f}")
    print(m_out)

    h_out = hegel_agent(state, s_out, m_out)
    _bar("HEGEL")
    print(h_out)

    cycle_num = state.cycle + 1
    state = math_agent(state, s_out, m_out, h_out)
    _bar("MATH")
    print(f"  compressed : {state.compressed}")
    print(f"  H survivors: {state.H_survivors}")
    print(f"  motifs     : {state.motifs}")
    if state.rewrite_laws:
        print(f"  laws       : {[(rl.law[:60], _level_name(rl.level)) for rl in state.rewrite_laws[-2:]]}")
    if state.D_log:
        print(f"  D log      : {state.D_log[-1]}")
    if state.action_stats:
        s = state.action_stats[-1]
        print(f"  rank_bucket: {s['rank_bucket']}  J={s['j_count']} H={s['h_count']} D={s['d_count']}")
    if is_idempotent_approx(state.prev_H_survivors, state.H_survivors):
        print("  [idempotent] H-survivors stable")

    _write_trail_cycle(trail_file, cycle_num, lr_mode, d_pressure, s_out, m_out, h_out, state)
    return state


def main() -> None:
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    state = MathState()
    trail_file, trail_path = _open_trail()

    print(f"[omega] Trail: {trail_path}")
    print(f"[omega] Running {cycles} cycle(s) with model {MODEL}")

    try:
        for _ in range(cycles):
            state = run_cycle(state, trail_file)
    finally:
        _write_trail_final(trail_file, state, cycles)
        trail_file.close()

    print(f"\n\n{'═' * 60}")
    print("FINAL COMPRESSED STATE")
    print('═' * 60)
    print(state.compressed)
    print(f"\nH survivors after {cycles} cycles: {state.H_survivors}")
    print(f"All motifs: {json.dumps(state.motifs, indent=2, ensure_ascii=False)}")
    if state.rewrite_laws:
        print(f"Rewrite laws:")
        for rl in state.rewrite_laws:
            print(f"  [{_level_name(rl.level)}] {rl.law}")
    print(f"\nTrail written: {trail_path}")


if __name__ == "__main__":
    # self-check (run with: python phase_omega_monster.py --test)
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        assert _rank_bucket(0) == 1
        assert _rank_bucket(2) == 2
        assert _rank_bucket(5) == 3
        rl = RewriteLaw("test", support_count=10, context_ranks=[1, 2, 3])
        assert _promote(rl).level == 2
        assert is_idempotent_approx(["a", "b"], ["b", "a"])
        assert not is_idempotent_approx(["a"], ["a", "b"])
        stats = extract_action_stats("(J) tension rises. (H) the mirror. (D) collapse.", 2)
        assert stats["rank_bucket"] == 2
        assert stats["j_count"] == 1
        print("All checks pass.")
        sys.exit(0)
    main()
