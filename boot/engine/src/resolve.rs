use boot_db::Database;
use boot_db::DiagnosticResult;
use boot_db::Generation;
use boot_resolve::ResolveInput;
use boot_resolve::resolve_module as resolve_source_module;

pub(crate) fn resolve_module(db: &mut Database) -> DiagnosticResult<()> {
  let functions: Vec<_> = db
    .functions
    .iter()
    .filter(|f| f.generation.is_new())
    .cloned()
    .collect();

  let tests: Vec<_> = db
    .tests
    .iter()
    .filter(|t| t.generation.is_new())
    .cloned()
    .collect();

  let statements: Vec<_> = db
    .statements
    .iter()
    .filter(|s| s.generation.is_new())
    .cloned()
    .collect();

  let resolve_output = resolve_source_module(&ResolveInput {
    functions: &functions,
    tests: &tests,
    statements: &statements,
  })?;

  let mut new_resolved_functions = resolve_output.resolved_functions;
  for existing in &mut db.resolved_functions {
    if existing.generation == Generation::OldOnly {
      if let Some(pos) = new_resolved_functions.iter().position(|f| {
        f.id == existing.id && f.content_hash == existing.content_hash
      }) {
        existing.generation = Generation::NewAndOld;
        new_resolved_functions.swap_remove(pos);
      }
    }
  }
  db.resolved_functions.extend(new_resolved_functions);

  let mut new_resolved_tests = resolve_output.resolved_tests;
  for existing in &mut db.resolved_tests {
    if existing.generation == Generation::OldOnly {
      if let Some(pos) = new_resolved_tests.iter().position(|t| {
        t.id == existing.id && t.content_hash == existing.content_hash
      }) {
        existing.generation = Generation::NewAndOld;
        new_resolved_tests.swap_remove(pos);
      }
    }
  }
  db.resolved_tests.extend(new_resolved_tests);

  let mut new_resolved_statements = resolve_output.resolved_statements;
  for existing in &mut db.resolved_statements {
    if existing.generation == Generation::OldOnly {
      if let Some(pos) = new_resolved_statements.iter().position(|s| {
        s.id == existing.id
          && s.content_hash == existing.content_hash
          && s.index == existing.index
      }) {
        existing.generation = Generation::NewAndOld;
        new_resolved_statements.swap_remove(pos);
      }
    }
  }
  db.resolved_statements.extend(new_resolved_statements);

  Ok(())
}

#[cfg(test)]
#[path = "resolve_test.rs"]
mod resolve_test;
