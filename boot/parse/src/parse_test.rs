use super::*;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::ResolvedDiagnosticResult;
use boot_db::Span;
use boot_db::Spanned;
use boot_db::StatementId;
use boot_db::StatementRecord;
use boot_db::Term;
use boot_db::TestId;
use boot_db::TestRecord;
use boot_db::Value;
use boot_db::hash_terms;
use pretty_assertions::assert_eq;

fn parse_str(input: &str) -> ResolvedDiagnosticResult<ParsedModule> {
  let tokens =
    boot_lex::lex_source("test", input, boot_db::ContentHash([0; 32]))
      .map_err(|diagnostic| {
        let mut db = boot_db::Database::default();
        db.files.push(boot_db::FileRecord {
          id: FileId("test".to_string()),
          path: "test".to_string(),
          source: input.to_string(),
          content_hash: boot_db::ContentHash([0; 32]),
          generation: Generation::NewOnly,
        });
        diagnostic.resolve(&db)
      })?;
  let result = parse_source("test", input, &tokens);

  match result {
    Err(diagnostic) => {
      let mut db = boot_db::Database::default();
      db.files.push(boot_db::FileRecord {
        id: FileId("test".to_string()),
        path: "test".to_string(),
        source: input.to_string(),
        content_hash: boot_db::ContentHash([0; 32]),
        generation: Generation::NewOnly,
      });
      Err(diagnostic.resolve(&db))
    }
    Ok(module) => Ok(module),
  }
}

fn s<T>(value: T, start: usize, end: usize) -> Spanned<T> {
  Spanned::new(value, Span { start, end })
}

#[test]
fn test_integer() {
  let result = parse_str("123,").expect("Parse failed");
  let body = vec![s(Term::Literal(Value::Integer(123)), 0, 3)];
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
  let result = parse_str("'hello',").expect("Parse failed");
  let body =
    vec![s(Term::Literal(Value::String("hello".to_string())), 0, 7)];
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
  let result = parse_str("1 2 +,").expect("Parse failed");
  let body_0 = vec![s(Term::Literal(Value::Integer(1)), 0, 1)];
  let body_1 = vec![s(Term::Literal(Value::Integer(2)), 2, 3)];
  let body_2 = vec![s(Term::Word("+".to_string()), 4, 5)];

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
  let result = parse_str(input).expect("Parse failed");

  let expected = ParsedModule {
    functions: vec![FunctionRecord {
      id: FunctionId("main".to_string()),
      name: "main".to_string(),
      file_id: FileId("test".to_string()),
      body: vec![
        s(Term::Literal(Value::String("Hi".to_string())), 12, 16),
        s(Term::Word("say".to_string()), 17, 20),
      ],
      content_hash: hash_terms(&[
        s(Term::Literal(Value::String("Hi".to_string())), 12, 16),
        s(Term::Word("say".to_string()), 17, 20),
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
  let err = parse_str(input).expect_err("Should have failed");
  assert_eq!(err.error_message, "expected 'fn'");
}

#[test]
fn test_parse_error_reserved_word() {
  let input = "fn";
  let err = parse_str(input).expect_err("Should have failed");
  assert_eq!(err.error_message, "expected term");
}
#[test]
fn test_comments() {
  let input = "-- comment --\n 1,";
  let result = parse_str(input).expect("Parse failed");
  let body = vec![s(Term::Literal(Value::Integer(1)), 15, 16)];
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
  let input = "
        test
            1 1 + 2 eq assert
        end-test,
    ";
  let result = parse_str(input).expect("Parse failed");

  // Offset calculation:
  // \n (1)
  //         test (8 spaces + 4 = 12) -> end at 13
  // \n (1)
  //             (12 spaces)
  // 1 (1) -> 13 + 1 + 12 = 26. End 27.
  //   (1)
  // 1 (1) -> 28. End 29.
  //   (1)
  // + (1) -> 30. End 31.
  //   (1)
  // 2 (1) -> 32. End 33.
  //   (1)
  // eq (2) -> 34. End 36.
  //    (1)
  // assert (6) -> 37. End 43.

  let body = vec![
    s(Term::Literal(Value::Integer(1)), 26, 27),
    s(Term::Literal(Value::Integer(1)), 28, 29),
    s(Term::Word("+".to_string()), 30, 31),
    s(Term::Literal(Value::Integer(2)), 32, 33),
    s(Term::Word("eq".to_string()), 34, 36),
    s(Term::Word("assert".to_string()), 37, 43),
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
