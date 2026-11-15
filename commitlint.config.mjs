export default {
  extends: ['@commitlint/config-conventional'],
  // merge commits are skipped by commitlint's default ignores
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'refactor', 'test', 'ci', 'chore', 'build', 'perf', 'style', 'revert', 'data'],
    ],
    // Allow a capitalised first word so subjects may start with an acronym or a proper
    // name (SQLite, HTML, JSON). Title Case, PascalCase and ALL CAPS subjects stay rejected.
    'subject-case': [2, 'never', ['start-case', 'pascal-case', 'upper-case']],
    'body-max-line-length': [0],
    'footer-max-line-length': [0],
  },
};
