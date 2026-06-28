from typing import Any, Dict, List, Optional, Union


# 根据字段值查找列表中的元素
def find_list_item_by_field(items: List[Union[Dict[str, Any], Any]], field: str, value: Any) -> Optional[Union[Dict[str, Any], Any]]:
    for item in items:
        if isinstance(item, dict):
            if item.get(field) == value:
                return item
        else:
            if getattr(item, field, None) == value:
                return item
    return None


# 查找字段值在指定集合中的所有元素
def find_list_item_by_value_in_set(array: List[Dict[str, Any]], field: str, values_set: set) -> List[Dict[str, Any]]:
    return [item for item in array if item.get(field) in values_set]


# ================================ 调用示例 ================================

if __name__ == "__main__":

    data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    print(find_list_item_by_field(data, "id", 2))
    print(find_list_item_by_value_in_set(data, "id", {1, 3}))
