from marshmallow import Schema, fields, validate


class RaceCreateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.Str(load_default="", validate=validate.Length(max=200))
    status = fields.Str(load_only=True)
    description = fields.Str(load_default="", validate=validate.Length(max=5000))
    start_time = fields.Str(load_default=None, allow_none=True)
    end_time = fields.Str(load_default=None, allow_none=True)
    rules = fields.Str(load_default="")
    schedule = fields.Str(load_default="")
    theme = fields.Str(load_default="")
    organizer_name = fields.Str(load_default="")
    ca_policy = fields.Str(
        load_default="rider_choice",
        validate=validate.OneOf(["organizer_specified", "rider_choice"]),
    )
    ca_policy_config = fields.Str(load_default="{}")
    submission_deadline = fields.Str(load_default=None, allow_none=True)
    judging_deadline = fields.Str(load_default=None, allow_none=True)
    judging_mode = fields.Str(
        load_default="blind", validate=validate.OneOf(["blind", "open"])
    )
    judging_tiebreaker = fields.Str(
        load_default="avg",
        validate=validate.OneOf(["avg", "median", "trimmed_mean"]),
    )


class RaceEditSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=200))
    description = fields.Str(validate=validate.Length(max=5000))
    start_time = fields.Str(allow_none=True)
    end_time = fields.Str(allow_none=True)
    rules = fields.Str()
    schedule = fields.Str()
    theme = fields.Str()
    organizer_name = fields.Str()
    ca_policy = fields.Str(
        validate=validate.OneOf(["organizer_specified", "rider_choice"])
    )
    ca_policy_config = fields.Str()
    submission_deadline = fields.Str(allow_none=True)
    judging_deadline = fields.Str(allow_none=True)
    judging_mode = fields.Str(validate=validate.OneOf(["blind", "open"]))
    judging_tiebreaker = fields.Str(
        validate=validate.OneOf(["avg", "median", "trimmed_mean"])
    )


class WorkCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    description = fields.Str(load_default="", validate=validate.Length(max=5000))
    repo_url = fields.Str(load_default="", validate=validate.Length(max=500))
    demo_url = fields.Str(load_default="", validate=validate.Length(max=500))
    video_url = fields.Str(load_default="", validate=validate.Length(max=500))
    cover_image_url = fields.Str(load_default="", validate=validate.Length(max=500))
    screenshot_urls = fields.Str(load_default="[]")
    readme_body = fields.Str(load_default="")
    visibility = fields.Str(
        load_default="private", validate=validate.OneOf(["private", "public"])
    )


class AnnouncementCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    body = fields.Str(load_default="", validate=validate.Length(max=10000))


class AnnouncementEditSchema(Schema):
    title = fields.Str(validate=validate.Length(min=1, max=200))
    body = fields.Str(validate=validate.Length(max=10000))


# =============================================
# 人员 C：评审系统
# =============================================

class JudgeAssignmentBatchSchema(Schema):
    """批量分配评委的请求体"""
    assignments = fields.List(
        fields.Dict(keys=fields.Str(), values=fields.Int()),
        required=True,
        validate=validate.Length(min=1),
    )


class JudgmentSubmitSchema(Schema):
    """提交/修改四维评分"""
    technical_score = fields.Int(
        required=True, validate=validate.Range(min=1, max=10)
    )
    innovation_score = fields.Int(
        required=True, validate=validate.Range(min=1, max=10)
    )
    presentation_score = fields.Int(
        required=True, validate=validate.Range(min=1, max=10)
    )
    completeness_score = fields.Int(
        required=True, validate=validate.Range(min=1, max=10)
    )
    comment = fields.Str(load_default="", validate=validate.Length(max=5000))


# =============================================
# 人员 C：奖项榜单
# =============================================

class AwardCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    position = fields.Int(required=True, validate=validate.Range(min=1))
    work_id = fields.Int(load_default=None, allow_none=True)
    registration_id = fields.Int(load_default=None, allow_none=True)
    description = fields.Str(load_default="", validate=validate.Length(max=1000))


class AwardEditSchema(Schema):
    title = fields.Str(validate=validate.Length(min=1, max=200))
    position = fields.Int(validate=validate.Range(min=1))
    work_id = fields.Int(allow_none=True)
    registration_id = fields.Int(allow_none=True)
    description = fields.Str(validate=validate.Length(max=1000))
