import prettierPlugin from 'eslint-plugin-prettier';
import prettierConfig from 'eslint-config-prettier';
import tseslint from 'typescript-eslint';

// Next.js plugin is not fully typed for Flat Config yet, so we require it
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const nextPlugin = require('@next/eslint-plugin-next');

export default tseslint.config(
  ...tseslint.configs.recommended,
  {
    plugins: {
      '@next/next': nextPlugin,
      prettier: prettierPlugin,
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs['core-web-vitals'].rules,
      ...prettierPlugin.configs.recommended.rules,
      ...prettierConfig.rules,
      'prettier/prettier': 'error',
      // Downgrade any TypeScript any rules that might have been warnings to errors
      // per user request for "strict linter"
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': 'error',
    },
  },
  {
    ignores: [
      'node_modules/**',
      '.next/**',
      'out/**',
      'build/**',
      'next-env.d.ts',
    ],
  }
);
