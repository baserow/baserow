import { describe, test, expect } from 'vitest'
import fs from 'fs'
import path from 'path'

const FIXTURES_DIR = path.join(import.meta.dirname, 'fixtures/templates')

if (!fs.existsSync(FIXTURES_DIR)) {
  throw new Error(
    `No fixture files found at ${FIXTURES_DIR}. Run 'just b manage export_builder_template_trees' first.`
  )
}

const fixtureFiles = fs
  .readdirSync(FIXTURES_DIR)
  .filter((f) => f.endsWith('.json'))

if (fixtureFiles.length === 0) {
  throw new Error(
    `No fixture files found in ${FIXTURES_DIR}. Run 'just b manage export_builder_template_trees' first.`
  )
}

describe('Builder template regression', () => {
  for (const file of fixtureFiles) {
    const templateSlug = file.replace('.json', '')
    const pages = JSON.parse(
      fs.readFileSync(path.join(FIXTURES_DIR, file), 'utf-8')
    )
    test(`template: ${templateSlug}`, async () => {
      await expect(JSON.stringify(pages)).toMatchFileSnapshot(
        path.join(
          import.meta.dirname,
          `__snapshots__/templates/${templateSlug}.snap`
        )
      )
    })
  }
})
