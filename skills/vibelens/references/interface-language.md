# Interface language

VibeLens starts in English. During discovery and subsequent conversation, the coding
assistant records the user's language:

```bash
python SKILL/scripts/bo_design.py language --root PROJECT --locale zh-CN --source "Current Chinese conversation"
```

Use `en` for English and unsupported conversation languages. Run this before giving
the user the graph URL; update it when the user changes language. This command works
before a business graph exists. It writes only `bo_stategraph/config/interface.json`.

The viewer resolves language in this order: explicit `?lang=`, saved personal choice,
conversation language, English. A manual switch persists in the project's personal
view settings. A browser's system language alone does not select Chinese.

Language affects interface labels and tooltips. It does not rename graph IDs, fields,
source symbols, business labels, or notes. Existing personal layouts survive a switch.
`/api/design` includes `locale` even when no discussion focus is available. When the
conversation language changes, the live viewer reloads after saving its layout unless
the user has chosen a language explicitly.

An expired, absent or unavailable discussion focus clears its highlights silently.
Valid confirmed focus highlights the graph directly, without a discussion bar.
Click empty canvas or press Escape to dismiss it. Dismissal survives reloads; a newly
confirmed scope can focus again. User answers and revisions stay in the coding conversation.
