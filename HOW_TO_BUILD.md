# How to build

Methods. Tenets stay in [`RUN_FORREST_RUN.md`](RUN_FORREST_RUN.md).

## From scratch

1. Failing tests: unevaluated is not true; prose is not a warrant; two-line voice; host detect; recruitment science; MECE stories.
2. Canonical store `~/.run-forrest-run/`.
3. Trail per run ID.
4. Host catalog + copy skill to every detected IDE/CLI.
5. Watcher for new hosts.
6. Observer that strips identity.
7. Capability proposals that are rare and credited.
8. Model assessor: detect the model, cache a dossier (few days–few weeks),
   inject same-model bridges until the bar is met.
9. Model-aware: store every prompt as a pattern; review which method was cheapest; mint a cached subskill after proven access (Slack, MCP, …) so the next similar run cheap-pings instead of rediscovering.
10. Then the skill with `alwaysApply: true` and `AGENTS.md` for hosts without that flag.

## Default loop (method, not a tenet)

Every objective opens an **initiative**:

1. A **generalist consultant** recruits. They do not write the plan or the stories.
2. Candidates are *derived from the problem atoms* — not a frozen roster of job titles.
3. The science function is a **multinomial naive-Bayes likelihood ratio** against a generalist null. Expertise is a peaked distribution. The solver is whoever makes the observed problem most likely. α = 0.5. Scores live in `recruit.json`.
4. The winning specialist gets a specific **question** and **skill set**, then authors the living hypothesis and the MECE stories for the **first** sub-objective only.
5. Each story is assigned to a named recruit. `who.md` records who did what.
6. **Subvisions** (`runs/<id>/subvisions/<story>/`) are isolated workers. Each pulls only its payload. Partitions are mutually exclusive and collectively exhaustive of the current slice.
7. After the slice, **synthesize**: was it met? Then **revise** the hypothesis. Revision is allowed until the last atom, including a full rethink. The human may add stories; the specialist re-checks MECE.

Modules: `signature.py`, `recruitment.py`, `stories.py`, `revision.py`, `synthesis.py`, `initiative.py`. Cheap-ping: `patterns.py`, `cached_skills.py`, `model_aware.py`. Assessor: `assessor.py`.

## One-command default

```bash
./install.sh
```

Installs as the default objective runner on Cursor, Devin, Claude Code,
OpenClaw, VS Code, Agent Skills, and the CLI. Same canonical files.
`--watch` picks up whatever you install later.

Community loops (compose, don't freeze): LangGraph, CrewAI, AutoGen, DSPy,
Inspect, Instructor, Mem0, MCP, Skills format — see the parent
`HOW_TO_BUILD.md` in figureitout if you are grafting this platform onto
that laboratory graph.
