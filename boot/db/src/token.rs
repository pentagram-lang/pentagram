use crate::file::FileId;
use crate::generation::Generation;
use crate::hash::ContentHash;
use crate::span::Spanned;
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Token {
  Keyword(KeywordTokenKind),
  Punctuation(PunctuationTokenKind),
  Literal(LiteralTokenKind),
  Identifier(IdentifierTokenKind),
  Trivia(TriviaTokenKind),
  Unknown(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum KeywordTokenKind {
  Def,
  Fn,
  EndFn,
  Test,
  EndTest,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PunctuationTokenKind {
  Comma,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LiteralTokenKind {
  Integer(i64),
  String(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IdentifierTokenKind {
  Word(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TriviaTokenKind {
  Whitespace,
  Comment,
  InvalidTermination,
}

pub type SpannedToken = Spanned<Token>;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct TokenStreamId(pub String);

impl fmt::Display for TokenStreamId {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    write!(f, "{}", self.0)
  }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TokenStreamRecord {
  pub id: TokenStreamId,
  pub file_id: FileId,
  pub tokens: Vec<SpannedToken>,
  pub content_hash: ContentHash,
  pub generation: Generation,
}
