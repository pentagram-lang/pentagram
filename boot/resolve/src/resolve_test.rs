use super::*;
use boot_db::ContentHash;
use boot_db::FileId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::StatementId;
use boot_db::StatementRecord;
use boot_db::Term;
use boot_db::hash_resolved_terms;
use boot_db::hash_terms;
use pretty_assertions::assert_eq;
use std::slice::from_ref;

#[test]
fn test_resolve_undefined_reference() {
  let file_id = FileId("test.penta".to_string());
  let func = FunctionRecord {
    id: FunctionId("main".to_string()),
    name: "main".to_string(),
    file_id,
    body: vec![Term::Word("unknown_func".to_string())],
    content_hash: ContentHash([0; 32]),
    generation: Generation::NewOnly,
    index: 0,
  };

  let input = ResolveInput {
    functions: from_ref(&func),
    tests: &[],
    statements: &[],
  };

  let result = resolve_module(&input).expect_err("Should have failed");
  assert_eq!(result.to_string(), "Undefined reference: unknown_func");
}

#[test]
fn test_resolve_known_reference() {
  let file_id = FileId("test.penta".to_string());
  let inc = FunctionRecord {
    id: FunctionId("inc".to_string()),
    name: "inc".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([0; 32]),
    generation: Generation::NewOnly,
    index: 0,
  };
  let main = FunctionRecord {
    id: FunctionId("main".to_string()),
    name: "main".to_string(),
    file_id: file_id.clone(),
    body: vec![Term::Word("inc".to_string())],
    content_hash: ContentHash([0; 32]),
    generation: Generation::NewOnly,
    index: 0,
  };

  let input = ResolveInput {
    functions: &[inc.clone(), main.clone()],
    tests: &[],
    statements: &[],
  };

  let result = resolve_module(&input).unwrap();

  let inc_body = vec![];
  let inc_hash = hash_resolved_terms(&inc_body);

  let main_body = vec![ResolvedTerm::Word(ResolvedWord::Function(
    FunctionId("inc".to_string()),
  ))];
  let main_hash = hash_resolved_terms(&main_body);

  let expected = ResolveOutput {
    resolved_functions: vec![
      ResolvedFunctionRecord {
        id: FunctionId("inc".to_string()),
        file_id: file_id.clone(),
        body: inc_body,
        content_hash: inc_hash,
        generation: Generation::NewOnly,
      },
      ResolvedFunctionRecord {
        id: FunctionId("main".to_string()),
        file_id,
        body: main_body,
        content_hash: main_hash,
        generation: Generation::NewOnly,
      },
    ],
    resolved_tests: vec![],
    resolved_statements: vec![],
  };

  assert_eq!(result, expected);
}

#[test]
fn test_resolve_statement_scope_fail() {
  let file_id = FileId("test.penta".to_string());
  let func_b = FunctionRecord {
    id: FunctionId("B".to_string()),
    name: "B".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([0; 32]),
    generation: Generation::NewOnly,
    index: 15,
  };

  let body = vec![Term::Word("B".to_string())];
  let stmt = StatementRecord {
    id: StatementId("test.penta:10".to_string()),
    file_id: file_id.clone(),
    body: body.clone(),
    content_hash: hash_terms(&body),
    generation: Generation::NewOnly,
    index: 10,
  };

  let input = ResolveInput {
    functions: from_ref(&func_b),
    tests: &[],
    statements: from_ref(&stmt),
  };

  let result =
    resolve_module(&input).expect_err("Scoped lookup should fail for B");
  assert_eq!(result.to_string(), "Undefined reference: B");
}

#[test]
fn test_resolve_statement_scope_success() {
  let file_id = FileId("test.penta".to_string());
  let func_a = FunctionRecord {
    id: FunctionId("A".to_string()),
    name: "A".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([0; 32]),
    generation: Generation::NewOnly,
    index: 5,
  };

  let body = vec![Term::Word("A".to_string())];
  let stmt = StatementRecord {
    id: StatementId("test.penta:10".to_string()),
    file_id: file_id.clone(),
    body: body.clone(),
    content_hash: hash_terms(&body),
    generation: Generation::NewOnly,
    index: 10,
  };

  let input = ResolveInput {
    functions: from_ref(&func_a),
    tests: &[],
    statements: from_ref(&stmt),
  };

  resolve_module(&input).expect("Scoped lookup should succeed for A");
}

#[test]
fn test_resolve_redefinition_fail() {
  let file_id = FileId("test.penta".to_string());
  let func_1 = FunctionRecord {
    id: FunctionId("foo".to_string()),
    name: "foo".to_string(),
    file_id: file_id.clone(),
    body: vec![Term::Word("foo".to_string())],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewOnly,
    index: 0,
  };
  let func_2 = FunctionRecord {
    id: FunctionId("foo".to_string()),
    name: "foo".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([2; 32]),
    generation: Generation::NewOnly,
    index: 1,
  };

  let input = ResolveInput {
    functions: &[func_1, func_2],
    tests: &[],
    statements: &[],
  };

  let result =
    resolve_module(&input).expect_err("Should detect redefinition");
  assert_eq!(result.to_string(), "Function redefinition: foo");
}
