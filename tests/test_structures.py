"""Unit tests for nested structure utilities."""

from tools.structures import get_value, iter_string_nodes, path_to_key, set_value

# Expected counts for test assertions
EXPECTED_FLAT_KEYS = 2
EXPECTED_ARRAY_ITEMS = 3
EXPECTED_MIXED_ITEMS = 4


class TestIterStringNodes:
    """Test cases for iter_string_nodes function."""

    def test_flat_dict(self):
        """Test iteration over flat dictionary."""
        data = {"a": "value1", "b": "value2"}
        nodes = list(iter_string_nodes(data))
        assert len(nodes) == EXPECTED_FLAT_KEYS
        keys = {path_to_key(path) for path, _ in nodes}
        assert keys == {"a", "b"}

    def test_nested_dict(self):
        """Test iteration over nested dictionary."""
        data = {"level1": {"level2": {"level3": "deep_value"}}}
        nodes = list(iter_string_nodes(data))
        assert len(nodes) == 1
        path, value = nodes[0]
        assert path_to_key(path) == "level1.level2.level3"
        assert value == "deep_value"

    def test_dict_with_array(self):
        """Test iteration over dict containing arrays."""
        data = {"items": ["first", "second", "third"]}
        nodes = list(iter_string_nodes(data))
        assert len(nodes) == EXPECTED_ARRAY_ITEMS
        keys = {path_to_key(path) for path, _ in nodes}
        assert keys == {"items[0]", "items[1]", "items[2]"}

    def test_mixed_structure(self):
        """Test iteration over mixed nested structure."""
        data = {
            "simple": "value",
            "nested": {"key": "nested_value"},
            "array": ["item1", "item2"],
        }
        nodes = list(iter_string_nodes(data))
        assert len(nodes) == EXPECTED_MIXED_ITEMS
        values = {value for _, value in nodes}
        assert values == {"value", "nested_value", "item1", "item2"}

    def test_skip_non_strings(self):
        """Test that non-string values are skipped."""
        data = {"string": "text", "number": 123, "bool": True, "null": None}
        nodes = list(iter_string_nodes(data))
        assert len(nodes) == 1
        assert nodes[0][1] == "text"


class TestGetValue:
    """Test cases for get_value function."""

    def test_get_simple_key(self):
        """Test getting value with simple key."""
        data = {"a": "value"}
        assert get_value(data, ("a",)) == "value"

    def test_get_nested_key(self):
        """Test getting value with nested keys."""
        data = {"level1": {"level2": "value"}}
        assert get_value(data, ("level1", "level2")) == "value"

    def test_get_array_index(self):
        """Test getting value from array."""
        data = {"items": ["first", "second"]}
        assert get_value(data, ("items", 0)) == "first"
        assert get_value(data, ("items", 1)) == "second"

    def test_get_missing_key(self):
        """Test getting missing key returns None."""
        data = {"a": "value"}
        assert get_value(data, ("b",)) is None

    def test_get_out_of_bounds_index(self):
        """Test getting out of bounds index returns None."""
        data = {"items": ["first"]}
        assert get_value(data, ("items", 10)) is None

    def test_get_empty_path(self):
        """Test getting value with empty path."""
        data = {"a": "value"}
        assert get_value(data, ()) == data


class TestSetValue:
    """Test cases for set_value function."""

    def test_set_simple_key(self):
        """Test setting value with simple key."""
        data = {"a": "old"}
        set_value(data, ("a",), "new")
        assert data["a"] == "new"

    def test_set_nested_key(self):
        """Test setting value with nested keys."""
        data = {"level1": {"level2": "old"}}
        set_value(data, ("level1", "level2"), "new")
        assert data["level1"]["level2"] == "new"

    def test_set_array_index(self):
        """Test setting value in array."""
        data = {"items": ["first", "second"]}
        set_value(data, ("items", 0), "updated")
        assert data["items"][0] == "updated"

    def test_set_mixed_path(self):
        """Test setting value with mixed dict/array path."""
        data = {"nested": {"items": ["a", "b"]}}
        set_value(data, ("nested", "items", 1), "updated")
        assert data["nested"]["items"][1] == "updated"


class TestPathToKey:
    """Test cases for path_to_key function."""

    def test_simple_path(self):
        """Test conversion of simple path."""
        assert path_to_key(("a",)) == "a"
        assert path_to_key(("nested", "key")) == "nested.key"

    def test_path_with_array_index(self):
        """Test conversion of path with array index."""
        assert path_to_key(("items", 0)) == "items[0]"
        assert path_to_key(("items", 5)) == "items[5]"

    def test_mixed_path(self):
        """Test conversion of mixed path."""
        assert path_to_key(("a", "b", 0, "c")) == "a.b[0].c"

    def test_empty_path(self):
        """Test conversion of empty path."""
        assert path_to_key(()) == ""

    def test_multiple_array_indices(self):
        """Test path with multiple consecutive array indices."""
        assert path_to_key(("matrix", 0, 1)) == "matrix[0][1]"
