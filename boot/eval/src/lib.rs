use anyhow::Result;
use anyhow::anyhow;
use boot_types::Term;
use boot_types::Value;
use std::collections::HashMap;
use std::io::Write;

pub struct VM {
  stack: Vec<Value>,
  dictionary: HashMap<String, Vec<Term>>,
  stdout: Box<dyn Write + Send>,
}

impl Default for VM {
  fn default() -> Self {
    Self::new(Box::new(std::io::stdout()))
  }
}

impl VM {
  pub fn new(stdout: Box<dyn Write + Send>) -> Self {
    Self {
      stack: Vec::new(),
      dictionary: HashMap::new(),
      stdout,
    }
  }

  pub fn eval(&mut self, terms: Vec<Term>) -> Result<()> {
    for term in terms {
      self.step(term)?;
    }
    Ok(())
  }

  fn step(&mut self, term: Term) -> Result<()> {
    match term {
      Term::Literal(v) => self.stack.push(v),
      Term::Word(w) => self.exec_word(&w)?,
      Term::Def { name, body } => {
        self.dictionary.insert(name, body);
      }
      Term::Test { body } => {
        self.eval(body)?;
      }
    }
    Ok(())
  }

  fn exec_word(&mut self, word: &str) -> Result<()> {
    if let Some(body) = self.dictionary.get(word).cloned() {
      return self.eval(body);
    }

    match word {
      "+" => {
        let b = self.pop_int()?;
        let a = self.pop_int()?;
        self.stack.push(Value::Integer(a + b));
      }
      "eq" => {
        let b =
          self.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
        let a =
          self.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
        self.stack.push(Value::Boolean(a == b));
      }
      "say" => {
        let v =
          self.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
        writeln!(self.stdout, "{}", v)
          .map_err(|e| anyhow!("IO Error: {}", e))?;
      }
      "assert" => {
        let v =
          self.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
        match v {
          Value::Boolean(true) => {}
          Value::Boolean(false) => {
            return Err(anyhow!("Assertion failed"));
          }
          _ => {
            return Err(anyhow!(
              "Expected boolean for assert, got {:?}",
              v
            ));
          }
        }
      }
      _ => return Err(anyhow!("Unknown word: {}", word)),
    }
    Ok(())
  }

  fn pop_int(&mut self) -> Result<i64> {
    let v = self.stack.pop().ok_or_else(|| anyhow!("Stack underflow"))?;
    match v {
      Value::Integer(i) => Ok(i),
      _ => Err(anyhow!("Expected integer, got {:?}", v)),
    }
  }

  pub fn take_stack(&mut self) -> Vec<Value> {
    std::mem::take(&mut self.stack)
  }
}

#[cfg(test)]
mod tests;
