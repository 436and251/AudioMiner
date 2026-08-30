from tts_builder.events import CancellationToken, PipelineCancelled, PipelineEvent


def test_cancellation_token_raises_after_cancel():
    token = CancellationToken()
    token.cancel()
    try:
        token.raise_if_cancelled()
    except PipelineCancelled:
        return
    raise AssertionError('expected PipelineCancelled')


def test_pipeline_event_defaults_are_safe():
    event = PipelineEvent(kind='log', message='hello')
    assert event.stage is None
    assert event.current is None
    assert event.total is None
    assert event.metadata == {}
