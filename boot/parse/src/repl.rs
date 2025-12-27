use crate::parse::parse_source;
use crate::shred::ParsedModule;
use anyhow::Result as AnyhowResult;
use boot_db::TokenStreamRecord;
use std::collections::HashSet;

pub fn parse_repl_module(
  path: &str,
  source: &str,
  token_stream: &TokenStreamRecord,
  old_functions: Vec<boot_db::FunctionRecord>,
  old_tests: Vec<boot_db::TestRecord>,
) -> AnyhowResult<ParsedModule> {
  let new_module = parse_source(path, source, token_stream)?;

  let new_def_names: HashSet<String> = new_module
    .functions
    .iter()
    .map(|f| f.name.clone())
    .collect();

  let mut final_functions = Vec::new();
  for func in old_functions {
    if !new_def_names.contains(&func.name) {
      final_functions.push(func);
    }
  }
  final_functions.extend(new_module.functions);

  let mut final_tests = old_tests;
  final_tests.extend(new_module.tests);

  let final_statements = new_module.statements;

  Ok(ParsedModule {
    functions: final_functions,
    tests: final_tests,
    statements: final_statements,
  })
}

#[cfg(test)]
#[path = "repl_test.rs"]
mod repl_test;
