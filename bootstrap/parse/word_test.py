from numpy import int32
from numpy import int64
from numpy import uint8
from numpy import uint16
from numpy import uint32
from numpy import uint64
from parse.line import Line
from parse.line import LineComment
from parse.line import LineWord
from parse.word import WordComment
from parse.word import WordIdentifier
from parse.word import WordLine
from parse.word import WordNumber
from parse.word import parse_word_lines
from test import params


def params_word():
    yield LineWord("abc"), WordIdentifier("abc")
    yield LineComment(" desc"), WordComment(" desc")
    yield LineWord("0"), WordNumber(int32(0))
    yield LineWord("123"), WordNumber(int32(123))
    yield LineWord("456d"), WordNumber(int64(456))
    yield LineWord("0xFF"), WordNumber(uint8(255))
    yield LineWord("0xF01D-AB1E"), WordNumber(
        uint32(0xF01DAB1E)
    )
    yield LineWord("0x0xh"), WordNumber(uint16(0))
    yield LineWord("0xDDxd"), WordNumber(uint64(0xDD))


@params(params_word)
def test_word(term, expected_result):
    lines = [Line(indent=0, terms=[term])]
    result = parse_word_lines(lines)
    assert result[0].terms[0] == expected_result
    assert result == [
        WordLine(indent=0, terms=[expected_result])
    ]
