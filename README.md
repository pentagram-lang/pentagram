# Pentagram <img width="30" height="30" src="art/favicon.svg?raw=true"/>

## About

Pentagram is a programming language for **ergonomics**, **determinism**, and **efficiency** currently in the design & prototyping phase.

```
-- Entry point for writing an ELF binary
main >>
  program-data =
    [] arr
    generate-elf-header cat
    generate-code cat
    generate-data cat

  cout program-data write
```

## License

This project is released under the MIT License (see [LICENSE.md](LICENSE.md) for details).
