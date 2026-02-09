// @ts-check
import withNuxt from "./web-frontend/.nuxt/eslint.config.mjs";
import globals from "./web-frontend/node_modules/globals/index.js";
import vitest from "./web-frontend/node_modules/eslint-plugin-vitest/dist/index.mjs";
import eslintConfigPrettier from "./web-frontend/node_modules/eslint-config-prettier/index.js";

// Export factory function for reusability in plugins
export const createBaserowConfig = ({ extraSourceFiles = [] } = {}) => {
  return withNuxt([
    {
      ignores: [
        "**/node_modules/**",
        "**/.nuxt/**",
        "**/coverage/**",
        "**/generated/**",
        "**/.nuxt-storybook/**",
        "**/dist/**",
        "**/.output/**",
        "**/.storybook/**",
        "**/vitest.setup.ts",
      ],
    },
    eslintConfigPrettier, // deactivate eslint rules that conflict with prettier
    {
      files: [
        "web-frontend/**/*.{js,ts,mjs,mts,jsx,tsx,vue}",
        "premium/web-frontend/**/*.{js,ts,mjs,mts,jsx,tsx,vue}",
        "enterprise/web-frontend/**/*.{js,ts,mjs,mts,jsx,tsx,vue}",
        ...extraSourceFiles,
      ],
      languageOptions: {
        globals: {
          ...globals.browser,
          ...globals.node,
        },
      },
      rules: {
        "no-console": 0,
        "vue/no-mutating-props": 0,
        "import/order": "off",
        "vue/html-self-closing": "off",
        "vue/no-unused-components": "warn",
        "vue/no-use-computed-property-like-method": "off",
        "vue/multi-word-component-names": "off",
        "vue/no-reserved-component-names": "off",
        "import/no-named-as-default-member": "off",
        "no-unused-vars": "off",
        "@typescript-eslint/no-unused-vars": "off",
        "@typescript-eslint/no-explicit-any": "off",
        "@typescript-eslint/no-dynamic-delete": "off",
        "no-empty": "off",
      },
    },
    // Plugin specific overrides
    {
      files: [
        "premium/web-frontend/**/*.{js,ts,mjs,mts,jsx,tsx,vue}",
        "enterprise/web-frontend/**/*.{js,ts,mjs,mts,jsx,tsx,vue}",
        ...extraSourceFiles, // Apply these rules to plugins too
      ],
      rules: {
        "vue/order-in-components": "off",
      },
    },
    // Test files configuration
    {
      files: [
        "**/*.{test,spec}.{js,ts,jsx,tsx}",
        "**/__tests__/**/*.{js,ts,jsx,tsx}",
      ],
      plugins: { vitest },
      languageOptions: {
        globals: {
          ...vitest.environments.env.globals,
        },
      },
      rules: {
        ...vitest.configs.recommended.rules,
      },
    },
  ]);
};

export default createBaserowConfig();
