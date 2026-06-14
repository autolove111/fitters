import re
from dataclasses import dataclass
from pathlib import Path

from rag.sources import load_sources


@dataclass(frozen=True)
class FitnessGuidance:
    source: str
    title: str
    url: str
    text: str
    keywords: tuple[str, ...]


GUIDANCE_LIBRARY: tuple[FitnessGuidance, ...] = (
    FitnessGuidance(
        source="WHO",
        title="WHO guidelines on physical activity and sedentary behaviour",
        url="https://www.who.int/publications/i/item/9789240015128",
        text=(
            "Adults should do 150-300 minutes of moderate-intensity aerobic physical activity "
            "or 75-150 minutes of vigorous-intensity aerobic activity each week, and reduce sedentary time."
        ),
        keywords=("adult", "weekly", "moderate", "aerobic", "sedentary", "activity"),
    ),
    FitnessGuidance(
        source="CDC",
        title="Adult Activity: An Overview",
        url="https://www.cdc.gov/physical-activity-basics/guidelines/adults.html",
        text=(
            "Adults need aerobic activity plus at least 2 days of muscle-strengthening activity each week. "
            "Beginners can spread activity across the week and start with manageable sessions."
        ),
        keywords=("adult", "strength", "muscle", "beginner", "weekly", "aerobic"),
    ),
    FitnessGuidance(
        source="ACSM",
        title="Physical Activity Guidelines",
        url="https://acsm.org/education-resources/trending-topics-resources/physical-activity-guidelines/",
        text=(
            "Healthy adults can use moderate intensity aerobic activity on five days per week, "
            "or vigorous activity on three days per week, plus strength work for major muscle groups."
        ),
        keywords=("moderate", "vigorous", "strength", "muscle", "intensity", "aerobic"),
    ),
    FitnessGuidance(
        source="ACSM",
        title="Exercise preparticipation screening",
        url="https://www.exerciseismedicine.org/assets/page_documents/ACSM%20Preparticipation%20Screening%20Guidelines.pdf",
        text=(
            "Exercise plans should screen for symptoms, known disease, current activity level, and safety risks. "
            "Pain or discomfort should lower intensity and may require professional advice."
        ),
        keywords=("screening", "risk", "pain", "discomfort", "knee", "injury", "safety"),
    ),
    FitnessGuidance(
        source="Mayo Clinic",
        title="Exercise intensity: How to measure it",
        url="https://www.mayoclinic.org/healthy-lifestyle/fitness/in-depth/exercise-intensity/art-20046887",
        text=(
            "Exercise intensity can be guided by perceived exertion, heart rate, breathing, and ability to talk. "
            "Beginners should progress gradually and avoid pushing through warning symptoms."
        ),
        keywords=("intensity", "beginner", "heart", "breathing", "progress", "symptoms"),
    ),
    FitnessGuidance(
        source="Harvard Health",
        title="Strength training builds more than muscles",
        url="https://www.health.harvard.edu/staying-healthy/strength-training-builds-more-than-muscles",
        text=(
            "Strength training supports muscle, metabolism, bones, balance, and daily function. "
            "A balanced routine can combine resistance work with aerobic activity."
        ),
        keywords=("strength", "muscle", "resistance", "metabolism", "balance", "routine"),
    ),
    FitnessGuidance(
        source="NIH",
        title="Physical Activity and Your Heart",
        url="https://www.nhlbi.nih.gov/health/heart/physical-activity",
        text=(
            "Regular physical activity helps the heart and overall health. "
            "Plans should match current fitness and increase activity over time."
        ),
        keywords=("heart", "regular", "fitness", "activity", "health", "increase"),
    ),
    FitnessGuidance(
        source="Cleveland Clinic",
        title="Rest and Recovery After Exercise",
        url="https://health.clevelandclinic.org/rest-and-recovery-after-exercise",
        text=(
            "Recovery matters for adaptation and reducing overuse risk. "
            "Sleep, hydration, lighter days, and mobility work can help the body respond to training."
        ),
        keywords=("recovery", "sleep", "hydration", "mobility", "overuse", "training"),
    ),
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def _markdown_guidance_library() -> tuple[FitnessGuidance, ...]:
    source_dir = Path(__file__).resolve().parent / "rag_sources"
    sources = load_sources(source_dir)
    if not sources:
        return ()
    return tuple(
        FitnessGuidance(
            source=item.source,
            title=item.title,
            url=item.url,
            text=item.text,
            keywords=tuple(item.topics),
        )
        for item in sources
    )


def _guidance_library() -> tuple[FitnessGuidance, ...]:
    markdown_items = _markdown_guidance_library()
    if not markdown_items:
        return GUIDANCE_LIBRARY
    seen = set()
    merged: list[FitnessGuidance] = []
    for item in (*markdown_items, *GUIDANCE_LIBRARY):
        key = item.url or item.title
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return tuple(merged)


def retrieve_fitness_guidance(query: str, limit: int = 3) -> list[dict[str, str]]:
    query_tokens = _tokens(query)
    scored: list[tuple[int, FitnessGuidance]] = []

    library = _guidance_library()
    for item in library:
        keyword_score = sum(3 for keyword in item.keywords if keyword.lower() in query_tokens)
        text_score = len(query_tokens.intersection(_tokens(item.text)))
        score = keyword_score + text_score
        if score > 0:
            scored.append((score, item))

    if len(scored) < len(library):
        matched = {item.url for _, item in scored}
        scored.extend((0, item) for item in library if item.url not in matched)

    scored.sort(key=lambda entry: entry[0], reverse=True)
    return [
        {
            "source": item.source,
            "title": item.title,
            "url": item.url,
            "text": item.text,
        }
        for _, item in scored[: max(1, min(limit, 8))]
    ]


def build_personalized_rag_documents(
    profile: dict,
    stats: dict,
    history: list[dict],
) -> list[dict[str, str]]:
    equipment = profile.get("equipment") or []
    equipment_text = ", ".join(equipment) if isinstance(equipment, list) and equipment else "bodyweight"
    goal = profile.get("goal") or "general_fitness"
    level = profile.get("fitnessLevel") or "beginner"
    injuries = profile.get("injuries") or "none reported"
    preferred_time = profile.get("preferredWorkoutTime") or "evening"
    workout_values = [float(item.get("workoutMinutes") or 0) for item in history]
    sleep_values = [float(item.get("sleepHours") or 0) for item in history if item.get("sleepHours")]
    diet_values = [float(item.get("dietCalories") or 0) for item in history if item.get("dietCalories")]
    avg_workout = round(sum(workout_values) / len(workout_values), 1) if workout_values else 0
    avg_sleep = round(sum(sleep_values) / len(sleep_values), 1) if sleep_values else 0
    avg_diet = round(sum(diet_values) / len(diet_values), 1) if diet_values else 0
    today_minutes = stats.get("completedMinutes") or 0
    today_steps = stats.get("steps") or 0

    return [
        {
            "source": "个人画像RAG",
            "title": "目标、水平与器械偏好",
            "url": "fitters://personal-rag/profile",
            "text": (
                f"User goal is {goal}, level is {level}, available equipment is {equipment_text}, "
                f"and preferred workout time is {preferred_time}."
            ),
            "scope": "personal",
        },
        {
            "source": "30天趋势RAG",
            "title": "运动、睡眠与饮食历史",
            "url": "fitters://personal-rag/trends",
            "text": (
                f"Recent averages: workout {avg_workout} min/day, sleep {avg_sleep} h/day, "
                f"diet {avg_diet} kcal/day across available history."
            ),
            "scope": "personal",
        },
        {
            "source": "风险偏好RAG",
            "title": "伤痛与恢复限制",
            "url": "fitters://personal-rag/risk",
            "text": f"Reported limitation is {injuries}; plan should avoid aggravating risk and control impact.",
            "scope": "personal",
        },
        {
            "source": "今日状态RAG",
            "title": "今日完成量与负荷",
            "url": "fitters://personal-rag/today",
            "text": f"Today already completed {today_minutes} workout minutes and {today_steps} steps.",
            "scope": "personal",
        },
    ]
