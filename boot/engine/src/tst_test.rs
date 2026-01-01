use super::*;
use boot_db::ContentHash;
use boot_db::DependencyTestRecord;
use boot_db::FileId;
use boot_db::Generation;
use boot_db::ResolvedTestRecord;
use boot_db::TestId;
use boot_db::TestResultRecord;
use boot_db::hash_test_result;
use pretty_assertions::assert_eq;

#[test]
fn test_incremental_execution_logic() {
  let mut db = Database::default();

  let test_id_run = TestId("run".to_string());
  let test_id_skip = TestId("skip".to_string());
  let test_id_match = TestId("match".to_string());

  let hash_run = ContentHash([1; 32]);
  let hash_skip = ContentHash([2; 32]);
  let hash_match = ContentHash([3; 32]);

  let file_id = FileId("test.penta".to_string());

  // 1. Test to be RUN (NewOnly dependency)
  db.test_dependencies.push(DependencyTestRecord {
    id: test_id_run.clone(),
    content_hash: hash_run,
    generation: Generation::NewOnly,
  });
  db.resolved_tests.push(ResolvedTestRecord {
    id: test_id_run.clone(),
    file_id: file_id.clone(),
    body: vec![], // Empty body runs and passes
    content_hash: hash_run,
    generation: Generation::NewOnly,
  });

  // 2. Test to be SKIPPED (NewAndOld dependency, matches OldOnly result)
  db.test_dependencies.push(DependencyTestRecord {
    id: test_id_skip.clone(),
    content_hash: hash_skip,
    generation: Generation::NewAndOld,
  });
  db.test_results.push(TestResultRecord {
    id: test_id_skip.clone(),
    passed: true,
    output: "Skipped\n".to_string(),
    content_hash: hash_test_result(true, "Skipped\n"),
    generation: Generation::OldOnly,
  });

  // 3. Test that MATCHES existing (Promoted to NewAndOld)
  db.test_dependencies.push(DependencyTestRecord {
    id: test_id_match.clone(),
    content_hash: hash_match,
    generation: Generation::NewOnly,
  });
  db.resolved_tests.push(ResolvedTestRecord {
    id: test_id_match.clone(),
    file_id: file_id.clone(),
    body: vec![],
    content_hash: hash_match,
    generation: Generation::NewOnly,
  });
  db.test_results.push(TestResultRecord {
    id: test_id_match.clone(),
    passed: true,
    output: String::new(),
    content_hash: hash_test_result(true, ""),
    generation: Generation::OldOnly,
  });

  run_engine_tests_incrementally(&mut db);

  let mut results = db.test_results.clone();
  results.sort_by(|a, b| a.id.0.cmp(&b.id.0));

  let expected_results = vec![
    TestResultRecord {
      id: test_id_match.clone(),
      passed: true,
      output: String::new(),
      content_hash: hash_test_result(true, ""),
      generation: Generation::NewAndOld,
    },
    TestResultRecord {
      id: test_id_run.clone(),
      passed: true,
      output: String::new(),
      content_hash: hash_test_result(true, ""),
      generation: Generation::NewOnly,
    },
    TestResultRecord {
      id: test_id_skip.clone(),
      passed: true,
      output: "Skipped\n".to_string(),
      content_hash: hash_test_result(true, "Skipped\n"),
      generation: Generation::NewAndOld,
    },
  ];

  assert_eq!(results, expected_results);
}
