from typing import Annotated

from fastapi import Depends

from src.modules.demograph.application.use_cases.pipeline import Pipeline
from src.modules.demograph.presentation.dependencies.providers import get_pipeline

PipelineDep = Annotated[Pipeline, Depends(get_pipeline)]
