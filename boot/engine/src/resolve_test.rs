use super::*;
use boot_db::ContentHash;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::ResolvedFunctionRecord;
use pretty_assertions::assert_eq;

#[test]
fn test_resolve_engine_filtering() {
  let mut db = Database::default();
  let file_id = FileId("test.penta".to_string());

  db.functions.push(FunctionRecord {
    id: FunctionId("old_func".to_string()),
    name: "old_func".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([0; 32]),
    generation: Generation::OldOnly,
    index: 0,
  });

  db.functions.push(FunctionRecord {
    id: FunctionId("new_func".to_string()),
    name: "new_func".to_string(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewOnly,
    index: 0,
  });

  resolve_module(&mut db).expect("Resolve failed");

  let expected_resolved = vec![ResolvedFunctionRecord {
    id: FunctionId("new_func".to_string()),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: boot_db::hash_resolved_terms(&[]),
    generation: Generation::NewOnly,
  }];

  assert_eq!(db.resolved_functions, expected_resolved);
}
