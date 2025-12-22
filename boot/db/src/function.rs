use crate::file::FileId;
use crate::generation::Generation;
use crate::hash::ContentHash;
use crate::term::Term;
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct FunctionId(pub String);

impl fmt::Display for FunctionId {
  fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
    write!(f, "{}", self.0)
  }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FunctionRecord {
  pub id: FunctionId,
  pub name: String,
  pub file_id: FileId,
  pub body: Vec<Term>,
  pub content_hash: ContentHash,
  pub generation: Generation,
  pub index: u32,
}
