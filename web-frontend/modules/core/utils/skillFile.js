/**
 * Reads a skill written for another tool into our name, description and
 * markdown content. Supported shapes:
 *
 * - Anthropic Agent Skills `SKILL.md`: YAML frontmatter with `name` and
 *   `description`, the instructions as the markdown body.
 * - Cursor `.mdc` rules and GitHub Copilot `*.instructions.md`: frontmatter
 *   with a `description` (and keys we ignore such as `globs` or `applyTo`).
 * - Plain markdown: the first heading becomes the name and the first
 *   paragraph the description.
 */

const FRONTMATTER = /^\uFEFF?---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*\r?\n?/
const SKILL_NAME_MAX_LENGTH = 160
const SKILL_DESCRIPTION_MAX_LENGTH = 500

/**
 * A deliberately small YAML reader: top-level `key: value` pairs, quoted
 * strings, and `|` / `>` block scalars. Nested structures are skipped.
 */
export function parseFrontmatter(text) {
  const result = {}
  const lines = text.split(/\r?\n/)
  let index = 0
  while (index < lines.length) {
    const line = lines[index]
    const match = line.match(/^([A-Za-z0-9_-]+):[ \t]*(.*)$/)
    if (!match) {
      index++
      continue
    }
    const key = match[1]
    let value = match[2].trim()
    if (value === '|' || value === '>' || value === '|-' || value === '>-') {
      const folded = value.startsWith('>')
      const block = []
      index++
      while (index < lines.length && /^(\s+\S|\s*$)/.test(lines[index])) {
        if (lines[index].trim() === '' && index + 1 < lines.length) {
          const next = lines[index + 1]
          if (!/^\s+\S/.test(next)) {
            break
          }
        }
        block.push(lines[index].replace(/^\s{1,}/, ''))
        index++
      }
      value = folded
        ? block.join(' ').replace(/\s+/g, ' ').trim()
        : block.join('\n').trim()
      result[key] = value
      continue
    }
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    if (value !== '' && !value.startsWith('[') && !value.startsWith('{')) {
      result[key] = value
    }
    index++
  }
  return result
}

const humanizeName = (value) =>
  value
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^./, (c) => c.toUpperCase())

const fileStem = (filename) =>
  (filename || '')
    .split('/')
    .pop()
    .replace(/\.(instructions|skill)?\.(md|mdc|markdown|txt)$/i, '')
    .replace(/\.(md|mdc|markdown|txt)$/i, '')

export function parseSkillFile(text, filename = '') {
  const match = text.match(FRONTMATTER)
  const meta = match ? parseFrontmatter(match[1]) : {}
  let body = (match ? text.slice(match[0].length) : text).replace(/^\uFEFF/, '')
  body = body.trim()

  let name = meta.name || meta.title || ''
  let description = meta.description || ''

  if (!name) {
    const heading = body.match(/^#\s+(.+?)\s*#*\s*$/m)
    if (heading) {
      name = heading[1].trim()
      // The heading only named the skill; keep the body to the instructions.
      body = body.replace(heading[0], '').trim()
    }
  }
  if (!name) {
    const stem = fileStem(filename)
    name = stem.toUpperCase() === 'SKILL' ? '' : stem
  }
  if (!description) {
    const paragraph = body
      .split(/\r?\n\s*\r?\n/)
      .map((part) => part.trim())
      .find((part) => part !== '' && !/^[#>\-*`|]/.test(part))
    description = paragraph ? paragraph.replace(/\s+/g, ' ') : ''
  }

  return {
    name: humanizeName(name).slice(0, SKILL_NAME_MAX_LENGTH),
    description: description.slice(0, SKILL_DESCRIPTION_MAX_LENGTH),
    content: body,
  }
}
