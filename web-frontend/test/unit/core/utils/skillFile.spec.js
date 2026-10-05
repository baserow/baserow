import { describe, expect, test } from 'vitest'
import {
  parseFrontmatter,
  parseSkillFile,
} from '@baserow/modules/core/utils/skillFile'

describe('skillFile', () => {
  test('reads an Agent Skills SKILL.md', () => {
    const text = `---
name: pdf-processing
description: "Extract text and tables from PDF files. Use when the user mentions PDFs."
license: Apache-2.0
allowed-tools: Bash(python:*)
metadata:
  author: someone
---
# PDF processing

## Steps

1. Run the script.
`
    expect(parseSkillFile(text, 'SKILL.md')).toEqual({
      name: 'Pdf processing',
      description:
        'Extract text and tables from PDF files. Use when the user mentions PDFs.',
      content: '# PDF processing\n\n## Steps\n\n1. Run the script.',
    })
  })

  test('reads a Cursor rule with a folded description', () => {
    const text = `---
description: >
  Use when writing
  Vue components.
globs: ["*.vue"]
alwaysApply: false
---
Prefer the composition API.
`
    expect(parseSkillFile(text, 'vue.mdc')).toEqual({
      name: 'Vue',
      description: 'Use when writing Vue components.',
      content: 'Prefer the composition API.',
    })
  })

  test('falls back to the heading and first paragraph of plain markdown', () => {
    const text = `# Formula conventions

Use when writing Baserow formulas.

- Wrap field names in field('...').
`
    expect(parseSkillFile(text, 'notes.md')).toEqual({
      name: 'Formula conventions',
      description: 'Use when writing Baserow formulas.',
      content:
        "Use when writing Baserow formulas.\n\n- Wrap field names in field('...').",
    })
  })

  test('uses the file name when nothing else names the skill', () => {
    expect(parseSkillFile('Just do it.', 'data-entry.instructions.md')).toEqual(
      {
        name: 'Data entry',
        description: 'Just do it.',
        content: 'Just do it.',
      }
    )
  })

  test('parseFrontmatter handles literal blocks and quoted values', () => {
    expect(
      parseFrontmatter(
        `name: 'a'\ndescription: |\n  line one\n  line two\nx: [1]`
      )
    ).toEqual({ name: 'a', description: 'line one\nline two' })
  })
})
