use super::*;
use blake3::Hasher;
use boot_db::ContentHash;
use boot_db::DependencyFunctionRecord;
use boot_db::DependencyTestRecord;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::ResolvedFunctionRecord;
use boot_db::ResolvedTerm;
use boot_db::ResolvedTestRecord;
use boot_db::ResolvedWord;
use boot_db::Span;
use boot_db::Spanned;
use boot_db::TestId;
use boot_db::TestRecord;
use pretty_assertions::assert_eq;

fn s<T>(val: T) -> Spanned<T> {
  Spanned::new(val, Span { start: 0, end: 0 })
}

#[test]
fn test_analyze_dependencies_mapping() {
  let mut db = Database::default();

  let id_a = FunctionId("a".to_string());
  let id_b = FunctionId("b".to_string());
  let id_t = TestId("t".to_string());
  let file_id = FileId("test.penta".to_string());

  db.functions.push(FunctionRecord {
    id: id_a.clone(),
    name: "a".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewOnly,
    index: 0,
  });
  db.functions.push(FunctionRecord {
    id: id_b.clone(),
    name: "b".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([2; 32]),
    generation: Generation::NewOnly,
    index: 0,
  });
  db.tests.push(TestRecord {
    id: id_t.clone(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([3; 32]),
    generation: Generation::NewOnly,
    index: 0,
  });

  db.resolved_functions.push(ResolvedFunctionRecord {
    id: id_a.clone(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewOnly,
  });

  db.resolved_functions.push(ResolvedFunctionRecord {
    id: id_b.clone(),
    file_id: file_id.clone(),
    body: vec![s(ResolvedTerm::Word(ResolvedWord::Function(
      id_a.clone(),
    )))],
    content_hash: ContentHash([2; 32]),
    generation: Generation::NewOnly,
  });

  db.resolved_tests.push(ResolvedTestRecord {
    id: id_t.clone(),
    file_id: file_id.clone(),
    body: vec![s(ResolvedTerm::Word(ResolvedWord::Function(
      id_b.clone(),
    )))],
    content_hash: ContentHash([3; 32]),
    generation: Generation::NewOnly,
  });

  analyze_dependencies(&mut db);

  let mut hasher_a = Hasher::new();
  hasher_a.update(&[1; 32]);
  let hash_a: ContentHash = hasher_a.finalize().into();

  let mut hasher_b = Hasher::new();
  hasher_b.update(&[2; 32]);
  hasher_b.update(&hash_a.0);
  let hash_b: ContentHash = hasher_b.finalize().into();

  let mut hasher_t = Hasher::new();
  hasher_t.update(&[3; 32]);
  hasher_t.update(&hash_b.0);
  let hash_t: ContentHash = hasher_t.finalize().into();

  let mut expected_func_deps = vec![
    DependencyFunctionRecord {
      id: id_a.clone(),
      content_hash: hash_a,
      generation: Generation::NewOnly,
    },
    DependencyFunctionRecord {
      id: id_b.clone(),
      content_hash: hash_b,
      generation: Generation::NewOnly,
    },
  ];

  let expected_test_deps = vec![DependencyTestRecord {
    id: id_t.clone(),
    content_hash: hash_t,
    generation: Generation::NewOnly,
  }];

  db.function_dependencies.sort_by_key(|d| d.id.clone());
  expected_func_deps.sort_by_key(|d| d.id.clone());
  assert_eq!(db.function_dependencies, expected_func_deps);
  assert_eq!(db.test_dependencies, expected_test_deps);
}

#[test]
fn test_analyze_uses_resolved_hash() {
  let mut db = Database::default();
  let id = FunctionId("a".to_string());
  let file_id = FileId("test.penta".to_string());

  db.functions.push(FunctionRecord {
    id: id.clone(),
    name: "a".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewOnly,
    index: 0,
  });

  db.resolved_functions.push(ResolvedFunctionRecord {
    id: id.clone(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([9; 32]),
    generation: Generation::NewOnly,
  });

  analyze_dependencies(&mut db);

  let mut hasher = Hasher::new();
  hasher.update(&[9; 32]);
  let expected_content_hash: ContentHash = hasher.finalize().into();

  assert_eq!(
    db.function_dependencies[0].content_hash,
    expected_content_hash
  );
  assert_ne!(
    db.function_dependencies[0].content_hash,
    ContentHash([1; 32])
  );
}
