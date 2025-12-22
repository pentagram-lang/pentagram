use anyhow::Error as AnyhowError;
use anyhow::Result as AnyhowResult;
use boot_db::Diagnostic;
use boot_db::FileId;
use boot_db::FunctionId;
use boot_db::FunctionRecord;
use boot_db::Generation;
use boot_db::StatementId;
use boot_db::StatementRecord;
use boot_db::Term;
use boot_db::TestId;
use boot_db::TestRecord;
use boot_db::Value;
use boot_db::hash_terms;
use std::collections::HashSet;
use winnow::Parser;
use winnow::ascii::digit1;
use winnow::ascii::multispace1;
use winnow::combinator::alt;
use winnow::combinator::cut_err;
use winnow::combinator::delimited;
use winnow::combinator::eof;
use winnow::combinator::preceded;
use winnow::combinator::repeat;
use winnow::combinator::terminated;
use winnow::error::ContextError;
use winnow::error::ErrMode;
use winnow::error::StrContext;
use winnow::token::take_till;
use winnow::token::take_while;

type WinnowResult<O> = Result<O, ErrMode<ContextError>>;

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

enum TopLevelItem {
  Def { name: String, body: Vec<Term> },
  Test { body: Vec<Term> },
  Expr(Term),
}

pub fn parse_source(
  path: &str,
  input: &str,
) -> AnyhowResult<ParsedModule> {
  let items: Vec<TopLevelItem> = program.parse(input).map_err(|e| {
    AnyhowError::new(Diagnostic {
      full_source: e.input().to_string(),
      error_offset: e.offset(),
      error_message: e.inner().to_string(),
    })
  })?;

  Ok(shred_items(path, items))
}

pub fn parse_repl_module(
  path: &str,
  old_functions: Vec<FunctionRecord>,
  old_tests: Vec<TestRecord>,
  new_input: &str,
) -> AnyhowResult<ParsedModule> {
  let new_items: Vec<TopLevelItem> =
    program.parse(new_input).map_err(|e| {
      AnyhowError::new(Diagnostic {
        full_source: e.input().to_string(),
        error_offset: e.offset(),
        error_message: e.inner().to_string(),
      })
    })?;

  let new_def_names: HashSet<String> = new_items
    .iter()
    .filter_map(|item| {
      if let TopLevelItem::Def { name, .. } = item {
        Some(name.clone())
      } else {
        None
      }
    })
    .collect();

  let mut items = Vec::new();

  for func in old_functions {
    if !new_def_names.contains(&func.name) {
      items.push(TopLevelItem::Def {
        name: func.name,
        body: func.body,
      });
    }
  }

  for test in old_tests {
    items.push(TopLevelItem::Test { body: test.body });
  }

  items.extend(new_items);

  Ok(shred_items(path, items))
}

fn shred_items(path: &str, items: Vec<TopLevelItem>) -> ParsedModule {
  let mut functions = Vec::new();
  let mut tests = Vec::new();
  let mut statements = Vec::new();
  let file_id = FileId(path.to_string());
  let mut current_index: u32 = 0;

  for (parse_idx, item) in items.into_iter().enumerate() {
    match item {
      TopLevelItem::Def { name, body } => {
        let hash = hash_terms(&body);
        functions.push(FunctionRecord {
          id: FunctionId(name.clone()),
          name,
          file_id: file_id.clone(),
          body,
          content_hash: hash,
          generation: Generation::NewOnly,
          index: current_index,
        });
      }
      TopLevelItem::Test { body } => {
        let hash = hash_terms(&body);
        let id = format!("{path}.{parse_idx}");
        tests.push(TestRecord {
          id: TestId(id),
          file_id: file_id.clone(),
          body,
          content_hash: hash,
          generation: Generation::NewOnly,
          index: current_index,
        });
      }
      TopLevelItem::Expr(t) => {
        let body = vec![t];
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

fn program(input: &mut &str) -> WinnowResult<Vec<TopLevelItem>> {
  (
    preceded(
      ws,
      repeat::<_, _, Vec<TopLevelItem>, _, _>(
        0 ..,
        alt((def_item, test_item, expr_item)),
      ),
    ),
    ws,
    eof.context(StrContext::Label("end of input")),
  )
    .map(|(items, (), _)| items)
    .parse_next(input)
}

fn ws(input: &mut &str) -> WinnowResult<()> {
  repeat::<_, _, (), _, _>(0 .., alt((multispace1.void(), comment.void())))
    .void()
    .parse_next(input)
}

fn comment(input: &mut &str) -> WinnowResult<()> {
  ("--", take_till(0 .., |c| c == '\n' || c == '\r'))
    .void()
    .parse_next(input)
}

fn def_item(input: &mut &str) -> WinnowResult<TopLevelItem> {
  terminated(
    preceded(
      "def",
      cut_err((
        ws,
        word_str,
        ws,
        "fn",
        ws,
        repeat::<_, _, Vec<Term>, _, _>(0 .., body_term),
        "end-fn",
      ))
      .map(
        |((), name, (), _, (), body, _): (
          (),
          &str,
          (),
          &str,
          (),
          Vec<Term>,
          &str,
        )| TopLevelItem::Def {
          name: name.to_string(),
          body,
        },
      ),
    ),
    (ws, repeat::<_, _, (), _, _>(0 .., ','), ws),
  )
  .context(StrContext::Label("function definition"))
  .parse_next(input)
}

fn test_item(input: &mut &str) -> WinnowResult<TopLevelItem> {
  terminated(
    preceded(
      "test",
      cut_err((
        ws,
        repeat::<_, _, Vec<Term>, _, _>(0 .., body_term),
        "end-test",
      ))
      .map(|((), body, _)| TopLevelItem::Test { body }),
    ),
    (ws, repeat::<_, _, (), _, _>(0 .., ','), ws),
  )
  .context(StrContext::Label("test block"))
  .parse_next(input)
}

fn expr_item(input: &mut &str) -> WinnowResult<TopLevelItem> {
  body_term.map(TopLevelItem::Expr).parse_next(input)
}

fn body_term(input: &mut &str) -> WinnowResult<Term> {
  terminated(
    alt((literal_term, word_term)),
    (ws, repeat::<_, _, (), _, _>(0 .., ','), ws),
  )
  .parse_next(input)
}

fn literal_term(input: &mut &str) -> WinnowResult<Term> {
  alt((
    integer.map(|i| Term::Literal(Value::Integer(i))),
    string.map(|s| Term::Literal(Value::String(s))),
  ))
  .parse_next(input)
}

fn integer(input: &mut &str) -> WinnowResult<i64> {
  digit1.parse_to().parse_next(input)
}

fn string(input: &mut &str) -> WinnowResult<String> {
  delimited('\'', take_till(0 .., '\''), '\'')
    .map(|s: &str| s.to_string())
    .parse_next(input)
}

fn word_term(input: &mut &str) -> WinnowResult<Term> {
  word_str
    .verify(|s: &&str| !is_reserved(s))
    .map(|s: &str| Term::Word(s.to_string()))
    .parse_next(input)
}

fn word_str<'a>(input: &mut &'a str) -> WinnowResult<&'a str> {
  take_while(1 .., |c: char| {
    !c.is_whitespace() && c != ',' && c != '\'' && c != '[' && c != ']'
  })
  .parse_next(input)
}

fn is_reserved(s: &str) -> bool {
  matches!(s, "def" | "fn" | "end-fn" | "test" | "end-test")
}

#[cfg(test)]
#[path = "parse_test.rs"]
mod parse_test;
