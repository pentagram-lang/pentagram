use blake3::Hasher;
use std::cmp::max;
use std::cmp::min;
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Span {
  pub start: usize,
  pub end: usize,
}

impl Span {
  pub fn len(&self) -> usize {
    self.end - self.start
  }

  pub fn is_empty(&self) -> bool {
    self.start == self.end
  }

  #[must_use]
  pub fn merge(self, other: Span) -> Span {
    Span {
      start: min(self.start, other.start),
      end: max(self.end, other.end),
    }
  }
}

pub fn update_span_hash(span: &Span, hasher: &mut Hasher) {
  hasher.update(&span.start.to_le_bytes());
  hasher.update(&span.end.to_le_bytes());
}

impl fmt::Display for Span {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    write!(f, "{}..{}", self.start, self.end)
  }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Spanned<T> {
  pub value: T,
  pub span: Span,
}

impl<T> Spanned<T> {
  #[must_use]
  pub fn new(value: T, span: Span) -> Self {
    Self { value, span }
  }

  #[must_use]
  pub fn map<U, F>(self, f: F) -> Spanned<U>
  where
    F: FnOnce(T) -> U,
  {
    Spanned {
      value: f(self.value),
      span: self.span,
    }
  }
}
