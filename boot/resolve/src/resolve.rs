use anyhow::Result as AnyhowResult;
use anyhow::bail;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::ResolvedFunctionRecord;
use boot_db::ResolvedStatementRecord;
use boot_db::ResolvedTerm;
use boot_db::ResolvedTestRecord;
use boot_db::ResolvedWord;
use boot_db::StatementId;
use boot_db::StatementRecord;
use boot_db::Term;
use boot_db::TestRecord;
use boot_db::hash_resolved_terms;
use boot_db::parse_builtin;

#[derive(Debug)]
pub struct ResolveInput<'a> {
  pub functions: &'a [FunctionRecord],
  pub tests: &'a [TestRecord],
  pub statements: &'a [StatementRecord],
}

#[derive(Debug, PartialEq, Eq, Default)]
pub struct ResolveOutput {
  pub resolved_functions: Vec<ResolvedFunctionRecord>,
  pub resolved_tests: Vec<ResolvedTestRecord>,
  pub resolved_statements: Vec<ResolvedStatementRecord>,
}

pub fn resolve_module(
  input: &ResolveInput<'_>,
) -> AnyhowResult<ResolveOutput> {
  let resolved_functions =
    resolve_functions(input.functions, input.functions)?;
  let resolved_tests = resolve_tests(input.tests, input.functions)?;
  let resolved_statements =
    resolve_statements(input.statements, input.functions)?;

  Ok(ResolveOutput {
    resolved_functions,
    resolved_tests,
    resolved_statements,
  })
}

fn resolve_functions(
  functions: &[FunctionRecord],
  all_functions: &[FunctionRecord],
) -> AnyhowResult<Vec<ResolvedFunctionRecord>> {
  let mut resolved = Vec::with_capacity(functions.len());
  for func in functions {
    let body = resolve_body(&func.body, |id| {
      let matches: Vec<_> = all_functions
        .iter()
        .filter(|f| {
          if f.name != id.0 {
            return false;
          }
          f.file_id == func.file_id
        })
        .collect();

      if matches.len() > 1 {
        bail!("Function redefinition: {}", id.0);
      }
      if matches.is_empty() {
        bail!("Undefined reference: {}", id.0);
      }
      Ok(matches[0].id.clone())
    })?;
    let hash = hash_resolved_terms(&body);
    resolved.push(ResolvedFunctionRecord {
      id: func.id.clone(),
      file_id: func.file_id.clone(),
      body,
      content_hash: hash,
      generation: Generation::NewOnly,
    });
  }
  Ok(resolved)
}

fn resolve_tests(
  tests: &[TestRecord],
  all_functions: &[FunctionRecord],
) -> AnyhowResult<Vec<ResolvedTestRecord>> {
  let mut resolved = Vec::with_capacity(tests.len());
  for test in tests {
    let body = resolve_body(&test.body, |id| {
      let matches: Vec<_> =
        all_functions.iter().filter(|f| f.name == id.0).collect();
      if matches.len() > 1 {
        bail!("Function redefinition: {}", id.0);
      }
      if matches.is_empty() {
        bail!("Undefined reference: {}", id.0);
      }
      Ok(matches[0].id.clone())
    })?;
    let hash = hash_resolved_terms(&body);
    resolved.push(ResolvedTestRecord {
      id: test.id.clone(),
      file_id: test.file_id.clone(),
      body,
      content_hash: hash,
      generation: Generation::NewOnly,
    });
  }
  Ok(resolved)
}

fn resolve_statements(
  statements: &[StatementRecord],
  all_functions: &[FunctionRecord],
) -> AnyhowResult<Vec<ResolvedStatementRecord>> {
  let mut resolved = Vec::with_capacity(statements.len());

  for stmt in statements {
    let body = resolve_body(&stmt.body, |id| {
      let matches: Vec<_> = all_functions
        .iter()
        .filter(|f| {
          if f.name != id.0 {
            return false;
          }
          if f.file_id == stmt.file_id {
            f.index <= stmt.index
          } else {
            true
          }
        })
        .collect();

      if matches.len() > 1 {
        bail!("Function redefinition: {}", id.0);
      }
      if matches.is_empty() {
        bail!("Undefined reference: {}", id.0);
      }
      Ok(matches[0].id.clone())
    })?;
    let hash = hash_resolved_terms(&body);
    resolved.push(ResolvedStatementRecord {
      id: StatementId(format!("{}:{}", stmt.file_id.0, stmt.index)),
      file_id: stmt.file_id.clone(),
      body,
      content_hash: hash,
      generation: stmt.generation,
      index: stmt.index,
    });
  }
  Ok(resolved)
}

fn resolve_body<F>(
  terms: &[Term],
  resolve_name: F,
) -> AnyhowResult<Vec<ResolvedTerm>>
where
  F: Fn(&FunctionId) -> AnyhowResult<FunctionId>,
{
  let mut resolved = Vec::with_capacity(terms.len());
  for term in terms {
    match term {
      Term::Literal(v) => resolved.push(ResolvedTerm::Literal(v.clone())),
      Term::Word(w) => {
        if let Some(builtin) = parse_builtin(w) {
          resolved
            .push(ResolvedTerm::Word(ResolvedWord::Builtin(builtin)));
        } else {
          let func_id = FunctionId(w.clone());
          let id = resolve_name(&func_id)?;
          resolved.push(ResolvedTerm::Word(ResolvedWord::Function(id)));
        }
      }
    }
  }
  Ok(resolved)
}

#[cfg(test)]
#[path = "resolve_test.rs"]
mod resolve_test;
