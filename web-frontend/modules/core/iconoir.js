import { readFileSync, readdirSync, existsSync } from 'node:fs'
import pathe from 'pathe'

// Icons that are used, but that the code doesn't mention with the `iconoir-`
// prefix, because `HelpIcon` adds the prefix to its `icon` prop.
const ICONOIR_ICONS_WITHOUT_PREFIX_IN_CODE = ['chat-bubble-question']

/**
 * Changes the stroke-width of the iconoir svg files because this way, we don't
 * have to fork the repository and change it there.
 */
export function patchIconoirStrokeWidth(css) {
  return css.replace(/stroke-width="1\.5"/g, 'stroke-width="2.0"')
}

/**
 * The directories of the Baserow modules, like core, premium, enterprise and the
 * ones added with `ADDITIONAL_MODULES`, which are registered as a path to their
 * `module.js`.
 */
export function getLocalModuleDirectories(options) {
  return options.modules
    .map((module) => (Array.isArray(module) ? module[0] : module))
    .filter((module) => typeof module === 'string')
    .map((module) => pathe.resolve(options.rootDir, module))
    .filter((modulePath) => existsSync(modulePath))
    .map((modulePath) => pathe.dirname(modulePath))
}

export function findUsedIconoirIcons(directories, ignoredDirectory) {
  const icons = new Set(ICONOIR_ICONS_WITHOUT_PREFIX_IN_CODE)
  const visit = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const entryPath = pathe.join(directory, entry.name)
      if (entry.isDirectory()) {
        if (
          entry.name !== 'node_modules' &&
          !entry.name.startsWith('.') &&
          entryPath !== ignoredDirectory
        ) {
          visit(entryPath)
        }
      } else if (/\.(vue|jsx?|tsx?|scss)$/.test(entry.name)) {
        const content = readFileSync(entryPath, 'utf-8')
        for (const match of content.matchAll(
          /iconoir-([a-z0-9]+(?:-[a-z0-9]+)*)/g
        )) {
          icons.add(match[1])
        }
      }
    }
  }
  directories.forEach(visit)
  return icons
}

/**
 * Every icon is an inline svg, which makes the full set about 1.4MB of CSS that
 * every page has to load, so only the rules of the used icons are kept. The
 * name can contain a space, like the broken `privacy policy` icon of iconoir,
 * which no class can match.
 */
export function removeUnusedIconoirIcons(css, usedIcons) {
  return css.replace(
    /\.iconoir-([a-z0-9 -]+)::before\{[^}]*\}/g,
    (rule, name) => (usedIcons.has(name) ? rule : '')
  )
}
