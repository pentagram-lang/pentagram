use super::*;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::Span;
use boot_db::Spanned;
use boot_db::Term;
use boot_db::TestId;
use boot_db::TestResultRecord;
use boot_db::Value;
use boot_db::hash_test_result;
use pretty_assertions::assert_eq;

fn s<T>(val: T, start: usize, end: usize) -> Spanned<T> {
  Spanned::new(val, Span { start, end })
}

#[test]
fn test_engine_basic_flow() {
  let mut db = Database::default();

  let script = "
    def main fn 'Hello' say end-fn,
    test 'Hello' say end-test,
  ";

  let mut output = Vec::new();

  execute_tests(&mut db, &[("test.penta", script)], &mut output)
    .expect("Run failed");

  assert_eq!(String::from_utf8(output).unwrap(), "PASS test.penta.1\n");

  let main_hash = db.functions[0].content_hash;

  // script counting:
  // 0: \n
  // 1-4: spaces
  // 5-7: def
  // 8: space
  // 9-12: main
  // 13: space
  // 14-15: fn
  // 16: space
  // 17-23: 'Hello' (length 7)
  // 24: space
  // 25-27: say (length 3)

  let expected_functions = vec![FunctionRecord {
    id: FunctionId("main".to_string()),
    name: "main".to_string(),
    file_id: FileId("test.penta".to_string()),
    body: vec![
      s(Term::Literal(Value::String("Hello".to_string())), 17, 24),
      s(Term::Word("say".to_string()), 25, 28),
    ],
    content_hash: main_hash,
    generation: Generation::OldOnly,
    index: 0,
  }];

  assert_eq!(db.functions, expected_functions);

  let expected_results = vec![TestResultRecord {
    id: TestId("test.penta.1".to_string()),
    passed: true,
    output: "Hello\n".to_string(),
    content_hash: hash_test_result(true, "Hello\n"),
    generation: Generation::OldOnly,
  }];

  assert_eq!(db.test_results, expected_results);
}

#[test]
fn test_engine_incremental_no_change() {
  let mut db = Database::default();

  let script = "
    def inc fn 1 + end-fn,
    test 1 inc 2 eq assert end-test,
  ";

  let mut output = Vec::new();

  execute_tests(&mut db, &[("test.penta", script)], &mut output)
    .expect("Run 1 failed");

  assert_eq!(
    String::from_utf8(output.clone()).unwrap(),
    "PASS test.penta.1\n"
  );

  db.test_results[0].output = "TAINTED".to_string();
  db.test_results[0].content_hash = hash_test_result(true, "TAINTED");
  db.test_results[0].generation = Generation::OldOnly;

  output.clear();

  execute_tests(&mut db, &[("test.penta", script)], &mut output)
    .expect("Run 2 failed");

  assert_eq!(String::from_utf8(output).unwrap(), "PASS test.penta.1\n");

  let expected_results = vec![TestResultRecord {
    id: TestId("test.penta.1".to_string()),
    passed: true,
    output: "TAINTED".to_string(),
    content_hash: hash_test_result(true, "TAINTED"),
    generation: Generation::OldOnly,
  }];

  assert_eq!(db.test_results, expected_results);
}

#[test]
fn test_engine_incremental_change_dependency() {
  let mut db = Database::default();

  let v1_script = "
    def val fn 1 end-fn,
    test val 1 eq assert end-test,
  ";

  let mut output = Vec::new();

  execute_tests(&mut db, &[("test.penta", v1_script)], &mut output)
    .expect("Run 1 failed");

  assert_eq!(
    String::from_utf8(output.clone()).unwrap(),
    "PASS test.penta.1\n"
  );

  db.test_results[0].output = "TAINTED".to_string();
  db.test_results[0].content_hash = hash_test_result(true, "TAINTED");
  db.test_results[0].generation = Generation::OldOnly;

  let v2_script = "
    def val fn 2 end-fn,
    test val 1 eq assert end-test,
  ";

  output.clear();

  execute_tests(&mut db, &[("test.penta", v2_script)], &mut output)
    .expect("Run 2 failed");

  assert_eq!(
    String::from_utf8(output).unwrap(),
    "FAIL test.penta.1\nError in test.penta at 44..50: Assertion failed\n"
  );

  let expected_results = vec![TestResultRecord {
    id: TestId("test.penta.1".to_string()),
    passed: false,
    output: "Error in test.penta at 44..50: Assertion failed\n"
      .to_string(),
    content_hash: hash_test_result(
      false,
      "Error in test.penta at 44..50: Assertion failed\n",
    ),
    generation: Generation::OldOnly,
  }];

  assert_eq!(db.test_results, expected_results);
}

