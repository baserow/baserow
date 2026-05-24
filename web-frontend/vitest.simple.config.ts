import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['test/unit/utils/truncaText.spec.js'],
    environment: 'node',
  }
})
