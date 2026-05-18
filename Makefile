.PHONY: test test-audio

test:
	uv run pytest -m "not manual" tests

test-audio:
	CHORES_TEST_AUDIO=1 uv run --env-file .env pytest -m manual tests/manual/test_audio.py -s
