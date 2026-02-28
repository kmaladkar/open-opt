from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    question: str = ""
    household_id: int | None = None
    include_visualization: bool = True


class RecommendationResponse(BaseModel):
    response: str
    chart_spec: dict | None = None


class RecommendationItem(BaseModel):
    title: str
    response: str
    chart_spec: dict | None = None


class AutoRecommendationsResponse(BaseModel):
    recommendations: list[RecommendationItem]
    chart_spec: dict | None = None
