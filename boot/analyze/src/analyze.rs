use anyhow::Result as AnyhowResult;
use blake3::Hasher;
use boot_db::ContentHash;
use boot_db::DependencyFunctionRecord;
use boot_db::DependencyTestRecord;
use boot_db::FunctionId;
use boot_db::Generation;
use boot_db::ResolvedFunctionRecord;
use boot_db::ResolvedTerm;
use boot_db::ResolvedTestRecord;
use boot_db::ResolvedWord;
use boot_db::TestId;
use std::collections::HashMap;
use std::collections::HashSet;

#[derive(Debug)]
pub struct AnalyzeInput<'a> {
  pub resolved_functions: &'a [ResolvedFunctionRecord],
  pub resolved_tests: &'a [ResolvedTestRecord],
}

#[derive(Debug, PartialEq, Eq, Default)]
pub struct AnalyzeOutput {
  pub function_dependencies: Vec<DependencyFunctionRecord>,
  pub test_dependencies: Vec<DependencyTestRecord>,
}

pub fn analyze_dependency_graph(
  input: &AnalyzeInput<'_>,
) -> AnyhowResult<AnalyzeOutput> {
  let (function_deps, test_deps) = extract_direct_deps(input);
  let (transitive_function_hashes, transitive_test_hashes) =
    compute_transitive_hashes(input, &function_deps, &test_deps);

  let mut function_dependencies = Vec::new();
  for func in input.resolved_functions {
    let id = &func.id;
    let hash = *transitive_function_hashes
      .get(id)
      .expect("constraint violation: transitive function hash missing");

    function_dependencies.push(DependencyFunctionRecord {
      id: id.clone(),
      content_hash: hash,
      generation: Generation::NewOnly,
    });
  }

  let mut test_dependencies = Vec::new();
  for test in input.resolved_tests {
    let id = &test.id;
    let hash = *transitive_test_hashes
      .get(id)
      .expect("constraint violation: transitive test hash missing");

    test_dependencies.push(DependencyTestRecord {
      id: id.clone(),
      content_hash: hash,
      generation: Generation::NewOnly,
    });
  }

  Ok(AnalyzeOutput {
    function_dependencies,
    test_dependencies,
  })
}

fn extract_direct_deps(
  input: &AnalyzeInput<'_>,
) -> (
  HashMap<FunctionId, HashSet<FunctionId>>,
  HashMap<TestId, HashSet<FunctionId>>,
) {
  let mut function_deps = HashMap::new();
  let mut test_deps = HashMap::new();

  for func in input.resolved_functions {
    let mut calls = HashSet::new();
    find_calls(&func.body, &mut calls);
    function_deps.insert(func.id.clone(), calls);
  }

  for test in input.resolved_tests {
    let mut calls = HashSet::new();
    find_calls(&test.body, &mut calls);
    test_deps.insert(test.id.clone(), calls);
  }

  (function_deps, test_deps)
}

fn compute_transitive_hashes(
  input: &AnalyzeInput<'_>,
  function_deps: &HashMap<FunctionId, HashSet<FunctionId>>,
  test_deps: &HashMap<TestId, HashSet<FunctionId>>,
) -> (
  HashMap<FunctionId, ContentHash>,
  HashMap<TestId, ContentHash>,
) {
  let mut transitive_function_hashes = HashMap::new();
  let mut visited_functions = HashSet::new();

  let function_hashes: HashMap<FunctionId, ContentHash> = input
    .resolved_functions
    .iter()
    .map(|f| (f.id.clone(), f.content_hash))
    .collect();

  for id in function_deps.keys() {
    compute_function_hash(
      id,
      &function_hashes,
      function_deps,
      &mut transitive_function_hashes,
      &mut visited_functions,
    );
  }

  let mut transitive_test_hashes = HashMap::new();
  let test_hashes: HashMap<TestId, ContentHash> = input
    .resolved_tests
    .iter()
    .map(|t| (t.id.clone(), t.content_hash))
    .collect();

  for id in test_deps.keys() {
    let mut hasher = Hasher::new();
    let content_hash = test_hashes
      .get(id)
      .copied()
      .expect("constraint violation: test hash missing");
    hasher.update(&content_hash.0);

    if let Some(calls) = test_deps.get(id) {
      let mut sorted_calls: Vec<_> = calls.iter().collect();
      sorted_calls.sort();

      for call in sorted_calls {
        let dep_hash = compute_function_hash(
          call,
          &function_hashes,
          function_deps,
          &mut transitive_function_hashes,
          &mut visited_functions,
        );
        hasher.update(&dep_hash.0);
      }
    }
    transitive_test_hashes.insert(id.clone(), hasher.finalize().into());
  }

  (transitive_function_hashes, transitive_test_hashes)
}

fn compute_function_hash(
  id: &FunctionId,
  function_hashes: &HashMap<FunctionId, ContentHash>,
  function_deps: &HashMap<FunctionId, HashSet<FunctionId>>,
  transitive_hashes: &mut HashMap<FunctionId, ContentHash>,
  visited: &mut HashSet<FunctionId>,
) -> ContentHash {
  if let Some(hash) = transitive_hashes.get(id) {
    return *hash;
  }

  if !visited.insert(id.clone()) {
    return *function_hashes
      .get(id)
      .expect("constraint violation: function hash missing");
  }

  let mut hasher = Hasher::new();
  let content_hash = function_hashes
    .get(id)
    .copied()
    .expect("constraint violation: function hash missing");
  hasher.update(&content_hash.0);

  if let Some(calls) = function_deps.get(id) {
    let mut sorted_calls: Vec<_> = calls.iter().collect();
    sorted_calls.sort();

    for call in sorted_calls {
      let dep_hash = compute_function_hash(
        call,
        function_hashes,
        function_deps,
        transitive_hashes,
        visited,
      );
      hasher.update(&dep_hash.0);
    }
  }

  let final_hash = hasher.finalize().into();
  transitive_hashes.insert(id.clone(), final_hash);
  final_hash
}

fn find_calls(terms: &[ResolvedTerm], calls: &mut HashSet<FunctionId>) {
  for term in terms {
    if let ResolvedTerm::Word(ResolvedWord::Function(id)) = term {
      calls.insert(id.clone());
    }
  }
}

#[cfg(test)]
#[path = "analyze_test.rs"]
mod analyze_test;
