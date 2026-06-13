import pytest

from cancan_microstack.public.const.workflow_consts import IMMUTABLE_END_NODE_IDS
from cancan_microstack.public.const.workflow_consts import IMMUTABLE_START_NODE_IDS


def test_immutable_node_ids_are_frozenset_and_contains_expected_values():
    assert isinstance(IMMUTABLE_START_NODE_IDS, frozenset)
    assert isinstance(IMMUTABLE_END_NODE_IDS, frozenset)

    assert "start" in IMMUTABLE_START_NODE_IDS
    assert "start_node" in IMMUTABLE_START_NODE_IDS
    assert "end" in IMMUTABLE_END_NODE_IDS
    assert "end_node" in IMMUTABLE_END_NODE_IDS

    # frozenset should be immutable
    assert not hasattr(IMMUTABLE_START_NODE_IDS, "add")
    assert not hasattr(IMMUTABLE_END_NODE_IDS, "add")

    with pytest.raises(AttributeError):
        # pyright: ignore[reportAttributeAccessIssue]
        IMMUTABLE_START_NODE_IDS.add("x")
