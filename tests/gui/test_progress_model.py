from tts_builder.events import PipelineEvent
from tts_builder.gui.models import ProgressModel, STAGES


def test_stage_order_includes_prepare_and_pipeline():
    assert STAGES == ('prepare', 'source', 'separate', 'normalize', 'asr', 'segment', 'export')


def test_completed_path_reaches_100_percent():
    model = ProgressModel()
    for stage in STAGES:
        model.consume(PipelineEvent(kind='stage_started', stage=stage))
        model.consume(PipelineEvent(kind='stage_completed', stage=stage))
    assert model.overall_percent == 100
    assert all(model.stages[name].status == 'completed' for name in STAGES)


def test_cache_hit_completes_stage():
    model = ProgressModel()
    model.consume(PipelineEvent(kind='stage_cache_hit', stage='asr', message='cached'))
    assert model.stages['asr'].status == 'cached'
    assert model.stages['asr'].percent == 100
