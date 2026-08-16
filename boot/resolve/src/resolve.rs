use boot_db::Diagnostic;
use boot_db::DiagnosticResult;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::ResolvedFunctionRecord;
use boot_db::ResolvedStatementRecord;
use boot_db::ResolvedTerm;
use boot_db::ResolvedTestRecord;
use boot_db::ResolvedWord;
use boot_db::SpannedResolvedTerm;
use boot_db::SpannedTerm;
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
) -> DiagnosticResult<ResolveOutput> {
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
) -> DiagnosticResult<Vec<ResolvedFunctionRecord>> {
  let mut resolved = Vec::with_capacity(functions.len());
  for func in functions {
    let body = resolve_body(&func.file_id, &func.body, |id| {
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
        return Err(format!("Function redefinition: {}", id.0));
      }
      if matches.is_empty() {
        return Err(format!("Undefined reference: {}", id.0));
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
) -> DiagnosticResult<Vec<ResolvedTestRecord>> {
  let mut resolved = Vec::with_capacity(tests.len());
  for test in tests {
    let body = resolve_body(&test.file_id, &test.body, |id| {
      let matches: Vec<_> =
        all_functions.iter().filter(|f| f.name == id.0).collect();
      if matches.len() > 1 {
        return Err(format!("Function redefinition: {}", id.0));
      }
      if matches.is_empty() {
        return Err(format!("Undefined reference: {}", id.0));
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
) -> DiagnosticResult<Vec<ResolvedStatementRecord>> {
  let mut resolved = Vec::with_capacity(statements.len());

  for stmt in statements {
    let body = resolve_body(&stmt.file_id, &stmt.body, |id| {
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
        return Err(format!("Function redefinition: {}", id.0));
      }
      if matches.is_empty() {
        return Err(format!("Undefined reference: {}", id.0));
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
  file_id: &FileId,
  terms: &[SpannedTerm],
  resolve_name: F,
) -> DiagnosticResult<Vec<SpannedResolvedTerm>>
where
  F: Fn(&FunctionId) -> Result<FunctionId, String>,
{
  let mut resolved = Vec::with_capacity(terms.len());
  for term in terms {
    let span = term.span;
    match &term.value {
      Term::Literal(v) => {
        resolved.push(SpannedResolvedTerm::new(
          ResolvedTerm::Literal(v.clone()),
          span,
        ));
      }
      Term::Word(w) => {
        if let Some(builtin) = parse_builtin(w) {
          resolved.push(SpannedResolvedTerm::new(
            ResolvedTerm::Word(ResolvedWord::Builtin(builtin)),
            span,
          ));
        } else {
          let func_id = FunctionId(w.clone());
          let id = resolve_name(&func_id).map_err(|error_message| {
            Diagnostic {
              file_id: file_id.clone(),
              span,
              error_message,
            }
          })?;
          resolved.push(SpannedResolvedTerm::new(
            ResolvedTerm::Word(ResolvedWord::Function(id)),
            span,
          ));
        }
      }
    }
  }
  Ok(resolved)
}

#[cfg(test)]
#[path = "resolve_test.rs"]
mod resolve_test;
