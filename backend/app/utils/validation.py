"""
请求校验框架（人员 A 交付）

基于 marshmallow，提供 @validate(schema) 装饰器。
校验失败返回 400 + 字段级错误信息。
校验通过后 body 存入 g.validated_body。
"""
from functools import wraps

from flask import request, g, jsonify
from marshmallow import Schema, ValidationError as MarshmallowValidationError


def validate(schema: Schema):
    """
    marshmallow 校验装饰器。

    用法:
        from marshmallow import Schema, fields, validate as v

        class WorkCreateSchema(Schema):
            title = fields.Str(required=True, validate=v.Length(min=1, max=200))
            description = fields.Str(missing="")

        @rider_bp.route("...", methods=["POST"])
        @validate(WorkCreateSchema)
        def create_work():
            body = g.validated_body  # 已校验的 dict
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            body = request.get_json(silent=True) or {}
            try:
                validated = schema.load(body)
            except MarshmallowValidationError as exc:
                return (
                    jsonify({
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Request validation failed",
                            "fields": exc.messages,
                            "request_id": getattr(g, "request_id", "unknown"),
                        }
                    }),
                    400,
                )
            g.validated_body = validated
            return f(*args, **kwargs)
        return decorated
    return decorator
