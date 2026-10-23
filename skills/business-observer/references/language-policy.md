# Language policy

English is the maintained source language for instructions, identifiers, comments, protocol keys, and default documentation. This does not force English conversation or English business terms on the user.

| Surface | Rule |
|---|---|
| Conversation | Use the user's current language unless they request another. Ask necessary business questions in that language. |
| Skill instructions | Maintain one canonical English SKILL.md; translations are optional reading aids, not independent workflows. |
| Graph identity | Keep stable IDs, enum values, relation kinds, source symbols, and evidence IDs unchanged when switching display language. |
| Display | Use an explicit locale, then the environment locale, then English. Store locale with personal view preferences. |
| User-authored labels | Preserve exact wording and notes. Translate only on request, keeping the original. |
| Source and API errors | Use stable English diagnostic codes/messages. Localize presentation separately. |
| Documentation | README.md is English. Link a Chinese edition and retain navigation between editions. |
| Historical evidence | Preserve conversations, screenshots, frozen source, checksums, and assertions. Add English indexes; never rewrite accepted evidence as if it were original. |

Do not maintain separate graphs or source trees for each display language. Check behavior and locale catalogs without weakening mapping or business assertions. A source-language migration changes fingerprints and requires ordinary reviewed regeneration and acceptance.
