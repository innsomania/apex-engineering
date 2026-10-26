# Skill catalog

`skills.json` is the one record of third-party skills Apex Engineering relies on.
The repository itself ships exactly one skill, `SKILL.md`; everything listed here is
installed from its source, never copied in. A test fails if a second `SKILL.md`
appears or if an entry breaks the rules below.

## Categories

| Category | For |
| --- | --- |
| `engineering-practice` | How to work: debugging, isolation, planning habits |
| `review-and-quality` | Judging code that already exists |
| `security` | Threat modelling, auditing, guarding |
| `extend-and-guard` | Growing and constraining the agent itself: skills, plugins, hooks |
| `web-and-ui` | Browser and interface work |

A category holds at most four entries. Adding a fifth means removing one or
writing down why the cap should move.

## Admission

A skill enters `skills.json` as `installed` only after all of these are written down:

1. **Need:** `why` names a decision the agent gets wrong without it.
2. **Overlap:** `overlaps_ae` says how it differs from what `guides/` and the controls already do.
3. **Source and licence:** `source`, `path`, `license`, and a `pinned_ref` once installed.
4. **Content read:** `reviewed` records the date its `SKILL.md` and any scripts were read.
5. **Trial:** installed once in a disposable environment, with `hosts` set to `verified`
   only for hosts it was actually run on.
6. **Removal:** `removal` says how to take it out.

## Status

| Status | Meaning |
| --- | --- |
| `planned` | Chosen, not yet installed or reviewed |
| `installed` | Passed admission and is installed from its pinned source |
| `provided` | Already supplied by the host or the account; we do not install a second copy |
| `removed` | Taken out; kept as a record of why |
