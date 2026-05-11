import { describe, test, expect } from 'vitest'
import fs from 'fs'
import path from 'path'

const FIXTURES_DIR = path.join(import.meta.dirname, 'fixtures/templates')

const fixtureFiles = fs.existsSync(FIXTURES_DIR)
  ? fs
      .readdirSync(FIXTURES_DIR)
      .filter((f) => f.endsWith('.json'))
      .sort()
  : []

describe.skipIf(fixtureFiles.length === 0)(
  'Builder template regression',
  () => {
    for (const file of fixtureFiles) {
      const templateSlug = file.replace('.json', '')
      const pages = JSON.parse(
        fs.readFileSync(path.join(FIXTURES_DIR, file), 'utf-8')
      )
      test(`template: ${templateSlug}`, async () => {
        await expect(JSON.stringify(pages, null, 2)).toMatchFileSnapshot(
          path.join(
            import.meta.dirname,
            `__snapshots__/templates/${templateSlug}.snap`
          )
        )
      })
    }
  }
)
