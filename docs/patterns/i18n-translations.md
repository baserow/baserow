# Internationalisation and translations

The mechanics of getting user-facing text into Baserow in the right
language. There's one rule that prevents 90% of mistakes:

> **Only ever edit `en.json` (frontend) and English `.po` files
> (backend).** Every other locale is owned by Weblate. Manually
> editing non-English files gets your work overwritten on the next
> Weblate sync.

That rule is also in [Project conventions](../development/conventions.md#locales-only-edit-enjson).
This page expands it into the full workflow on both sides.

## The big picture

```
Developer ─── edits en.json / English .po ───▶ PR ───▶ develop
                                                            │
                                                            ▼
                                                       Weblate pulls
                                                            │
                                                            ▼
                                                       Translators add
                                                       other languages
                                                            │
                                                            ▼
                                       Weblate pushes other-locale files
                                       back into the repo before release
```

The English string is the source of truth. Weblate is the only
process that writes the other-locale files. The deployment picks up
whatever's on `master` at release time.

## Frontend — `@nuxtjs/i18n`

### Where strings live

Two layers of locale files, both flat JSON:

- **`web-frontend/locales/<lang>.json`** — top-level shared strings
  (`common.*`, `action.*`, `error.*`, etc.).
- **`web-frontend/modules/<module>/locales/<lang>.json`** — module-scoped
  strings.
- Same pattern under `premium/web-frontend/modules/baserow_premium/locales/`
  and `enterprise/web-frontend/modules/baserow_enterprise/locales/`.

Structure is a nested object keyed by translation namespace:

```json
{
  "common": { "yes": "yes", "no": "no", "wrong": "Something went wrong" },
  "action": { "close": "Close", "upload": "Upload", "submit": "Submit" }
}
```

Each module registers its locales via Nuxt's `i18n:registerModule`
hook from its `module.js`, so module-scoped keys live alongside the
shared ones at runtime.

### Using a string

In a Vue component template:

```html
<button>{{ $t('action.close') }}</button>
```

In a component method or computed:

```javascript
this.$i18n.t('common.yes')
```

On a `Registerable` (field type, view type, etc.) — the base class
proxies `$t` through:

```javascript
getName() {
  return this.$t('fieldType.text')
}
```

### Interpolation

`@nuxtjs/i18n` uses curly-brace placeholders:

```json
{ "row": { "count": "{count} rows selected" } }
```

```javascript
this.$t('row.count', { count: 5 })
```

For pluralisation, use the pipe syntax:

```json
{ "row": { "count": "no rows | 1 row | {count} rows" } }
```

```javascript
this.$t('row.count', 5)
```

### Adding a new string

1. Pick a sensible key path. Prefer existing namespaces (`common`,
   `action`, `error`, `<area>.*`) over inventing new ones — too many
   top-level namespaces makes the file unscannable.
2. Add the key to the right `en.json`:
    - Module-specific copy: that module's `locales/en.json`.
    - Truly shared: `web-frontend/locales/en.json`.
    - Premium/enterprise copy: those modules' `locales/en.json`.
3. Use the key via `$t(...)` in your code.
4. **Do not** add the key to any other-language JSON file. Weblate
   will pick it up from `en.json` and populate the other locales.

### Don't put HTML in translation strings

If the string contains markup, use Vue's component-based approach
instead — `<i18n-t>` (Vue I18n component) with named slots — or split
into pieces with separate keys. HTML in JSON strings escapes badly,
gets stripped by translators who don't expect it, and is a security
risk when the string ever reaches `v-html`.

## Backend — Django gettext

### Where strings live

`backend/src/baserow/locale/<lang>/LC_MESSAGES/django.po` (plus
`.mo` compiled files). Each app under `core/`, `contrib/database/`,
`premium/`, `enterprise/` has its own `locale/` directory.

### Using a string

```python
from django.utils.translation import gettext_lazy as _

class Meta:
    verbose_name = _("Table")

# Or in a function body:
from django.utils.translation import gettext

def message(user):
    return gettext("Welcome %(name)s") % {"name": user.first_name}
```

**Use `gettext_lazy`** for strings evaluated at import time (model
field labels, choices, class attributes) — eager `gettext` resolves
against whatever locale was active at module load, which is usually
the wrong one.

**Use `gettext`** (often imported as `_`) for strings evaluated per
request — error messages, log lines that go to the user, response
content.

### Adding a new string

1. Wrap the string in `_(...)` / `gettext_lazy(...)`.
2. Run `just make-translations` (from `backend/`) to update the English `.po` files
   with the new msgid.
3. Commit the changed English `.po` file along with your code change.
4. Weblate translates the rest before release.

`make-translations` only updates English. The other locales are
fetched from Weblate; you should never see them in a diff that
isn't a Weblate sync commit.

### Backend message formatting

Django's gettext uses C-style `%` placeholders, not curly braces:

```python
gettext("Created %(count)d rows in %(table)s") % {
    "count": n,
    "table": table.name,
}
```

For pluralisation use `ngettext`:

```python
from django.utils.translation import ngettext

ngettext(
    "%(count)d row",
    "%(count)d rows",
    n,
) % {"count": n}
```

## Weblate flow

We use [Weblate](https://hosted.weblate.org/) for community
translation. The integration is one-way for source strings and
one-way for translations:

1. **Source**: PRs merging to `develop` carry updated English files.
2. **Pull**: Weblate periodically pulls `develop`, parses the English
   source, exposes new strings to translators.
3. **Translate**: contributors add or update non-English strings via
   the Weblate UI.
4. **Push**: Weblate periodically pushes a commit with the updated
   non-English files. These commits show up in `git log` with
   Weblate as the author.

The implication for development:

- **A new string is invisible to users in any language other than
  English until Weblate processes it.** If a release ships immediately
  after you add a key, non-English speakers see the English fallback.
  Plan ahead for major copy if it matters.
- **Don't fight Weblate.** Don't manually fix bad translations in the
  repo — fix them in Weblate. Manual edits to non-English files get
  overwritten and you lose the change.
- **Don't delete a key in en.json without also clearing usages.**
  Weblate keeps stale keys around indefinitely; the cleanup pass is
  manual.

## Adding a new language

You don't. Weblate adds languages when enough translators sign up
for one. New-language requests go to product, not engineering.

If you're testing translation behaviour locally, you can add a
locale temporarily for development — but **don't commit it**. The
Weblate config is the authoritative list of supported languages.

## Testing

The frontend uses the `TestApp` fixture (see
[Frontend architecture — testing](frontend-architecture.md#testing)) with
the i18n plugin loaded. Tests can assert on translated strings
directly:

```javascript
expect(wrapper.find('button').text()).toBe('Close')
```

The fixture runs against `en.json` so assertions are stable.

For the backend, Django's `override_settings(LANGUAGE_CODE='en')` in
test fixtures keeps message strings deterministic. Tests that assert
on user-visible messages should always run in English.

## Anti-patterns

- **Editing `de.json` / `fr.json` / etc. directly.** The change will
  be overwritten on the next Weblate sync. If a translation is wrong,
  fix it in Weblate.
- **Hard-coded strings in components.** "It's only one word" is how
  100 untranslated buttons accumulate. Wrap every user-visible string
  in `$t(...)`.
- **String concatenation across translation keys.** `$t('foo') + ' ' +
  $t('bar')` produces grammatically broken output in non-English
  languages. Use one key with placeholders.
- **HTML in JSON strings.** Use component slots or split into multiple
  keys.
- **`gettext` for module-level constants.** Use `gettext_lazy`. Eager
  resolution happens once at import — at the wrong locale.
- **String keys with embedded English assumptions.**
  `common.fieldNameIsPlural` reads as developer-friendly but
  translators won't have the context. Prefer keys that describe what
  the string is *for* (`common.field.namePluralLabel`) over keys that
  imitate the English text.

## Related

- [Project conventions](../development/conventions.md#locales-only-edit-enjson)
  — the one-line rule.
- [Frontend architecture](frontend-architecture.md) — where the
  locale files plug into the Nuxt module structure.
- [Tools — backend internationalisation](../development/tools.md#backend-internationalisation),
  [Tools — frontend internationalisation](../development/tools.md#frontend-internationalisation).
