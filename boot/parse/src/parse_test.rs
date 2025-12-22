use super::*;
use boot_db::FunctionId;
use boot_db::StatementId;
use boot_db::StatementRecord;
use boot_db::TestId;
use boot_db::hash_terms;
use pretty_assertions::assert_eq;

#[test]
fn test_integer() {
  let result = parse_source("test", "123,").expect("Parse failed");
  let body = vec![Term::Literal(Value::Integer(123))];
  let expected = ParsedModule {
    functions: vec![],
    tests: vec![],
    statements: vec![StatementRecord {
      id: StatementId("test.0".to_string()),
      file_id: FileId("test".to_string()),
      body: body.clone(),
      content_hash: hash_terms(&body),
      generation: Generation::NewOnly,
      index: 0,
    }],
  };
  assert_eq!(result, expected);
}

#[test]
fn test_string() {
  let result = parse_source("test", "'hello',").expect("Parse failed");
  let body = vec![Term::Literal(Value::String("hello".to_string()))];
  let expected = ParsedModule {
    functions: vec![],
    tests: vec![],
    statements: vec![StatementRecord {
      id: StatementId("test.0".to_string()),
      file_id: FileId("test".to_string()),
      body: body.clone(),
      content_hash: hash_terms(&body),
      generation: Generation::NewOnly,
      index: 0,
    }],
  };
  assert_eq!(result, expected);
}

#[test]
fn test_ops() {
  let result = parse_source("test", "1 2 +,").expect("Parse failed");
  let body_0 = vec![Term::Literal(Value::Integer(1))];
  let body_1 = vec![Term::Literal(Value::Integer(2))];
  let body_2 = vec![Term::Word("+".to_string())];

  let expected = ParsedModule {
    functions: vec![],
    tests: vec![],
    statements: vec![
      StatementRecord {
        id: StatementId("test.0".to_string()),
        file_id: FileId("test".to_string()),
        body: body_0.clone(),
        content_hash: hash_terms(&body_0),
        generation: Generation::NewOnly,
        index: 0,
      },
      StatementRecord {
        id: StatementId("test.1".to_string()),
        file_id: FileId("test".to_string()),
        body: body_1.clone(),
        content_hash: hash_terms(&body_1),
        generation: Generation::NewOnly,
        index: 1,
      },
      StatementRecord {
        id: StatementId("test.2".to_string()),
        file_id: FileId("test".to_string()),
        body: body_2.clone(),
        content_hash: hash_terms(&body_2),
        generation: Generation::NewOnly,
        index: 2,
      },
    ],
  };
  assert_eq!(result, expected);
}

#[test]
fn test_def() {
  let input = "def main fn 'Hi' say end-fn,";
  let result = parse_source("test", input).expect("Parse failed");

  let expected = ParsedModule {
    functions: vec![FunctionRecord {
      id: FunctionId("main".to_string()),
      name: "main".to_string(),
      file_id: FileId("test".to_string()),
      body: vec![
        Term::Literal(Value::String("Hi".to_string())),
        Term::Word("say".to_string()),
      ],
      content_hash: hash_terms(&[
        Term::Literal(Value::String("Hi".to_string())),
        Term::Word("say".to_string()),
      ]),
      generation: Generation::NewOnly,
      index: 0,
    }],
    tests: vec![],
    statements: vec![],
  };

  assert_eq!(result, expected);
}

#[test]
fn test_parse_error_malformed_def() {
  let input = "def f 2 end-fn,";
  let err = parse_source("test", input).expect_err("Should have failed");
  assert_eq!(
    err.to_string(),
    "Error: invalid function definition\n  def f 2 end-fn,\n        ^"
  );
}

#[test]
fn test_parse_error_reserved_word() {
  let input = "fn";
  let err = parse_source("test", input).expect_err("Should have failed");
  assert_eq!(err.to_string(), "Error: invalid end of input\n  fn\n  ^");
}

#[test]
fn test_comments() {
  let input = "-- comment\n 1,";
  let result = parse_source("test", input).expect("Parse failed");
  let body = vec![Term::Literal(Value::Integer(1))];
  let expected = ParsedModule {
    functions: vec![],
    tests: vec![],
    statements: vec![StatementRecord {
      id: StatementId("test.0".to_string()),
      file_id: FileId("test".to_string()),
      body: body.clone(),
      content_hash: hash_terms(&body),
      generation: Generation::NewOnly,
      index: 0,
    }],
  };
  assert_eq!(result, expected);
}

#[test]
fn test_multiline_test() {
  let input = r"
        test
            1 1 + 2 eq assert
        end-test,
    ";
  let result = parse_source("test", input).expect("Parse failed");

  let body = vec![
    Term::Literal(Value::Integer(1)),
    Term::Literal(Value::Integer(1)),
    Term::Word("+".to_string()),
    Term::Literal(Value::Integer(2)),
    Term::Word("eq".to_string()),
    Term::Word("assert".to_string()),
  ];
  let hash = hash_terms(&body);

  let expected = ParsedModule {
    functions: vec![],
    tests: vec![TestRecord {
      id: TestId("test.0".to_string()),
      file_id: FileId("test".to_string()),
      body,
      content_hash: hash,
      generation: Generation::NewOnly,
      index: 0,
    }],
    statements: vec![],
  };

  assert_eq!(result, expected);
}
