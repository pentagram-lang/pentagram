use std::fmt;

#[derive(Clone, PartialEq, Eq, Hash)]
pub enum Value {
  Integer(i64),
  String(String),
  Boolean(bool),
}

impl fmt::Debug for Value {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    match self {
      Self::Integer(i) => write!(f, "{i}"),
      Self::String(s) => write!(f, "'{s}'"),
      Self::Boolean(b) => write!(f, "{b}"),
    }
  }
}

impl fmt::Display for Value {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    match self {
      Self::Integer(i) => write!(f, "{i}"),
      Self::String(s) => write!(f, "{s}"),
      Self::Boolean(b) => write!(f, "{b}"),
    }
  }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Term {
  Literal(Value),
  Word(String),
  Def { name: String, body: Vec<Term> },
  Test { body: Vec<Term> },
}
