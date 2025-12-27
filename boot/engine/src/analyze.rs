use anyhow::Result as AnyhowResult;
use boot_analyze::AnalyzeInput;
use boot_analyze::analyze_dependency_graph;
use boot_db::Database;
use boot_db::Generation;

pub(crate) fn analyze_dependencies(db: &mut Database) -> AnyhowResult<()> {
  let resolved_functions: Vec<_> = db
    .resolved_functions
    .iter()
    .filter(|f| f.generation.is_new())
    .cloned()
    .collect();

  let resolved_tests: Vec<_> = db
    .resolved_tests
    .iter()
    .filter(|t| t.generation.is_new())
    .cloned()
    .collect();

  let analyze_output = analyze_dependency_graph(&AnalyzeInput {
    resolved_functions: &resolved_functions,
    resolved_tests: &resolved_tests,
  })?;

  let mut new_function_deps = analyze_output.function_dependencies;
  for existing in &mut db.function_dependencies {
    if existing.generation == Generation::OldOnly {
      if let Some(pos) = new_function_deps.iter().position(|d| {
        d.id == existing.id && d.content_hash == existing.content_hash
      }) {
        existing.generation = Generation::NewAndOld;
        new_function_deps.swap_remove(pos);
      }
    }
  }
  db.function_dependencies.extend(new_function_deps);

  let mut new_test_deps = analyze_output.test_dependencies;
  for existing in &mut db.test_dependencies {
    if existing.generation == Generation::OldOnly {
      if let Some(pos) = new_test_deps.iter().position(|d| {
        d.id == existing.id && d.content_hash == existing.content_hash
      }) {
        existing.generation = Generation::NewAndOld;
        new_test_deps.swap_remove(pos);
      }
    }
  }
  db.test_dependencies.extend(new_test_deps);

  Ok(())
}

#[cfg(test)]
#[path = "analyze_test.rs"]
mod analyze_test;
