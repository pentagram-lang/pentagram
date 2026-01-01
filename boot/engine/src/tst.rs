use boot_db::Database;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::Generation;
use boot_db::SpannedResolvedTerm;
use boot_db::TestId;
use boot_db::TestResultRecord;
use boot_db::hash_test_result;
use boot_test::TestInput;
use boot_test::TestRunResult;
use boot_test::run_tests;
use std::collections::HashMap;

pub(crate) fn run_engine_tests_incrementally(db: &mut Database) {
  let tests_to_run = select_tests_for_execution(db);
  let functions = get_engine_functions_map(db);
  let results = run_tests(&TestInput {
    tests_to_run: &tests_to_run,
    functions: &functions,
  });

  let mut next_results = create_records_from_run_results(results);
  next_results.extend(promote_unchanged_results(db));

  merge_results_into_database(db, next_results);
}

fn select_tests_for_execution(
  db: &Database,
) -> Vec<(TestId, FileId, Vec<SpannedResolvedTerm>)> {
  db.test_dependencies
    .iter()
    .filter(|dep| dep.generation == Generation::NewOnly)
    .filter_map(|dep| {
      db.resolved_tests
        .iter()
        .find(|t| t.id == dep.id && t.generation.is_new())
    })
    .map(|resolved| {
      (
        resolved.id.clone(),
        resolved.file_id.clone(),
        resolved.body.clone(),
      )
    })
    .collect()
}

fn create_records_from_run_results(
  results: Vec<TestRunResult>,
) -> Vec<TestResultRecord> {
  results
    .into_iter()
    .map(|res| TestResultRecord {
      id: res.test_id,
      passed: res.passed,
      content_hash: hash_test_result(res.passed, &res.output),
      output: res.output,
      generation: Generation::NewOnly,
    })
    .collect()
}

fn promote_unchanged_results(db: &Database) -> Vec<TestResultRecord> {
  db.test_dependencies
    .iter()
    .filter(|dep| dep.generation == Generation::NewAndOld)
    .filter_map(|dep| {
      db.test_results
        .iter()
        .find(|r| r.id == dep.id && r.generation == Generation::OldOnly)
    })
    .map(|existing| {
      let mut promoted = existing.clone();
      promoted.generation = Generation::NewOnly;
      promoted
    })
    .collect()
}

fn merge_results_into_database(
  db: &mut Database,
  mut next_results: Vec<TestResultRecord>,
) {
  db.test_results
    .iter_mut()
    .filter(|existing| existing.generation == Generation::OldOnly)
    .for_each(|existing| {
      if let Some(pos) = next_results.iter().position(|nr| {
        nr.id == existing.id && nr.content_hash == existing.content_hash
      }) {
        existing.generation = Generation::NewAndOld;
        next_results.swap_remove(pos);
      }
    });

  db.test_results.extend(next_results);
}

pub(crate) fn get_engine_functions_map(
  db: &Database,
) -> HashMap<FunctionId, (FileId, Vec<SpannedResolvedTerm>)> {
  db.resolved_functions
    .iter()
    .filter(|f| f.generation.is_new())
    .map(|f| (f.id.clone(), (f.file_id.clone(), f.body.clone())))
    .collect()
}

#[cfg(test)]
#[path = "tst_test.rs"]
mod tst_test;
