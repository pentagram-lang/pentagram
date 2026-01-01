use super::*;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::ResolvedTerm;
use boot_db::ResolvedWord;
use boot_db::Span;
use boot_db::Spanned;
use pretty_assertions::assert_eq;

fn s<T>(val: T) -> Spanned<T> {
  Spanned::new(val, Span { start: 0, end: 0 })
}

#[test]
fn test_run_tests_pure() {
  let file_id = FileId("test.penta".to_string());
  let mut functions = HashMap::new();
  functions.insert(
    FunctionId("inc".to_string()),
    (
      file_id.clone(),
      vec![
        s(ResolvedTerm::Literal(boot_db::Value::Integer(1))),
        s(ResolvedTerm::Word(ResolvedWord::Builtin(
          boot_db::Builtin::Add,
        ))),
      ],
    ),
  );

  let tests = vec![(
    TestId("test.1".to_string()),
    file_id.clone(),
    vec![
      s(ResolvedTerm::Literal(boot_db::Value::Integer(10))),
      s(ResolvedTerm::Word(ResolvedWord::Function(FunctionId(
        "inc".to_string(),
      )))),
      s(ResolvedTerm::Literal(boot_db::Value::Integer(11))),
      s(ResolvedTerm::Word(ResolvedWord::Builtin(
        boot_db::Builtin::Eq,
      ))),
      s(ResolvedTerm::Word(ResolvedWord::Builtin(
        boot_db::Builtin::Assert,
      ))),
    ],
  )];

  let input = TestInput {
    tests_to_run: &tests,
    functions: &functions,
  };

  let result = run_tests(&input);
  let expected = vec![TestRunResult {
    test_id: TestId("test.1".to_string()),
    passed: true,
    output: String::new(),
  }];

  assert_eq!(result, expected);
}
