export default {
  extends: ['@commitlint/config-conventional'],
  // merge commits are skipped by commitlint's default ignores
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'refactor', 'test', 'ci', 'chore', 'build', 'perf', 'style', 'revert', 'data'],
    ],
    'body-max-line-length': [0],
    'footer-max-line-length': [0],
  },
};
