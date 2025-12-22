use super::*;
use boot_db::FunctionId;
use boot_db::ResolvedTerm;
use boot_db::ResolvedWord;
use pretty_assertions::assert_eq;

#[test]
fn test_run_tests_pure() {
  let mut functions = HashMap::new();
  functions.insert(
    FunctionId("inc".to_string()),
    vec![
      ResolvedTerm::Literal(boot_db::Value::Integer(1)),
      ResolvedTerm::Word(ResolvedWord::Builtin(boot_db::Builtin::Add)),
    ],
  );

  let tests = vec![(
    TestId("test.1".to_string()),
    vec![
      ResolvedTerm::Literal(boot_db::Value::Integer(10)),
      ResolvedTerm::Word(ResolvedWord::Function(FunctionId(
        "inc".to_string(),
      ))),
      ResolvedTerm::Literal(boot_db::Value::Integer(11)),
      ResolvedTerm::Word(ResolvedWord::Builtin(boot_db::Builtin::Eq)),
      ResolvedTerm::Word(ResolvedWord::Builtin(boot_db::Builtin::Assert)),
    ],
  )];

  let input = TestInput {
    tests_to_run: &tests,
    functions: &functions,
  };

  let result = run_tests(&input).unwrap();
  let expected = vec![TestRunResult {
    test_id: TestId("test.1".to_string()),
    passed: true,
    output: String::new(),
  }];

  assert_eq!(result, expected);
}