#[test]
fn test_engine_incremental_transitive_change() {
  let mut db = Database::default();

  let v1_script = "
    def a fn 1 end-fn,
    def b fn a end-fn,
    test b 1 eq assert end-test,
  ";

  let mut output = Vec::new();

  execute_tests(&mut db, &[("test.penta", v1_script)], &mut output)
    .expect("Run 1 failed");

  assert_eq!(
    String::from_utf8(output.clone()).unwrap(),
    "PASS test.penta.2\n"
  );

  db.test_results[0].output = "TAINTED".to_string();
  db.test_results[0].content_hash = hash_test_result(true, "TAINTED");
  db.test_results[0].generation = Generation::OldOnly;

  let v2_script = "
    def a fn 2 end-fn,
    def b fn a end-fn,
    test b 1 eq assert end-test,
  ";

  output.clear();

  execute_tests(&mut db, &[("test.penta", v2_script)], &mut output)
    .expect("Run 2 failed");

  assert_eq!(
    String::from_utf8(output).unwrap(),
    "FAIL test.penta.2\nError in test.penta at 63..69: Assertion failed\n"
  );

  let expected_results = vec![TestResultRecord {
    id: TestId("test.penta.2".to_string()),
    passed: false,
    output: "Error in test.penta at 63..69: Assertion failed\n"
      .to_string(),
    content_hash: hash_test_result(
      false,
      "Error in test.penta at 63..69: Assertion failed\n",
    ),
    generation: Generation::OldOnly,
  }];

  assert_eq!(db.test_results, expected_results);
}

#[test]
fn test_engine_resolve_error() {
  let mut db = Database::default();

  let script = "
    def main fn unknown end-fn,
  ";

  let mut output = Vec::new();

  let err = execute_file(&mut db, "test.penta", script, &mut output)
    .expect_err("Should have failed");

  assert_eq!(err.error_message, "Undefined reference: unknown");
  assert_eq!(err.path, "test.penta");
  assert_eq!(String::from_utf8(output).unwrap(), "");
  assert_eq!(db, Database::default());
}

#[test]
fn test_engine_rollback() {
  let mut db = Database::default();

  let first_script = "def a fn 1 end-fn,";

  let mut output = Vec::new();

  execute_file(&mut db, "file1.penta", first_script, &mut output)
    .expect("First run failed");

  let hash_a = db.functions[0].content_hash;

  let failing_script = "def b fn unknown end-fn,";

  output.clear();

  let err =
    execute_file(&mut db, "file2.penta", failing_script, &mut output)
      .expect_err("Second run should have failed");

  assert_eq!(err.error_message, "Undefined reference: unknown");
  assert_eq!(err.path, "file2.penta");

  let expected_functions = vec![FunctionRecord {
    id: FunctionId("a".to_string()),
    name: "a".to_string(),
    file_id: FileId("file1.penta".to_string()),
    body: vec![s(Term::Literal(Value::Integer(1)), 9, 10)],
    content_hash: hash_a,
    generation: Generation::OldOnly,
    index: 0,
  }];

  assert_eq!(db.functions, expected_functions);
}

#[test]
fn test_engine_repl_error_in_previous_input() {
  let mut db = Database::default();
  let mut output = Vec::new();

  execute_repl(&mut db, "def boom fn 1 2 eq assert end-fn", &mut output)
    .expect("REPL 1 failed");

  output.clear();

  let err = execute_repl(&mut db, "boom", &mut output)
    .expect_err("REPL 2 should have failed");

  assert_eq!(err.path, "repl:1");
  assert_eq!(err.full_source, "def boom fn 1 2 eq assert end-fn");
  assert_eq!(err.error_message, "Assertion failed");
}
