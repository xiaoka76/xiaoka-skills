---
alwaysApply: true
---
# Python 编码规范（类型标注与代码风格）
1. 优先使用 `|` 运算符表示联合类型，替代 `typing.Union`、`typing.Optional`
2. 可选值（可能为None的类型）直接用 `类型 | None` 表示
3. 直接使用Python内置集合类型作为泛型标注，无需从`typing`模块导入别名
4. 所有集合相关抽象基类统一从`collections.abc`模块导入，禁止从`typing`模块导入同名类型：
    `Collection`, `Sequence`, `Mapping`, `Iterable`, `Iterator`, `Callable`, `Set`, `AsyncIterable`
5. 无返回值的函数/方法必须明确标注返回类型为 `-> None`，禁止省略
6. 可变参数标注：`*args: str`、`**kwargs: int`
7. 尽量避免使用`typing.Any`，除非完全无法确定类型
8. 类属性、实例属性都需要标注类型，避免使用`typing.Any`
9. 所有公共函数、类方法必须包含完整的功能描述与参数、返回值注释，私有方法（下划线开头）逻辑复杂时也需要添加注释。
# 示例：完整符合规范的代码
```python
from collections.abc import Sequence

def calculate_average(numbers: Sequence[int | float]) -> float | None:
    """
    计算数字序列的平均值
    :param numbers: 包含整数或浮点数的序列
    :return: 平均值，若序列为空则返回None
    """
    if not numbers:
        return None
    return sum(numbers) / len(numbers)
```
