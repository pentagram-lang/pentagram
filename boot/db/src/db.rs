use crate::dependency::DependencyFunctionRecord;
use crate::dependency::DependencyTestRecord;
use crate::file::FileRecord;
use crate::function::FunctionRecord;
use crate::resolved_function::ResolvedFunctionRecord;
use crate::resolved_statement::ResolvedStatementRecord;
use crate::resolved_tst::ResolvedTestRecord;
use crate::statement::StatementRecord;
use crate::token::TokenStreamRecord;
use crate::tst::TestRecord;
use crate::tst_result::TestResultRecord;

#[derive(Debug, PartialEq, Eq, Default)]
pub struct Database {
  pub files: Vec<FileRecord>,
  pub functions: Vec<FunctionRecord>,
  pub resolved_functions: Vec<ResolvedFunctionRecord>,
  pub tests: Vec<TestRecord>,
  pub resolved_tests: Vec<ResolvedTestRecord>,
  pub statements: Vec<StatementRecord>,
  pub resolved_statements: Vec<ResolvedStatementRecord>,
  pub token_streams: Vec<TokenStreamRecord>,
  pub function_dependencies: Vec<DependencyFunctionRecord>,
  pub test_dependencies: Vec<DependencyTestRecord>,
  pub test_results: Vec<TestResultRecord>,
}
