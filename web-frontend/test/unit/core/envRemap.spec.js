import { execFileSync } from 'node:child_process'

import { describe, expect, test } from 'vitest'

const CURRENT_MODEL_ENV = 'BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL'
const LEGACY_MODEL_ENV = 'UDSPY_LM_MODEL'
const NUXT_MODEL_ENV = 'NUXT_PUBLIC_BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL'
const MODEL_ENV_NAMES = [CURRENT_MODEL_ENV, LEGACY_MODEL_ENV, NUXT_MODEL_ENV]

const remappedModel = (overrides = {}) => {
  const env = { ...process.env }
  MODEL_ENV_NAMES.forEach((name) => delete env[name])
  Object.assign(env, overrides)

  return execFileSync(
    process.execPath,
    [
      '--import',
      './env-remap.mjs',
      '--eval',
      `process.stdout.write(process.env.${NUXT_MODEL_ENV} ?? '<unset>')`,
    ],
    { cwd: process.cwd(), encoding: 'utf8', env }
  )
}

describe('assistant model environment remapping', () => {
  test.each([
    [
      'uses the current variable',
      { [CURRENT_MODEL_ENV]: 'current:model' },
      'current:model',
    ],
    [
      'falls back to the deprecated variable',
      { [LEGACY_MODEL_ENV]: 'legacy:model' },
      'legacy:model',
    ],
    [
      'prefers the current variable over the deprecated variable',
      {
        [CURRENT_MODEL_ENV]: 'current:model',
        [LEGACY_MODEL_ENV]: 'legacy:model',
      },
      'current:model',
    ],
    [
      'uses the deprecated variable when the current variable is empty',
      { [CURRENT_MODEL_ENV]: '', [LEGACY_MODEL_ENV]: 'legacy:model' },
      'legacy:model',
    ],
    [
      'keeps a direct Nuxt override authoritative',
      {
        [CURRENT_MODEL_ENV]: 'current:model',
        [LEGACY_MODEL_ENV]: 'legacy:model',
        [NUXT_MODEL_ENV]: 'nuxt:model',
      },
      'nuxt:model',
    ],
    [
      'keeps an empty direct Nuxt override authoritative',
      { [CURRENT_MODEL_ENV]: 'current:model', [NUXT_MODEL_ENV]: '' },
      '',
    ],
    ['leaves the runtime variable unset without a model', {}, '<unset>'],
  ])('%s', (_name, overrides, expected) => {
    expect(remappedModel(overrides)).toBe(expected)
  })
})
