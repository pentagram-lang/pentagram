use super::*;
use boot_db::Builtin;
use boot_db::ContentHash;
use boot_db::DependencyFunctionRecord;
use boot_db::DependencyTestRecord;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::Generation;
use boot_db::ResolvedFunctionRecord;
use boot_db::ResolvedTerm;
use boot_db::ResolvedTestRecord;
use boot_db::ResolvedWord;
use boot_db::TestId;
use boot_db::Value;
use pretty_assertions::assert_eq;

#[test]
fn test_analyze_dependency_transitive_hash() {
  let file_id = FileId("test.penta".to_string());

  let func_a = ResolvedFunctionRecord {
    id: FunctionId("a".to_string()),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewOnly,
  };

  let func_b = ResolvedFunctionRecord {
    id: FunctionId("b".to_string()),
    file_id: file_id.clone(),
    body: vec![ResolvedTerm::Word(ResolvedWord::Function(FunctionId(
      "a".to_string(),
    )))],
    content_hash: ContentHash([2; 32]),
    generation: Generation::NewOnly,
  };

  let test_t = ResolvedTestRecord {
    id: TestId("t".to_string()),
    file_id: file_id.clone(),
    body: vec![ResolvedTerm::Word(ResolvedWord::Function(FunctionId(
      "b".to_string(),
    )))],
    content_hash: ContentHash([3; 32]),
    generation: Generation::NewOnly,
  };

  let input = AnalyzeInput {
    resolved_functions: &[func_a, func_b],
    resolved_tests: &[test_t],
  };

  let result = analyze_dependency_graph(&input).unwrap();

  let mut hasher_a = Hasher::new();
  hasher_a.update(&[1; 32]);
  let expected_hash_a: ContentHash = hasher_a.finalize().into();

  let mut hasher_b = Hasher::new();
  hasher_b.update(&[2; 32]);
  hasher_b.update(&expected_hash_a.0);
  let expected_hash_b: ContentHash = hasher_b.finalize().into();

  let mut hasher_t = Hasher::new();
  hasher_t.update(&[3; 32]);
  hasher_t.update(&expected_hash_b.0);
  let expected_hash_t: ContentHash = hasher_t.finalize().into();

  let expected = AnalyzeOutput {
    function_dependencies: vec![
      DependencyFunctionRecord {
        id: FunctionId("a".to_string()),
        content_hash: expected_hash_a,
        generation: Generation::NewOnly,
      },
      DependencyFunctionRecord {
        id: FunctionId("b".to_string()),
        content_hash: expected_hash_b,
        generation: Generation::NewOnly,
      },
    ],
    test_dependencies: vec![DependencyTestRecord {
      id: TestId("t".to_string()),
      content_hash: expected_hash_t,
      generation: Generation::NewOnly,
    }],
  };

  assert_eq!(result, expected);
}

#[test]
fn test_analyze_dependency_basic() {
  let file_id = FileId("test.penta".to_string());
  let func = ResolvedFunctionRecord {
    id: FunctionId("main".to_string()),
    file_id,
    body: vec![
      ResolvedTerm::Literal(Value::Integer(10)),
      ResolvedTerm::Word(ResolvedWord::Function(FunctionId(
        "inc".to_string(),
      ))),
      ResolvedTerm::Word(ResolvedWord::Builtin(Builtin::Add)),
    ],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewOnly,
  };

  let func_inc = ResolvedFunctionRecord {
    id: FunctionId("inc".to_string()),
    file_id: FileId("test.penta".to_string()),
    body: vec![],
    content_hash: ContentHash([2; 32]),
    generation: Generation::NewOnly,
  };

  let input = AnalyzeInput {
    resolved_functions: &[func, func_inc],
    resolved_tests: &[],
  };

  let result = analyze_dependency_graph(&input).unwrap();

  let mut hasher_inc = Hasher::new();
  hasher_inc.update(&[2; 32]);

  let expected_hash_inc: ContentHash = hasher_inc.finalize().into();

  let mut hasher_main = Hasher::new();
  hasher_main.update(&[1; 32]);
  hasher_main.update(&expected_hash_inc.0);
  let expected_hash_main: ContentHash = hasher_main.finalize().into();

  let expected = AnalyzeOutput {
    function_dependencies: vec![
      DependencyFunctionRecord {
        id: FunctionId("main".to_string()),
        content_hash: expected_hash_main,
        generation: Generation::NewOnly,
      },
      DependencyFunctionRecord {
        id: FunctionId("inc".to_string()),
        content_hash: expected_hash_inc,
        generation: Generation::NewOnly,
      },
    ],
    test_dependencies: vec![],
  };

  assert_eq!(result, expected);
}
