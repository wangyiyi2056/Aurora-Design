# Aurora Design Skills

This directory contains file-based design skills. Each skill is a directory with
`SKILL.md` plus optional `assets/`, `references/`, and `example.html` files.

The initial template skills were vendored from the local Open Design
repository's `design-templates/` directory so Aurora can use the same
Claude/Open Design `SKILL.md` prompt-template format. Keep any upstream
per-skill license or attribution files intact when adding more skills.

Migration status:

- Batch 1 and 2 template skills are available by default.
- Batch 3 skills that depend on external services or complex runtimes are kept
  in this catalog with `.aurora-design-skill.json` metadata:
  `hidden: true`, `status: adapter-pending`. They are preserved for future
  Python/tool adapters but are not shown in the Composer picker by default.
