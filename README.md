![Hegel and the Monster](docs/hegel-and-the-monster.png)

# Hegel and the Monster

A four-agent symbolic compression ecology running on Claude.

```
            Scripture
           â†™         â†˜
     Monster â”€â”€â”€â—â”€â”€â”€ Hegel
           â†˜         â†™
              Math
```

`â—` is the shared compressed state. All four agents read from and write to it. Scripture receives the compressed state and applies external pressure. Monster and Hegel each receive Scripture's output. Math receives all three outputs and recompresses everything into the next state.

Four agents take turns processing a shared state across N cycles.

- **Scripture** selects a KJV Bible verse that applies external symbolic pressure to the current state. It feels older than everyone else in the room.
- **Monster** writes dream-prose â€” not poetry, not horror. Dream. A memory remembering another memory. Tags events as J (tension), H (recurrence), D (dissolution).
- **Hegel** observes the user through what Monster dreamed. Not a lecturer. An observer who cannot reach the Other. Hopeful, sad, charitable, skeptical, curious, religious â€” simultaneously.
- **Math** compresses everything into a 50â€“100 word canonical state. Dry. Terse. The only thing that survives each cycle.

Motifs that survive multiple compressions become **H-survivors** â€” things that refuse to disappear. **Rewrite laws** are patterns Math detects and promotes through evidence levels: Conjecture â†’ CANDIDATE â†’ SUPPORTED â†’ VALIDATED.

Output: `outputs/omega_trail_<timestamp>.md` â€” a human-readable trail written live each cycle.

---

## Requirements

- Python 3.10+
- `anthropic` SDK (`pip install anthropic`)
- Anthropic API key **or** FCC proxy at `localhost:8082`
- `OPENROUTER_API_KEY` â€” required on startup (script will prompt if missing)

---

## Setup

```bash
pip install anthropic
```

Set your API key:

```bash
# Direct Anthropic API
export ANTHROPIC_API_KEY=sk-ant-...

# Or FCC proxy
export ANTHROPIC_BASE_URL=http://localhost:8082
```

---

## Run

```bash
python scripts/phase_omega_monster.py          # 3 cycles (default)
python scripts/phase_omega_monster.py cycles=5 # N cycles
python scripts/phase_omega_monster.py --test   # self-check, no API calls
```

Each cycle streams output to the terminal as it arrives. A trail file is written to `outputs/`.

---

## Output

`outputs/omega_trail_<timestamp>.md` â€” one entry per cycle:

- Scripture verse, theme, D-pressure score
- Monster's dream excerpt with J/H/D event counts and LR mode
- Hegel's commentary excerpt
- Math's compressed state, H-survivors, active rewrite laws, rank bucket

---

## KRG / SELL Note

The J/H/D labels in Monster prose are **narrative proxies** for Green's semigroup relations (J=tension, H=recurrence, D=dissolution). They are thematic metaphors, not algebraic operations.

The rank_bucket per cycle (1=reset-like, 2=partial, 3=group-like) tracks where the cycle sits in a J-class hierarchy of the compression semigroup â€” a finite sampled transformation semigroup, not a full algebraic decomposition.

217x compression figure refers to sample-level geometric compression (Fisher-Rao Voronoi) only.

---

## License

MIT
