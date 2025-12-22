use super::*;
use boot_db::ContentHash;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::TestId;
use boot_db::TestResultRecord;
use boot_db::hash_test_result;
use pretty_assertions::assert_eq;

#[test]
fn test_generation_lifecycle() {
  let mut db = Database::default();

  let record = FunctionRecord {
    id: FunctionId("test".to_string()),
    name: "test".to_string(),
    file_id: FileId("test.penta".to_string()),
    body: vec![],
    content_hash: ContentHash([0; 32]),
    generation: Generation::NewOnly,
    index: 0,
  };
  db.functions.push(record.clone());

  commit_engine_generation(&mut db);
  let expected_after_commit_1 = vec![FunctionRecord {
    generation: Generation::OldOnly,
    ..record.clone()
  }];
  assert_eq!(db.functions, expected_after_commit_1);

  db.functions[0].generation = Generation::NewOnly;
  commit_engine_generation(&mut db);
  assert_eq!(db.functions, expected_after_commit_1);

  db.functions[0].generation = Generation::OldOnly;
  commit_engine_generation(&mut db);
  assert!(db.functions.is_empty());
}

#[test]
fn test_test_result_lifecycle() {
  let mut db = Database::default();

  let output = "Passed\n".to_string();
  let hash = hash_test_result(true, &output);

  let record = TestResultRecord {
    id: TestId("test".to_string()),
    passed: true,
    output,
    content_hash: hash,
    generation: Generation::NewOnly,
  };
  db.test_results.push(record.clone());

  commit_engine_generation(&mut db);
  let expected_after_commit_1 = vec![TestResultRecord {
    generation: Generation::OldOnly,
    ..record.clone()
  }];
  assert_eq!(db.test_results, expected_after_commit_1);

  commit_engine_generation(&mut db);
  assert!(db.test_results.is_empty());
}

#[test]
fn test_rollback_lifecycle() {
  let mut db = Database::default();

  let old_record = FunctionRecord {
    id: FunctionId("old".to_string()),
    name: "old".to_string(),
    file_id: FileId("test.penta".to_string()),
    body: vec![],
    content_hash: ContentHash([0; 32]),
    generation: Generation::OldOnly,
    index: 0,
  };
  let new_record = FunctionRecord {
    id: FunctionId("new".to_string()),
    name: "new".to_string(),
    file_id: FileId("test.penta".to_string()),
    body: vec![],
    content_hash: ContentHash([1; 32]),
    generation: Generation::NewOnly,
    index: 1,
  };
  let shared_record = FunctionRecord {
    id: FunctionId("shared".to_string()),
    name: "shared".to_string(),
    file_id: FileId("test.penta".to_string()),
    body: vec![],
    content_hash: ContentHash([2; 32]),
    generation: Generation::NewAndOld,
    index: 2,
  };

  db.functions.push(old_record.clone());
  db.functions.push(new_record.clone());
  db.functions.push(shared_record.clone());

  rollback_engine_generation(&mut db);

  let expected = vec![
    FunctionRecord {
      generation: Generation::OldOnly,
      ..old_record
    },
    FunctionRecord {
      generation: Generation::OldOnly,
      ..shared_record
    },
  ];
  assert_eq!(db.functions, expected);
}
