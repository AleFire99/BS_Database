export default {
  extends: ['@commitlint/config-conventional'],
  // merge commits are skipped by commitlint's default ignores
  ignores: [
    // cb864b7 (#83) is on the shared epic #10 history and cannot be reworded without a
    // force-push; its subject starts with the acronym "SQLite". Owner-approved exception.
    (message) =>
      message.startsWith(
        'feat(state): SQLite ingestion state store and per-page state machine (#83)',
      ),
  ],
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
