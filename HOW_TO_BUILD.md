# How to build

Methods. Tenets stay in [`RUN_FORREST_RUN.md`](RUN_FORREST_RUN.md).

## From scratch

1. Failing tests: unevaluated is not true; prose is not a warrant; two-line voice; host detect.
2. Canonical store `~/.run-forrest-run/`.
3. Trail per run ID.
4. Host catalog + copy skill to every detected IDE/CLI.
5. Watcher for new hosts.
6. Observer that strips identity.
7. Capability proposals that are rare and credited.
8. Model-aware: store every prompt as a pattern; review which method was cheapest; mint a cached subskill after proven access (Slack, MCP, …) so the next similar run cheap-pings instead of rediscovering.
9. Then the skill with `alwaysApply: true` and `AGENTS.md` for hosts without that flag.

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
