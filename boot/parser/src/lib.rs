use boot_types::Term;
use boot_types::Value;
use winnow::Result as PResult;
use winnow::ascii::digit1;
use winnow::ascii::multispace1;
use winnow::combinator::alt;
use winnow::combinator::delimited;
use winnow::combinator::preceded;
use winnow::combinator::repeat;
use winnow::combinator::terminated;
use winnow::prelude::*;
use winnow::token::take_till;
use winnow::token::take_until;
use winnow::token::take_while;

pub fn parse(input: &str) -> Result<Vec<Term>, String> {
  program.parse(input).map_err(|e| e.to_string())
}

fn program(input: &mut &str) -> PResult<Vec<Term>> {
  terminated(preceded(ws, repeat(0 .., term)), ws).parse_next(input)
}

fn ws(input: &mut &str) -> PResult<()> {
  repeat::<_, _, (), _, _>(0 .., alt((multispace1.void(), comment.void())))
    .void()
    .parse_next(input)
}

fn comment(input: &mut &str) -> PResult<()> {
  ("--", take_until(0 .., "--"), "--")
    .void()
    .parse_next(input)
}

fn term(input: &mut &str) -> PResult<Term> {
  terminated(
    alt((def_term, test_term, literal_term, word_term)),
    (ws, repeat::<_, _, (), _, _>(0 .., ','), ws), // Consume trailing comma if present, plus whitespace
  )
  .parse_next(input)
}

fn def_term(input: &mut &str) -> PResult<Term> {
  (
    "def",
    ws,
    word_str,
    ws,
    "fn",
    ws,
    repeat(0 .., term),
    "end-fn",
  )
    .map(
      |(_, _, name, _, _, _, body, _): (
        _,
        _,
        &str,
        _,
        _,
        _,
        Vec<Term>,
        _,
      )| Term::Def {
        name: name.to_string(),
        body,
      },
    )
    .parse_next(input)
}

fn test_term(input: &mut &str) -> PResult<Term> {
  ("test", ws, repeat(0 .., term), "end-test")
    .map(|(_, _, body, _): (_, _, Vec<Term>, _)| Term::Test { body })
    .parse_next(input)
}

fn literal_term(input: &mut &str) -> PResult<Term> {
  alt((
    integer.map(|i| Term::Literal(Value::Integer(i))),
    string.map(|s| Term::Literal(Value::String(s))),
  ))
  .parse_next(input)
}

fn integer(input: &mut &str) -> PResult<i64> {
  digit1.parse_to().parse_next(input)
}

fn string(input: &mut &str) -> PResult<String> {
  delimited('\'', take_till(0 .., '\''), '\'')
    .map(|s: &str| s.to_string())
    .parse_next(input)
}

fn word_term(input: &mut &str) -> PResult<Term> {
  word_str
    .verify(|s: &&str| !is_reserved(s))
    .map(|s: &str| Term::Word(s.to_string()))
    .parse_next(input)
}

fn word_str<'a>(input: &mut &'a str) -> PResult<&'a str> {
  take_while(1 .., |c: char| {
    !c.is_whitespace() && c != ',' && c != '\'' && c != '[' && c != ']'
  })
  .parse_next(input)
}

fn is_reserved(s: &str) -> bool {
  matches!(s, "def" | "fn" | "end-fn" | "test" | "end-test")
}

#[cfg(test)]
mod tests;
