import { execFileSync } from 'node:child_process'

import { describe, expect, test } from 'vitest'

const ASSISTANT_MODEL_ENV = 'BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL'
const DSPY_MODEL_ENV = 'UDSPY_LM_MODEL'
const NUXT_MODEL_ENV = 'NUXT_PUBLIC_BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL'
const MODEL_ENV_NAMES = [ASSISTANT_MODEL_ENV, DSPY_MODEL_ENV, NUXT_MODEL_ENV]

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

describe('deprecated assistant model environment remapping', () => {
  test.each([
    [
      'uses the assistant model variable',
      { [ASSISTANT_MODEL_ENV]: 'assistant:model' },
      'assistant:model',
    ],
    [
      'falls back to the DSPy model variable',
      { [DSPY_MODEL_ENV]: 'dspy:model' },
      'dspy:model',
    ],
    [
      'prefers the assistant model variable over the DSPy model variable',
      {
        [ASSISTANT_MODEL_ENV]: 'assistant:model',
        [DSPY_MODEL_ENV]: 'dspy:model',
      },
      'assistant:model',
    ],
    [
      'uses the DSPy model variable when the assistant model variable is empty',
      { [ASSISTANT_MODEL_ENV]: '', [DSPY_MODEL_ENV]: 'dspy:model' },
      'dspy:model',
    ],
    [
      'keeps a direct Nuxt override authoritative',
      {
        [ASSISTANT_MODEL_ENV]: 'assistant:model',
        [DSPY_MODEL_ENV]: 'dspy:model',
        [NUXT_MODEL_ENV]: 'nuxt:model',
      },
      'nuxt:model',
    ],
    [
      'keeps an empty direct Nuxt override authoritative',
      { [ASSISTANT_MODEL_ENV]: 'assistant:model', [NUXT_MODEL_ENV]: '' },
      '',
    ],
    ['leaves the runtime variable unset without a model', {}, '<unset>'],
  ])('%s', (_name, overrides, expected) => {
    expect(remappedModel(overrides)).toBe(expected)
  })
})
