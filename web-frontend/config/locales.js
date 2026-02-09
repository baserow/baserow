/**
 * Shared locales configuration for all Baserow modules.
 * This is the single source of truth for supported languages.
 *
 * To add a new language:
 * 1. Add the locale entry here
 * 2. Create the corresponding .json translation files in each module's locales/ directory
 */
export const locales = [
  { code: 'en', name: 'English', file: 'en.json' },
  { code: 'fr', name: 'Français', file: 'fr.json' },
  { code: 'nl', name: 'Nederlands', file: 'nl.json' },
  { code: 'de', name: 'Deutsch', file: 'de.json' },
  { code: 'es', name: 'Español', file: 'es.json' },
  { code: 'it', name: 'Italiano', file: 'it.json' },
  { code: 'pl', name: 'Polski (Beta)', file: 'pl.json' },
  { code: 'ko', name: '한국어', file: 'ko.json' },
  { code: 'uk', name: 'Українська', file: 'uk.json' },
]
