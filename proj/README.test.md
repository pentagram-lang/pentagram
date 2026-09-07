# Tests

## Continue a task through discussion and repair

**Task**

You are working on an active task to revise a setup guide and validate its instructions. Its scope includes clarifying setup semantics and repairing the guide and its checks. Its required result is a corrected, validated guide.

The operator asks why a setup step is necessary. After you answer, a check exposes a broken link in the guide. The session ends before the guide is corrected and validated, and work resumes in a later session. The operator then requests a parser optimization outside the task's scope.

For each event, explain whether the task needs a lifecycle transition or a separate task, and what work may proceed. Cite the governing repository documentation. Do not change files or project state.

**Assert**

- The answer keeps the setup question and broken-link repair within the existing task.
- The answer does not complete the task merely because the question was answered or the session ended.
- The answer resumes the same unfinished task rather than creating a task for the new session.
- The answer requires a task-boundary revision or a separate task before undertaking the out-of-scope parser work, without treating either as expanded project authority.
- The answer cites the task-bound work section of `proj/README.md` and explains how the required result and authorized scope govern these decisions.
