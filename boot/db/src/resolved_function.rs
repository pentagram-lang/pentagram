use crate::file::FileId;
use crate::function::FunctionId;
use crate::generation::Generation;
use crate::hash::ContentHash;
use crate::term::ResolvedTerm;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedFunctionRecord {
  pub id: FunctionId,
  pub file_id: FileId,
  pub body: Vec<ResolvedTerm>,
  pub content_hash: ContentHash,
  pub generation: Generation,
}
