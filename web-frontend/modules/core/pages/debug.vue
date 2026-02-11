<template>
  <div class="debug">
    <h1>Debug page</h1>

    <table class="debug__table">
      <thead>
        <tr>
          <th>Key</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="[key, value] in publicConfigFiltered" :key="key">
          <td>
            <strong>{{ formatKey(key) }}</strong>
          </td>
          <td>
            <pre>{{ formatValue(value) }}</pre>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
const { public: publicConfig } = useRuntimeConfig()

const excludeList = ['i18n']

const formatKey = (key) =>
  key
    // Split acronym-to-Word boundary: "LLMModel" -> "LLM_Model"
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1_$2')
    // Split lower/digit-to-Upper boundary: "testModel" -> "test_Model"
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    // Normalize separators
    .replace(/[-\s]+/g, '_')
    .toUpperCase()

const formatValue = (value) => {
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value, null, 2)
  }
  return String(value)
}

const publicConfigFiltered = computed(() =>
  Object.entries(publicConfig).filter(([key]) => !excludeList.includes(key))
)
</script>

<style scoped>
.debug {
  padding: 20px;
}

.debug__table {
  border-collapse: collapse;
}

th,
td {
  border: 1px solid #ccc;
  padding: 0.5rem;
  vertical-align: top;
  text-align: left;
}

thead {
  background: #f5f5f5;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
