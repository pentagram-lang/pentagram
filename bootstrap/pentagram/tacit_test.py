from __future__ import annotations

import stat
import subprocess

from main import main_run
from os import chmod
from os import symlink
from os import unlink
from os.path import exists
from os.path import lexists
from pentagram.environment import base_environment
from pentagram.machine import MachineStream
from tempfile import mkdtemp
from textwrap import dedent


def test() -> None:
    make_tmp()
    write_flat_assembly()
    run_flat_nasm()
    interpret_tacit()
    flat_xxd = run_xxd("tmp/flat")
    tacit_xxd = run_xxd("tmp/tacit")
    for flat_line, tacit_line in zip(flat_xxd, tacit_xxd):
        assert tacit_line == flat_line
    assert len(tacit_line) == len(flat_line)
    assert run_tacit() == "Hello, Tacit world!\n"


def write_flat_assembly() -> None:
    text = """
        ; Build with `nasm -f bin hello_flat64.asm -o hello_flat64`
        ; Based on http://www.muppetlabs.com/~breadbox/software/tiny/teensy.html

        BITS 64
                    org     0x08048000
        ehdr:                                        ; Elf64_Ehdr
                    db      0x7F, "ELF", 2, 1, 1, 0  ;   e_ident
            times 8 db      0
                    dw      3                        ;   e_type
                    dw      0x3E                     ;   e_machine
                    dd      1                        ;   e_version
                    dq      _start                   ;   e_entry
                    dq      phdr - $$                ;   e_phoff
                    dq      shdr - $$                ;   e_shoff
                    dd      0                        ;   e_flags
                    dw      ehdrsize                 ;   e_ehsize
                    dw      phdrsize                 ;   e_phentsize
                    dw      2                        ;   e_phnum
                    dw      shdrsize                 ;   e_shentsize
                    dw      4                        ;   e_shnum
                    dw      1                        ;   e_shstrndx
        ehdrsize    equ     $ - ehdr


        phdr:                                        ; Elf64_Phdr
                    dd      1                        ;   p_type
                    dd      5                        ;   p_flags
                    dq      _start - $$              ;   p_offset
                    dq      _start                   ;   p_vaddr
                    dq      _start                   ;   p_paddr
                    dq      prog_size                ;   p_filesz
                    dq      prog_size                ;   p_memsz
                    dq      0x1000                   ;   p_align
        phdrsize    equ     $ - phdr
                    dd      1                        ;   p_type
                    dd      4                        ;   p_flags
                    dq      rodata - $$              ;   p_offset
                    dq      rodata + 0x1000          ;   p_vaddr
                    dq      rodata + 0x1000          ;   p_paddr
                    dq      rodata_size              ;   p_filesz
                    dq      rodata_size              ;   p_memsz
                    dq      0x1000                   ;   p_align


        shdr:                                        ; Elf64_Shdr
                                                     ; undefined
                    dd      0                        ;   sh_name
                    dd      0                        ;   sh_type
                    dq      0                        ;   sh_flags
                    dq      0                        ;   sh_addr
                    dq      0                        ;   sh_offset
                    dq      0                        ;   sh_size
                    dd      0                        ;   sh_link
                    dd      0                        ;   sh_info
                    dq      0                        ;   sh_addralign
                    dq      0                        ;   sh_entsize
        shdrsize    equ     $ - shdr
                                                     ; .shstrtab
                    dd      shstrtab_1               ;   sh_name
                    dd      3                        ;   sh_type
                    dq      0                        ;   sh_flags
                    dq      $$                       ;   sh_addr
                    dq      shstrtab - $$            ;   sh_offset
                    dq      shstrtab_size            ;   sh_size
                    dd      0                        ;   sh_link
                    dd      0                        ;   sh_info
                    dq      0x0001                   ;   sh_addralign
                    dq      0                        ;   sh_entsize
                                                     ; .text
                    dd      shstrtab_2               ;   sh_name
                    dd      1                        ;   sh_type
                    dq      6                        ;   sh_flags
                    dq      _start                   ;   sh_addr
                    dq      _start - $$              ;   sh_offset
                    dq      prog_size                ;   sh_size
                    dd      0                        ;   sh_link
                    dd      0                        ;   sh_info
                    dq      0x1000                   ;   sh_addralign
                    dq      0                        ;   sh_entsize
                                                     ; .rodata
                    dd      shstrtab_3               ;   sh_name
                    dd      1                        ;   sh_type
                    dq      2                        ;   sh_flags
                    dq      rodata + 0x1000          ;   sh_addr
                    dq      rodata - $$              ;   sh_offset
                    dq      rodata_size              ;   sh_size
                    dd      0                        ;   sh_link
                    dd      0                        ;   sh_info
                    dq      0x1000                   ;   sh_addralign
                    dq      0                        ;   sh_entsize

        shstrtab:
                    db      0
        shstrtab_1  equ     $ - shstrtab
                    db      ".shstrtab", 0
        shstrtab_2  equ     $ - shstrtab
                    db      ".text", 0
        shstrtab_3  equ     $ - shstrtab
                    db      ".rodata", 0

        shstrtab_size   equ     $ - shstrtab


        _start:

            mov     rdx,msg_len                         ;message length
            lea     rsi,[rel msg + 0x1000]              ;message to write
            mov     rdi,1                               ;file descriptor (stdout)
            mov     rax,1                               ;system call number (sys_write)
            syscall                                     ;call kernel

            mov     rdi,0                               ;exit code
            mov     rax,60                              ;system call number (sys_exit)
            syscall                                     ;call kernel

        prog_size   equ     $ - _start

        rodata:
        msg         db      'Hello, Tacit world!'
                    db      0x0A
        msg_len     equ     $ - msg
        rodata_size   equ     $ - rodata
    """
    text = dedent(text).lstrip()
    with open("tmp/flat.asm", "w") as flat_assembly_file:
        flat_assembly_file.write(text)


def run_flat_nasm() -> None:
    subprocess.run(
        [
            "nasm",
            "-f",
            "bin",
            "tmp/flat.asm",
            "-o",
            "tmp/flat",
        ]
    ).check_returncode()


def make_tmp() -> None:
    if exists("tmp"):
        return
    if lexists("tmp"):
        unlink("tmp")
    tmp_path = mkdtemp(suffix=".tacit-gen3-python")
    symlink(tmp_path, "tmp", target_is_directory=True)


def interpret_tacit() -> None:
    with open("tmp/tacit", "wb") as tacit_output_file:
        test_environment = base_environment().extend(
            {"cout": MachineStream(tacit_output_file)}
        )
        main_run("../main.tacit", test_environment)


def run_xxd(file_path: str) -> list[str]:
    result = subprocess.run(
        ["xxd", "-u", file_path],
        stdout=subprocess.PIPE,
        text=True,
    )
    result.check_returncode()
    return list(filter(bool, result.stdout.split("\n")))


def run_tacit() -> str:
    chmod("tmp/tacit", stat.S_IRWXU)
    result = subprocess.run(
        ["tmp/tacit"], stdout=subprocess.PIPE, text=True
    )
    result.check_returncode()
    return result.stdout
