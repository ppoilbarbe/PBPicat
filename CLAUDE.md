# Mode

`full-en` — code in English, everything else in English.

# Environment

Always run tests and Python commands using the `pbpicat` conda environment:
`conda run -n pbpicat <command>`

If `.pre-commit-config.yaml` exists and `.git/hooks/pre-commit` does not, run:
`conda run -n pbpicat pre-commit install`

# Documentation

Keep `SPEC.md` up to date with program specifications in a compact format targeting Claude, minimizing token count. Update `SPEC.md` on every significant change to functionality or structure.

# I18N

Each time a user viewable string is added, removed or modified, update the translations.
