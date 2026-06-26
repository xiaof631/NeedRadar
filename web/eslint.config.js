import vue from 'eslint-plugin-vue';
import js from '@eslint/js';
import tsParser from '@typescript-eslint/parser';

export default [
  {
    ignores: ['dist/**', 'node_modules/**']
  },
  js.configs.recommended,
  ...vue.configs['flat/essential'],
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { sourceType: 'module' }
    },
    rules: {
      'no-undef': 'off',
      'no-unused-vars': 'off'
    }
  },
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tsParser,
        extraFileExtensions: ['.vue'],
        sourceType: 'module'
      }
    },
    rules: {
      'no-undef': 'off',
      'no-unused-vars': 'off',
      'vue/multi-word-component-names': 'off'
    }
  }
];
