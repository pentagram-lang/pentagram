use crate::file::FileId;
use crate::generation::Generation;
use crate::hash::ContentHash;
use crate::statement::StatementId;
use crate::term::ResolvedTerm;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedStatementRecord {
  pub id: StatementId,
  pub file_id: FileId,
  pub body: Vec<ResolvedTerm>,
  pub content_hash: ContentHash,
  pub generation: Generation,
  pub index: u32,
}
