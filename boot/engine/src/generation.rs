use boot_db::Database;
use boot_db::Generation;

pub(crate) fn commit_engine_generation(db: &mut Database) {
  db.files.retain_mut(|f| {
    if f.generation.is_new() {
      f.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.functions.retain_mut(|f| {
    if f.generation.is_new() {
      f.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.resolved_functions.retain_mut(|f| {
    if f.generation.is_new() {
      f.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.tests.retain_mut(|t| {
    if t.generation.is_new() {
      t.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.resolved_tests.retain_mut(|t| {
    if t.generation.is_new() {
      t.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.statements.retain_mut(|s| {
    if s.generation.is_new() {
      s.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.resolved_statements.retain_mut(|s| {
    if s.generation.is_new() {
      s.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.function_dependencies.retain_mut(|d| {
    if d.generation.is_new() {
      d.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.test_dependencies.retain_mut(|d| {
    if d.generation.is_new() {
      d.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.test_results.retain_mut(|r| {
    if r.generation.is_new() {
      r.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });
}

pub(crate) fn rollback_engine_generation(db: &mut Database) {
  db.files.retain_mut(|f| {
    if f.generation.is_old() {
      f.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.functions.retain_mut(|f| {
    if f.generation.is_old() {
      f.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.resolved_functions.retain_mut(|f| {
    if f.generation.is_old() {
      f.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.tests.retain_mut(|t| {
    if t.generation.is_old() {
      t.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.resolved_tests.retain_mut(|t| {
    if t.generation.is_old() {
      t.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.statements.retain_mut(|s| {
    if s.generation.is_old() {
      s.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.resolved_statements.retain_mut(|s| {
    if s.generation.is_old() {
      s.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.function_dependencies.retain_mut(|d| {
    if d.generation.is_old() {
      d.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.test_dependencies.retain_mut(|d| {
    if d.generation.is_old() {
      d.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });

  db.test_results.retain_mut(|r| {
    if r.generation.is_old() {
      r.generation = Generation::OldOnly;
      true
    } else {
      false
    }
  });
}

#[cfg(test)]
#[path = "generation_test.rs"]
mod generation_test;
