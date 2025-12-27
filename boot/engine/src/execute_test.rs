use super::*;
use boot_db::Builtin;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::Generation;
use boot_db::ResolvedFunctionRecord;
use boot_db::ResolvedStatementRecord;
use boot_db::ResolvedTerm;
use boot_db::ResolvedWord;
use boot_db::StatementId;
use boot_db::Value;
use boot_db::hash_resolved_terms;
use pretty_assertions::assert_eq;
use std::io::Error as IoError;
use std::io::Result as IoResult;
use std::io::Write;
use std::sync::Arc;
use std::sync::Mutex;

#[derive(Clone, Default)]
struct TestOutput(Arc<Mutex<Vec<u8>>>);

impl Write for TestOutput {
  fn write(&mut self, buf: &[u8]) -> IoResult<usize> {
    self
      .0
      .lock()
      .map_err(|e| IoError::other(e.to_string()))?
      .write(buf)
  }

  fn flush(&mut self) -> IoResult<()> {
    self
      .0
      .lock()
      .map_err(|e| IoError::other(e.to_string()))?
      .flush()
  }
}

#[test]
fn test_execute_main() {
  let mut db = Database::default();

  let body = vec![
    ResolvedTerm::Literal(Value::String("Hello".to_string())),
    ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Say)),
  ];
  let hash = hash_resolved_terms(&body);
  db.resolved_functions.push(ResolvedFunctionRecord {
    id: FunctionId("main".to_string()),
    file_id: FileId("test.penta".to_string()),
    body,
    content_hash: hash,
    generation: Generation::NewOnly,
  });

  let mut out = TestOutput::default();
  run_main(&mut db, &mut out).expect("Main failed");
  assert_eq!(
    String::from_utf8(out.0.lock().expect("Lock poisoned").clone())
      .unwrap(),
    "Hello\n"
  );
}

#[test]
fn test_execute_statements() {
  let mut db = Database::default();
  let file_id = FileId("test.penta".to_string());

  let body_a = vec![
    ResolvedTerm::Literal(Value::String("A".to_string())),
    ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Say)),
  ];
  let hash_a = hash_resolved_terms(&body_a);
  db.resolved_statements.push(ResolvedStatementRecord {
    file_id: file_id.clone(),
    body: body_a,
    content_hash: hash_a,
    generation: Generation::NewOnly,
    index: 0,
    id: StatementId("test.penta:0".to_string()),
  });

  let body_c = vec![
    ResolvedTerm::Literal(Value::String("C".to_string())),
    ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Say)),
  ];
  let hash_c = hash_resolved_terms(&body_c);
  db.resolved_statements.push(ResolvedStatementRecord {
    file_id: file_id.clone(),
    body: body_c,
    content_hash: hash_c,
    generation: Generation::NewOnly,
    index: 2,
    id: StatementId("test.penta:2".to_string()),
  });

  let body_b = vec![
    ResolvedTerm::Literal(Value::String("B".to_string())),
    ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Say)),
  ];
  let hash_b = hash_resolved_terms(&body_b);
  db.resolved_statements.push(ResolvedStatementRecord {
    file_id: file_id.clone(),
    body: body_b,
    content_hash: hash_b,
    generation: Generation::NewOnly,
    index: 1,
    id: StatementId("test.penta:1".to_string()),
  });

  let mut out = TestOutput::default();
  run_statements(&mut db, "test.penta", &mut out)
    .expect("Statements failed");
  assert_eq!(
    String::from_utf8(out.0.lock().expect("Lock poisoned").clone())
      .unwrap(),
    "A\nB\nC\n"
  );
}
