import copy

import pytest

from agent_lab.domain.list_comparison import ComparisonInputError, compare_lists


@pytest.mark.parametrize(
    ("source", "baseline", "expected"),
    [
        (
            ["A", "B", "B"],
            ["B", "C"],
            {"same": ["B"], "source_only": ["A"], "baseline_only": ["C"]},
        ),
        ([], [], {"same": [], "source_only": [], "baseline_only": []}),
        (["Z", "A"], [], {"same": [], "source_only": ["A", "Z"], "baseline_only": []}),
        ([], ["B", "A"], {"same": [], "source_only": [], "baseline_only": ["A", "B"]}),
        (
            ["猫", "犬", "猫"],
            ["犬", "鳥"],
            {"same": ["犬"], "source_only": ["猫"], "baseline_only": ["鳥"]},
        ),
        (
            ["A", "a", " A", "A "],
            ["A"],
            {"same": ["A"], "source_only": [" A", "A ", "a"], "baseline_only": []},
        ),
        (
            ["é", " "],
            ["e\u0301"],
            {"same": [], "source_only": [" ", "é"], "baseline_only": ["e\u0301"]},
        ),
    ],
)
def test_comparison_contract(source, baseline, expected):
    before = copy.deepcopy((source, baseline))
    assert compare_lists(source, baseline) == expected
    assert (source, baseline) == before


@pytest.mark.parametrize("field", ["source", "baseline"])
@pytest.mark.parametrize(
    "invalid",
    [
        None,
        "A",
        1,
        True,
        {},
        ("A",),
        [1],
        [True],
        [None],
        [[]],
        [""],
        ["x" * 257],
        ["A"] * 1001,
    ],
)
def test_strict_validation(field, invalid):
    arguments = {"source": [], "baseline": []}
    arguments[field] = invalid
    with pytest.raises(ComparisonInputError):
        compare_lists(**arguments)


def test_inclusive_limits():
    value = "猫" * 256
    assert compare_lists([value] * 1000, [value] * 1000) == {
        "same": [value],
        "source_only": [],
        "baseline_only": [],
    }
