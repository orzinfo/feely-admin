from typing import Any

from pydantic import BaseModel
from tortoise.expressions import Q
from tortoise.models import Model

Total = int


class CRUDBase[ModelType: Model, CreateSchemaType: BaseModel, UpdateSchemaType: BaseModel]:
    def __init__(self, model: type[ModelType]):
        """
        初始化通用 CRUD 基类。

        参数:
        - model: 具体的 TortoiseORM 模型类型，用于执行数据库操作。

        返回:
        - None：仅保存模型类型以供后续方法使用。
        """
        self.model = model

    async def get(self, *args: Q, **kwargs) -> ModelType:
        """
        根据过滤条件获取单个模型实例。

        参数:
        - *args: 可选的 `Q` 表达式列表，用于构建查询条件。
        - **kwargs: 键值形式的过滤条件，如 `id=1`。

        返回:
        - ModelType: 匹配到的模型实例。
        """
        return await self.model.get(*args, **kwargs)

    async def list(
        self,
        page: int | None,
        page_size: int | None,
        search: Q = Q(),
        order: list[str] | None = None,
        fields: list[str] | None = None,
        last_id: int | None = None,
        count_by_pk_field: bool = False,
        prefetch: list[str] | None = None,
    ) -> tuple[Total, list[ModelType]]:
        """
        分页查询模型列表，支持搜索、排序与字段裁剪。

        参数:
        - page: 页码，默认1。
        - page_size: 每页数量，默认10。
        - search: `Q` 查询条件，默认空查询。
        - order: 排序字段列表，例: ["id", "-created_at"]。
        - fields: 仅返回的字段列表，减少载荷。
        - last_id: 若提供则按增量方式拉取大于该ID的数据。
        - count_by_pk_field: 是否按主键去重计数（针对 distinct 复杂场景）。
        - prefetch: 需要预加载的关联字段列表。

        返回:
        - (Total, list[ModelType]): 总数与当前页数据列表。
        """
        order = order or []
        page = page or 1
        page_size = page_size or 10

        query = self.model.filter(search).distinct()
        if prefetch:
            query = query.prefetch_related(*prefetch)

        if last_id:
            query = query.filter(id__gt=last_id)

        if fields:
            query = query.only(*fields)

        if count_by_pk_field:
            # 优化：使用数据库层面的去重计数，避免全量加载到内存
            total = await query.count()
        else:
            total = await query.count()

        if last_id:
            result = await query.order_by(*order).limit(page_size)
        else:
            result = await query.offset((page - 1) * page_size).limit(page_size).order_by(*order)

        return Total(total), result

    async def create(self, obj_in: CreateSchemaType, exclude: set[str] | None = None) -> ModelType:
        """
        创建模型实例，支持从 Pydantic 模型或字典构造。

        参数:
        - obj_in: 创建用的输入数据，Pydantic BaseModel 或 dict。
        - exclude: 可选的排除字段集合，在序列化时剔除。

        返回:
        - ModelType: 新创建并持久化的模型实例。
        """
        if isinstance(obj_in, dict):
            obj_dict = obj_in
        else:
            obj_dict = obj_in.model_dump(exclude_unset=True, exclude_none=True, exclude=exclude)
        obj: ModelType = self.model(**obj_dict)
        await obj.save()
        return obj

    async def update(
        self, id: int, obj_in: UpdateSchemaType | dict[str, Any], exclude: set[str] | None = None
    ) -> ModelType:
        """
        更新指定 ID 的模型实例，支持 Pydantic 模型或字典输入。

        参数:
        - id: 需要更新的模型主键ID。
        - obj_in: 更新用的输入数据，Pydantic BaseModel 或 dict。
        - exclude: 可选的排除字段集合，在序列化时剔除。

        返回:
        - ModelType: 更新后的模型实例。
        """
        if isinstance(obj_in, dict):
            obj_dict = obj_in
        else:
            obj_dict = obj_in.model_dump(exclude_unset=True, exclude_none=True, exclude=exclude)
        obj = await self.get(id=id)
        obj = obj.update_from_dict(obj_dict)

        await obj.save()
        return obj

    async def remove(self, id: int) -> None:
        """
        删除指定 ID 的模型实例。

        参数:
        - id: 需要删除的模型主键ID。

        返回:
        - None：删除操作无返回值。
        """
        obj = await self.get(id=id)
        await obj.delete()
