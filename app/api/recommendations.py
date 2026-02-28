"""
Recommendations API: delegates to main agent (which routes to Visualization agent for recommendation intents).
Returns narrative and optional chart_spec from the Visualization agent.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.household_member import HouseholdMember
from app.agents.recommendation_agent import run_recommendation_agent, run_auto_recommendations_list
from app.schemas.recommendations import (
    RecommendationRequest,
    RecommendationResponse,
    AutoRecommendationsResponse,
)

router = APIRouter()


def _get_household_id_for_user(db: Session, user_id: int, household_id: int | None) -> int:
    """Return household_id if user is a member; else use first membership; else 404."""
    memberships = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.user_id == user_id)
        .all()
    )
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No household found for user",
        )
    if household_id is not None:
        if not any(m.household_id == household_id for m in memberships):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this household",
            )
        return household_id
    return memberships[0].household_id


@router.post("", response_model=RecommendationResponse)
def post_recommendations(
    body: RecommendationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Recommendation agent: queries the DB via tools (accounts, goals, transaction patterns, etc.),
    retrieves recommendations (LLM), and visualizes (chart spec). Returns narrative + optional chart_spec.
    """
    household_id = _get_household_id_for_user(db, current_user.id, body.household_id)
    result = run_recommendation_agent(
        db=db,
        household_id=household_id,
        question=body.question or "",
        include_visualization=body.include_visualization,
    )
    return RecommendationResponse(
        response=result.get("response", ""),
        chart_spec=result.get("chart_spec"),
    )


@router.get("/auto", response_model=AutoRecommendationsResponse)
def get_auto_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Automatic recommendations for the current user's household: 5+ recommendations (title + body)
    and one chart spec. Used by the dashboard "Recommended for you" section at the bottom.
    """
    household_id = _get_household_id_for_user(db, current_user.id, None)
    result = run_auto_recommendations_list(
        db=db,
        household_id=household_id,
        include_visualization=True,
        min_recommendations=5,
    )
    items = [
        {
            "title": r.get("title", "Recommendation"),
            "response": r.get("response", ""),
            "chart_spec": r.get("chart_spec"),
        }
        for r in result.get("recommendations", [])
    ]
    return AutoRecommendationsResponse(
        recommendations=items,
        chart_spec=result.get("chart_spec"),
    )
