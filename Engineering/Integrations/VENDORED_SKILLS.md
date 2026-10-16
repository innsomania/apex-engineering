# Vendored skills playbook

Everything reaches the hosts through the global Apex install, so third-party skills are not
installed per project. They are copied under `Claude/skills/`, each keeping its upstream licence,
and `install.py` links every directory there that holds a `SKILL.md` into `~/.claude/skills/`
beside the Apex skill. `install.py uninstall` removes the links again and leaves the copies.

## What is vendored

| Skill | Upstream | Licence | Why it is here |
| --- | --- | --- | --- |
| `kiro-*` (17) | [gotalab/cc-sdd](https://github.com/gotalab/cc-sdd) 3.1.0 | MIT, as `LICENSE.cc-sdd` | Step lists and file boundaries; see [Spec planning](SPEC_PLANNING.md) |
| `claude-api` | [anthropics/skills](https://github.com/anthropics/skills) | Apache-2.0 | Model ids, pricing, parameters, caching — facts not to answer from memory |
| `mcp-builder` | same | Apache-2.0 | Building MCP servers |
| `webapp-testing` | same | Apache-2.0 | Driving and testing a running web application |
| `frontend-design` | same | Apache-2.0 | Front-end work |
| `web-artifacts-builder` | same | Apache-2.0 | Self-contained web pages |
| `skill-creator` | same | Apache-2.0 | Writing further skills |

Each Anthropic skill carries its own `LICENSE.txt` as copied. `Test/test_install.py` fails if a
vendored skill has no licence anyone can point to, and asserts every one of them is linked by an
install and removed by an uninstall.

## What is deliberately not vendored

- **`docx`, `pdf`, `pptx`, `xlsx`.** Their licence reads "© 2025 Anthropic, PBC. All rights
  reserved"; upstream calls them source-available, not open source. They are also already reachable
  in this host, so copying them would add risk for nothing.
- **cc-sdd's project files.** Its installer also writes a project-root `CLAUDE.md` declaring a
  `/kiro-*` workflow, plus `.kiro/settings/` templates. The `CLAUDE.md` would compete with the
  global instructions that route software work to Apex.
- **The non-engineering Anthropic skills** (`algorithmic-art`, `brand-guidelines`, `internal-comms`,
  `slack-gif-creator`, `theme-factory`, `academy-guide`, `discernment-nudge`, `canvas-design`,
  `doc-coauthoring`). Apache-2.0 and available if wanted; simply not asked for.

## Keeping them current

A vendored copy does not update itself. To refresh:

```bash
# cc-sdd
npx cc-sdd@<version> --claude-code-skills --lang en --yes   # into an empty directory
# Anthropic skills
git clone --depth 1 https://github.com/anthropics/skills.git
```

Copy the new directories over `Claude/skills/`, keep each licence file, re-read the limits in the
playbook that selected the skill, and run the suite. Upstream's own disclaimer is that these skills
are demonstrations: test before relying on one.

## What this does not do

Linking a skill makes it available; it does not make it authoritative. The user's instruction still
decides what gets built, Apex's `scope.json` still decides which files may change, and
`review.json` still checks the result against the user's own words. A skill that suggests an
approach the user did not ask for is a suggestion, not permission.
