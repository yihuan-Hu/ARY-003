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


# =============================================
# 人员 D：CA 连接与会话
# =============================================

class CAConnectionCreateSchema(Schema):
    """登记 CA 接入"""
    ca_type = fields.Str(
        required=True,
        validate=validate.OneOf(["codex", "claude", "other"]),
    )
    provider_name = fields.Str(
        required=True, validate=validate.Length(min=1, max=100)
    )
    api_key = fields.Str(load_default="")
    config_json = fields.Dict(load_default={})


class CAConnectionEditSchema(Schema):
    """更新 CA 配置"""
    provider_name = fields.Str(validate=validate.Length(min=1, max=100))
    api_key = fields.Str()
    config_json = fields.Dict()


class CAWizardStepSchema(Schema):
    """CA 向导每步提交数据"""
    ca_type = fields.Str(
        validate=validate.OneOf(["codex", "claude", "other"]),
    )
    provider_name = fields.Str(validate=validate.Length(min=1, max=100))
    api_key = fields.Str()
    config_json = fields.Dict()
    repo_url = fields.Str()


class CASessionIngestSchema(Schema):
    """CA Session 数据接入"""
    overall_progress = fields.Float(
        load_default=0.0,
        validate=validate.Range(min=0, max=1),
    )
    round_progress = fields.Float(
        load_default=0.0,
        validate=validate.Range(min=0, max=1),
    )
    cost_tokens = fields.Int(load_default=0, validate=validate.Range(min=0))
    cost_usd = fields.Float(load_default=0.0, validate=validate.Range(min=0))
    risk_level = fields.Str(
        load_default="none",
        validate=validate.OneOf(["none", "low", "medium", "high"]),
    )
    obstacle_count = fields.Int(load_default=0, validate=validate.Range(min=0))
    violation_count = fields.Int(load_default=0, validate=validate.Range(min=0))
    current_phase = fields.Str(load_default="DEV")
    started_at = fields.Str(load_default=None, allow_none=True)
    ended_at = fields.Str(load_default=None, allow_none=True)
