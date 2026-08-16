use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::SpannedTerm;
use boot_db::StatementId;
use boot_db::StatementRecord;
use boot_db::TestId;
use boot_db::TestRecord;
use boot_db::hash_terms;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ParsedModule {
  pub functions: Vec<FunctionRecord>,
  pub tests: Vec<TestRecord>,
  pub statements: Vec<StatementRecord>,
}

impl ParsedModule {
  pub fn is_empty(&self) -> bool {
    self.functions.is_empty()
      && self.tests.is_empty()
      && self.statements.is_empty()
  }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ParsedFunction {
  pub(crate) name: String,
  pub(crate) body: Vec<SpannedTerm>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ParsedTest {
  pub(crate) body: Vec<SpannedTerm>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ParsedStatement {
  pub(crate) term: SpannedTerm,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum TopLevelItem {
  Function(ParsedFunction),
  Test(ParsedTest),
  Statement(ParsedStatement),
}

pub(crate) fn shred_items(
  path: &str,
  items: Vec<TopLevelItem>,
) -> ParsedModule {
  let mut functions = Vec::new();
  let mut tests = Vec::new();
  let mut statements = Vec::new();
  let file_id = FileId(path.to_string());
  let mut current_index: u32 = 0;

  for (parse_idx, item) in items.into_iter().enumerate() {
    match item {
      TopLevelItem::Function(f) => {
        let hash = hash_terms(&f.body);
        functions.push(FunctionRecord {
          id: FunctionId(f.name.clone()),
          name: f.name,
          file_id: file_id.clone(),
          body: f.body,
          content_hash: hash,
          generation: Generation::NewOnly,
          index: current_index,
        });
      }
      TopLevelItem::Test(t) => {
        let hash = hash_terms(&t.body);
        let id = format!("{path}.{parse_idx}");
        tests.push(TestRecord {
          id: TestId(id),
          file_id: file_id.clone(),
          body: t.body,
          content_hash: hash,
          generation: Generation::NewOnly,
          index: current_index,
        });
      }
      TopLevelItem::Statement(s) => {
        let body = vec![s.term];
        let hash = hash_terms(&body);
        statements.push(StatementRecord {
          id: StatementId(format!("{path}.{parse_idx}")),
          file_id: file_id.clone(),
          body,
          content_hash: hash,
          generation: Generation::NewOnly,
          index: current_index,
        });
        current_index += 1;
      }
    }
  }

  ParsedModule {
    functions,
    tests,
    statements,
  }
}
